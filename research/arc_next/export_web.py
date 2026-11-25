"""Export exact float32 parameters and SentencePiece BPE pieces for browser inference."""
import argparse, base64, hashlib, json, pathlib, struct
import torch
from inference import Session

def main():
    p=argparse.ArgumentParser();p.add_argument('checkpoint');p.add_argument('--out',required=True);p.add_argument('--fixtures',required=True);a=p.parse_args()
    path=pathlib.Path(a.checkpoint);digest=hashlib.sha256(path.read_bytes()).hexdigest()
    if digest!='93970736d02a48087aaecd33fbdefe9c7bc3d67667de66a75cda3448eff96736':raise ValueError('Unexpected source checkpoint')
    s=Session(path,device='cpu');ck=torch.load(path,map_location='cpu',weights_only=True)
    tensors={}
    for name,t in ck['model'].items():
        if name=='out.weight':
            if not torch.equal(t,ck['model']['emb.weight']):raise ValueError('Output weights not tied')
            continue
        v=t.detach().cpu().float().contiguous().reshape(-1)
        tensors[name]={'shape':list(t.shape),'f32':base64.b64encode(struct.pack('<'+str(v.numel())+'f',*v.tolist())).decode('ascii')}
    count=sum(x.numel() for x in s.model.parameters())
    if count!=4240896 or s.report.get('training_tokens_processed')!=5616530:raise ValueError('Unexpected checkpoint statistics')
    pack={'format':'neuravale.arcnext.f32le.v1','model':'Neuravale Arc Next','checkpoint_sha256':digest,'config':ck['config'],'parameters':count,'training_tokens':5616530,'evaluation':{'correct':0,'total':60},'tokenizer':{'pieces':[s.sp.id_to_piece(i) for i in range(s.sp.vocab_size())],'scores':[s.sp.get_score(i) for i in range(s.sp.vocab_size())],'pad':s.sp.pad_id(),'bos':s.sp.bos_id(),'eos':s.sp.eos_id(),'unk':s.sp.unk_id(),'user':s.u,'assistant':s.a},'tensors':tensors}
    pathlib.Path(a.out).write_text(json.dumps(pack,separators=(',',':'),ensure_ascii=False),encoding='utf-8')
    prompts=[['Hello!'],['What is your name?'],['What is the difference between a lake and a river?'],['What is 17 plus 26?'],['My name is Alex.','Nice to meet you.','What is my name?'],['A   little  space.'],['Hello, world!']]
    fixtures=[]
    for turns in prompts:
        fixtures.append({'turns':turns,'ids':s.encode(turns),'response':s.answer(turns,max_new=32)['text']})
    pathlib.Path(a.fixtures).write_text(json.dumps(fixtures,ensure_ascii=False),encoding='utf-8')
    print('Exported exact source checkpoint',digest,'parameters',count,'browser bytes',pathlib.Path(a.out).stat().st_size)
if __name__=='__main__':main()
