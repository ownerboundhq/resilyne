"""Local inference for independently trained Arc Next checkpoints; no external API."""
import argparse, json, pathlib
import torch
import sentencepiece as spm
from train import GPT
class Session:
    def __init__(self,checkpoint,tokenizer=None,device=None):
        checkpoint=pathlib.Path(checkpoint)
        self.device=device or ('cuda' if torch.cuda.is_available() else 'cpu')
        torch.set_num_threads(min(4,torch.get_num_threads()))
        ck=torch.load(checkpoint,map_location=self.device,weights_only=True)
        self.model=GPT(ck['config']).to(self.device)
        self.model.load_state_dict(ck['model']);self.model.eval()
        self.sp=spm.SentencePieceProcessor(model_file=str(tokenizer or checkpoint.with_name('tokenizer.model')))
        if self.sp.vocab_size()!=ck['config']['vocab']:raise ValueError('Wrong tokenizer for this model')
        self.context=ck['config']['context']
        self.u=self.sp.piece_to_id('<user>');self.a=self.sp.piece_to_id('<assistant>')
        self.report=ck.get('report',{})
    def encode(self,turns,reserve=1):
        if not turns or len(turns)%2!=1:raise ValueError('Expected alternating user/assistant turns ending with user')
        budget=self.context-reserve
        def enc(s):
            for marker in ('<user>','<assistant>','<s>','</s>','<pad>','<unk>'):s=s.replace(marker,'')
            return self.sp.encode(s)
        if budget<4:raise ValueError('Context too small')
        last=enc(turns[-1])
        if len(last)>budget-3:raise ValueError('Question too long for this model')
        ids=[self.sp.bos_id(),self.u]+last+[self.a]
        for i in range(len(turns)-3,-1,-2):
            pair=[self.u]+enc(turns[i])+[self.a]+enc(turns[i+1])
            if len(ids)+len(pair)>budget:break
            ids=ids[:1]+pair+ids[1:]
        return ids
    @torch.inference_mode()
    def answer(self,turns,max_new=64):
        ids=self.encode(turns,reserve=1);out=[]
        banned=[self.sp.pad_id(),self.sp.bos_id(),self.sp.unk_id(),self.u,self.a]
        stop='length'
        for _ in range(min(max_new,self.context-len(ids))):
            z=self.model(torch.tensor([ids+out],device=self.device))[0,-1].clone()
            z[banned]=-float('inf')
            j=int(z.argmax())
            if j==self.sp.eos_id():stop='eos';break
            out.append(j)
        return {'text':self.sp.decode(out),'generated_tokens':len(out),'stop':stop}
def main():
    p=argparse.ArgumentParser();p.add_argument('checkpoint');p.add_argument('--prompt');p.add_argument('--max-new',type=int,default=64);a=p.parse_args()
    s=Session(a.checkpoint)
    if a.prompt is not None:print(json.dumps(s.answer([a.prompt],a.max_new),ensure_ascii=False));return
    history=[]
    print('Arc Next research preview. /reset or /quit.')
    while True:
        try:q=input('You: ').strip()
        except (KeyboardInterrupt,EOFError):break
        if q=='/quit':break
        if q=='/reset':history=[];continue
        if not q:continue
        try:r=s.answer(history+[q],a.max_new)
        except ValueError as e:print(e);continue
        print('Arc:',r['text'] or '(empty response)')
        if r['text']:history=(history+[q,r['text']])[-6:]
if __name__=='__main__':main()
