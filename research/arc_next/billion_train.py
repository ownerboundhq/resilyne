"""Dedicated GPU continuation from Arc Next alignment; atomic periodic checkpoints."""
import argparse, hashlib, json, pathlib, random, time, math
import numpy as np
import torch
import sentencepiece as spm
from train import GPT, corpus, read, seqs, chatbatch, loss_for, measure
from billion_data import sha_file

INITIAL='93970736d02a48087aaecd33fbdefe9c7bc3d67667de66a75cda3448eff96736'
TARGET=1_000_000_000
def totals(report):
    return {k:sum(int(s['supervised_tokens']) for s in report['stages'] if s['stage']==k) for k in ('pretrain','chat')}
def main():
    p=argparse.ArgumentParser();p.add_argument('--checkpoint',required=True);p.add_argument('--original-data',required=True);p.add_argument('--corpus',required=True);p.add_argument('--out',required=True)
    p.add_argument('--batch',type=int,default=64);p.add_argument('--max-steps',type=int,default=0);p.add_argument('--save-every',type=int,default=500);p.add_argument('--device',choices=['cuda','cpu'],default='cuda')
    p.add_argument('--additional-chat-tokens',type=int,default=1000000)
    a=p.parse_args()
    if a.batch<1 or a.save_every<1 or a.max_steps<0 or a.additional_chat_tokens<1:p.error('Invalid training limits')
    if a.device=='cuda' and not torch.cuda.is_available():raise RuntimeError('Dedicated CUDA GPU required; no automatic paid compute provisioning')
    torch.manual_seed(42);torch.set_num_threads(min(8,torch.get_num_threads()))
    device=a.device;source=pathlib.Path(a.checkpoint);data=pathlib.Path(a.original_data);root=pathlib.Path(a.corpus);out=pathlib.Path(a.out);out.mkdir(parents=True,exist_ok=True)
    latest=out/'checkpoint.pt';resuming=latest.exists()
    ck=torch.load(latest if resuming else source,map_location=device,weights_only=True)
    manifest=json.loads((root/'manifest.json').read_text())
    if manifest['format']!='arc-next-u16le-v1' or manifest['token_positions']<250000000:raise ValueError('Need at least 250 million expanded corpus token positions')
    path=root/manifest['file']
    if path.stat().st_size!=2*manifest['token_positions'] or sha_file(path)!=manifest['sha256']:raise ValueError('Expanded corpus checksum mismatch')
    tokenizer=source.with_name('tokenizer.model')
    if sha_file(tokenizer)!=manifest['tokenizer_sha256']:raise ValueError('Tokenizer mismatch')
    if sha_file(data/'provenance.json')!=manifest['original_provenance_sha256']:raise ValueError('Original corpus provenance mismatch')
    original=json.loads((data/'provenance.json').read_text())
    if original!=ck['report']['provenance']:raise ValueError('Original provenance changed')
    for name,meta in original['files'].items():
        if sha_file(data/name)!=meta['sha256']:raise ValueError('Original corpus hash mismatch: '+name)
    if not resuming and sha_file(source)!=INITIAL:raise ValueError('Expected the verified alignment checkpoint')
    if ck['config']!={'vocab':4096,'width':256,'heads':4,'layers':4,'context':128}:raise ValueError('Unexpected model architecture')
    sp=spm.SentencePieceProcessor(model_file=str(tokenizer));T=ck['config']['context'];B=a.batch
    model=GPT(ck['config']).to(device);model.load_state_dict(ck['model'])
    opt=torch.optim.AdamW(model.parameters(),lr=.0003,weight_decay=.1);opt.load_state_dict(ck['optimizer'])
    report=ck['report'];before=totals(report)
    if before['pretrain']+before['chat']!=report['training_tokens_processed']:raise ValueError('Prior token accounting mismatch')
    rng=random.Random(20261125);campaign={'manifest_sha256':sha_file(root/'manifest.json'),'source_checkpoint_sha256':INITIAL,'pretraining_target':TARGET,'chat_target':before['chat']+a.additional_chat_tokens,'batch':B}
    if resuming:
        previous=ck['billion_campaign']
        if any(previous[k]!=campaign[k] for k in ('manifest_sha256','source_checkpoint_sha256','pretraining_target','batch')):raise ValueError('Campaign settings changed')
        campaign=previous;rng.setstate(ck['rng_state'])
    else:
        # Preserve original model weights and optimizer, and record the expanded corpus separately.
        import shutil
        shutil.copy2(tokenizer,out/'tokenizer.model')
        report['expanded_corpus']=manifest
    tokens=np.memmap(path,dtype='<u2',mode='r')
    pv=corpus(read(data/'pretrain_val.jsonl'),sp)
    trainchat=seqs(read(data/'chat.jsonl'),sp,T);valchat=seqs(read(data/'chat_val.jsonl'),sp,T)
    def prebatch(r):
        starts=np.array([r.randrange(len(tokens)-T) for _ in range(B)],dtype=np.int64)
        z=torch.from_numpy(np.asarray(tokens[starts[:,None]+np.arange(T+1)],dtype=np.int64)).to(device)
        return z[:,:-1],z[:,1:]
    def validpre(r):
        starts=torch.tensor([r.randrange(len(pv)-T) for _ in range(min(B,8))])
        z=pv[starts[:,None]+torch.arange(T+1)].to(device);return z[:,:-1],z[:,1:]
    def validchat(r):return chatbatch(valchat,T,min(B,8),r,device)
    report['billion_campaign']=campaign;report['release_status']='research only; no automatic website deployment'
    def save():
        now=totals(report)
        if sum(now.values())!=report['training_tokens_processed']:raise RuntimeError('Token accounting mismatch')
        report['actual_stage_tokens']=now
        report['token_targets']={'pretrain':TARGET,'chat':campaign['chat_target']}
        report['target_met']={k:now[k]>=v for k,v in report['token_targets'].items()}
        tmp=out/'checkpoint.tmp'
        torch.save({'model':model.state_dict(),'optimizer':opt.state_dict(),'config':ck['config'],'report':report,'billion_campaign':campaign,'rng_state':rng.getstate()},tmp)
        tmp.replace(latest)
        rtmp=out/'report.tmp';rtmp.write_text(json.dumps(report,indent=2));rtmp.replace(out/'report.json')
        print('CHECKPOINT',json.dumps({'actual':now,'target':report['token_targets'],'met':report['target_met']}),flush=True)
    session_steps=0
    for stage,fn,val,target,lr in [('pretrain',prebatch,validpre,TARGET,.0003),('chat',lambda r:chatbatch(trainchat,T,B,r,device),validchat,campaign['chat_target'],.0001)]:
        if totals(report)[stage]>=target:continue
        entry={'stage':stage,'steps':0,'supervised_tokens':0,'validation_before':measure(model,val,202),'campaign':'billion-v1'};report['stages'].append(entry)
        count=totals(report)[stage]
        for group in opt.param_groups:group['lr']=lr
        start=time.monotonic()
        while count<target:
            if a.max_steps and session_steps>=a.max_steps:break
            model.train();x,y=fn(rng);opt.zero_grad(set_to_none=True);loss=loss_for(model,x,y)
            if not torch.isfinite(loss):raise RuntimeError('Nonfinite loss; previous checkpoint preserved')
            loss.backward();torch.nn.utils.clip_grad_norm_(model.parameters(),1.0);opt.step()
            n=int((y!=-100).sum().item());count+=n;entry['steps']+=1;entry['supervised_tokens']+=n;report['training_tokens_processed']+=n;session_steps+=1
            if entry['steps']%50==0:print(stage,'tokens',count,'loss',float(loss),'elapsed',round(time.monotonic()-start),flush=True)
            if session_steps%a.save_every==0:save()
        entry['validation_after']=measure(model,val,202);entry['validation_perplexity']=math.exp(min(entry['validation_after'],20));save()
        if a.max_steps and session_steps>=a.max_steps:break
    save()
if __name__=='__main__':main()
