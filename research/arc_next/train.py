"""Original decoder-only transformer: next-token pretraining, then response-only SFT."""
import argparse, json, math, pathlib, random, time
import torch
from torch import nn
import torch.nn.functional as F
import sentencepiece as spm
class Block(nn.Module):
    def __init__(self,d,heads):
        super().__init__();self.heads=heads;self.n1=nn.LayerNorm(d);self.qkv=nn.Linear(d,3*d);self.proj=nn.Linear(d,d);self.n2=nn.LayerNorm(d);self.ff=nn.Sequential(nn.Linear(d,4*d),nn.GELU(),nn.Linear(4*d,d))
    def forward(self,x):
        b,t,d=x.shape; q,k,v=self.qkv(self.n1(x)).reshape(b,t,3,self.heads,d//self.heads).permute(2,0,3,1,4).unbind(0)
        a=F.scaled_dot_product_attention(q,k,v,is_causal=True).transpose(1,2).reshape(b,t,d)
        x=x+self.proj(a);return x+self.ff(self.n2(x))
class GPT(nn.Module):
    def __init__(self,c):
        super().__init__();self.config=c;d=c['width'];self.emb=nn.Embedding(c['vocab'],d);self.pos=nn.Embedding(c['context'],d);self.blocks=nn.Sequential(*[Block(d,c['heads']) for _ in range(c['layers'])]);self.norm=nn.LayerNorm(d);self.out=nn.Linear(d,c['vocab'],bias=False);self.apply(self.init);self.out.weight=self.emb.weight
    @staticmethod
    def init(m):
        if isinstance(m,(nn.Embedding,nn.Linear)):nn.init.normal_(m.weight,std=.02)
        if isinstance(m,nn.Linear) and m.bias is not None:nn.init.zeros_(m.bias)
    def forward(self,x):
        return self.out(self.norm(self.blocks(self.emb(x)+self.pos(torch.arange(x.shape[1],device=x.device)))))
def read(p):return [json.loads(s) for s in p.read_text(encoding='utf-8').splitlines() if s.strip()]
def make_tokenizer(data,out,vocab):
    lines=out/'tokenizer_input.txt'
    with lines.open('w',encoding='utf-8') as f:
        for r in read(data/'pretrain.jsonl'):f.write(' '.join(r['text'].split())+'\n')
        for r in read(data/'chat.jsonl'):
            for s in [*r['turns'],r['answer']]:f.write(' '.join(s.split())+'\n')
    spm.SentencePieceTrainer.train(input=str(lines),model_prefix=str(out/'tokenizer'),vocab_size=vocab,model_type='bpe',byte_fallback=True,character_coverage=1.0,hard_vocab_limit=False,pad_id=0,unk_id=1,bos_id=2,eos_id=3,user_defined_symbols=['<user>','<assistant>'],num_threads=4,shuffle_input_sentence=False)
    lines.unlink()
def seqs(rows,sp,T):
    u=sp.piece_to_id('<user>');a=sp.piece_to_id('<assistant>');result=[]
    for r in rows:
        if not r['turns'] or len(r['turns'])%2!=1:continue
        # Keep at least half of the available context for the question/history.
        # Do not teach an artificial EOS at the truncation boundary.
        answer=sp.encode(r['answer'])+[sp.eos_id()]
        answer=answer[:max(1,T//2)]
        newest=sp.encode(r['turns'][-1])
        budget=T+1-len(answer)
        newest=newest[-max(1,budget-3):]
        prefix=[sp.bos_id(),u]+newest+[a]
        # Retain complete earlier dialogue pairs where space permits.
        for i in range(len(r['turns'])-3,-1,-2):
            pair=[u]+sp.encode(r['turns'][i])+[a]+sp.encode(r['turns'][i+1])
            if len(prefix)+len(pair)>budget:break
            prefix=prefix[:1]+pair+prefix[1:]
        if len(prefix)+len(answer)>T+1:raise RuntimeError('Context overflow')
        x=prefix+answer;y=[-100]*len(prefix)+answer
        result.append((x[:-1],y[1:]))
    if not result:raise ValueError('No usable dialogue examples')
    return result
def corpus(rows,sp):
    ids=[]
    for r in rows:ids.extend(sp.encode(r['text'])+[sp.eos_id()])
    return torch.tensor(ids,dtype=torch.long)
def prebatch(tokens,T,B,rng,device):
    starts=torch.tensor([rng.randrange(len(tokens)-T) for _ in range(B)])
    z=tokens[starts[:,None]+torch.arange(T+1)]
    return z[:,:-1].to(device),z[:,1:].to(device)
def chatbatch(rows,T,B,rng,device):
    batch=rng.choices(rows,k=B);n=max(len(x) for x,y in batch)
    return torch.tensor([x+[0]*(n-len(x)) for x,y in batch],device=device),torch.tensor([y+[-100]*(n-len(y)) for x,y in batch],device=device)
def loss_for(model,x,y):return F.cross_entropy(model(x).flatten(0,1),y.flatten(),ignore_index=-100)
@torch.no_grad()
def measure(model,fn,seed):
    model.eval();rng=random.Random(seed);total=0.;n=0
    for _ in range(12):
        x,y=fn(rng);count=int((y!=-100).sum());total+=float(loss_for(model,x,y))*count;n+=count
    return total/n
@torch.no_grad()
def generate(model,sp,prompt,device,max_new=80):
    model.eval();tokens=[sp.bos_id(),sp.piece_to_id('<user>')]+sp.encode(prompt)+[sp.piece_to_id('<assistant>')];out=[]
    for _ in range(max_new):
        x=torch.tensor([tokens[-model.config['context']:]],device=device)
        logits=model(x)[0,-1].clone()
        for i in [sp.pad_id(),sp.unk_id(),sp.bos_id(),sp.piece_to_id('<user>'),sp.piece_to_id('<assistant>')]:logits[i]=-float('inf')
        j=int(logits.argmax())
        if j==sp.eos_id():break
        tokens.append(j);out.append(j)
    return sp.decode(out)
def main():
    ap=argparse.ArgumentParser();ap.add_argument('--data',default='research/arc_next/data');ap.add_argument('--out',default='research/arc_next/run');ap.add_argument('--pre-steps',type=int,default=1500);ap.add_argument('--chat-steps',type=int,default=500);ap.add_argument('--width',type=int,default=256);ap.add_argument('--layers',type=int,default=4);ap.add_argument('--context',type=int,default=128);ap.add_argument('--batch',type=int,default=8);ap.add_argument('--vocab',type=int,default=4096);ap.add_argument('--seconds',type=int,default=660);ap.add_argument('--resume');ap.add_argument('--pre-token-target',type=int,default=0);ap.add_argument('--chat-token-target',type=int,default=0);ap.add_argument('--chat-extra-tokens',type=int,default=0,help='Additional supervised assistant tokens in this run, beyond prior cumulative count');ap.add_argument('--short-answer-mix',type=float,default=0.0);args=ap.parse_args()
    if not 0<=args.short_answer_mix<=1:ap.error('Short answer mix must be between 0 and 1')
    if args.chat_extra_tokens<0 or args.chat_token_target<0 or args.pre_token_target<0:ap.error('Token targets must be nonnegative')
    if args.chat_extra_tokens and args.chat_steps<=0:ap.error('--chat-extra-tokens requires positive --chat-steps')
    torch.manual_seed(42);torch.set_num_threads(min(4,torch.get_num_threads()));device='cuda' if torch.cuda.is_available() else 'cpu';p=pathlib.Path(args.data);o=pathlib.Path(args.out);o.mkdir(parents=True,exist_ok=True)
    if args.resume:
        ck=torch.load(args.resume,map_location=device,weights_only=True);c=ck['config'];sp=spm.SentencePieceProcessor(model_file=str(o/'tokenizer.model'));assert c['vocab']==sp.vocab_size()
    else:
        make_tokenizer(p,o,args.vocab);sp=spm.SentencePieceProcessor(model_file=str(o/'tokenizer.model'));c={'vocab':sp.vocab_size(),'width':args.width,'heads':4,'layers':args.layers,'context':args.context}
    m=GPT(c).to(device);opt=torch.optim.AdamW(m.parameters(),lr=.0006,weight_decay=.1);T=c['context'];B=args.batch
    pre=corpus(read(p/'pretrain.jsonl'),sp);pv=corpus(read(p/'pretrain_val.jsonl'),sp)
    trainchat=seqs(read(p/'chat.jsonl'),sp,T);valchat=seqs(read(p/'chat_val.jsonl'),sp,T)
    if min(len(pre),len(pv))<=T:raise ValueError('Not enough pretraining tokens')
    pf=lambda r:prebatch(pre,T,B,r,device);vf=lambda r:prebatch(pv,T,B,r,device)
    shortchat=[(x,y) for x,y in trainchat if y[-1]==sp.eos_id() and 2<=sum(v!=-100 for v in y)<=32]
    if args.short_answer_mix and len(shortchat)<50:raise RuntimeError('Insufficient complete short answers')
    print('Complete short-answer training rows:',len(shortchat),flush=True)
    def cf(r):return chatbatch(shortchat if args.short_answer_mix and r.random()<args.short_answer_mix else trainchat,T,B,r,device)
    cv=lambda r:chatbatch(valchat,T,B,r,device)
    report={'model':'Arc Next (research candidate)','parameters':sum(x.numel() for x in m.parameters()),'config':c,'device':device,'unique_pretraining_tokens':len(pre),'heldout_pretraining_tokens':len(pv),'conversation_training_rows':len(trainchat),'heldout_conversation_rows':len(valchat),'training_tokens_processed':0,'stages':[],'provenance':json.loads((p/'provenance.json').read_text()) if (p/'provenance.json').exists() else None}
    if args.resume:
        current=report['provenance'];m.load_state_dict(ck['model']);opt.load_state_dict(ck['optimizer']);report=ck['report']
        if current!=report['provenance']:raise RuntimeError('Resume corpus provenance changed')
    prior_chat_tokens=sum(s['supervised_tokens'] for s in report['stages'] if s['stage']=='chat')
    report_target={'pretrain':args.pre_token_target,'chat':max(args.chat_token_target,prior_chat_tokens+args.chat_extra_tokens) if args.chat_extra_tokens else args.chat_token_target}
    report['requested_additional_chat_tokens']=args.chat_extra_tokens
    report['short_answer_mix']=args.short_answer_mix
    report['complete_short_answer_rows']=len(shortchat)
    if not args.resume:report['baseline']={'pretrain_loss':measure(m,vf,100),'chat_loss':measure(m,cv,101)}
    print(json.dumps({k:v for k,v in report.items() if k!='provenance'}),flush=True)
    report['corpus_pretraining_token_positions']=len(pre)
    report['token_targets']=report_target
    report['conversation_packing']='v2: retains latest user prompt and masks history; answer truncation does not fabricate EOS'
    start=time.monotonic()
    def save():
        tmp=o/'checkpoint.tmp';torch.save({'model':m.state_dict(),'optimizer':opt.state_dict(),'config':c,'report':report},tmp);tmp.replace(o/'checkpoint.pt')
        (o/'report.json').write_text(json.dumps(report,indent=2))
    for name,fn,val,steps,limit,lr in [('pretrain',pf,vf,args.pre_steps,args.seconds*.72,.0006),('chat',cf,cv,args.chat_steps,args.seconds,.0002)]:
        prior=sum(s['steps'] for s in report['stages'] if s['stage']==name);rng=random.Random(42+prior+(10000 if name=='chat' else 0));done=0
        prior_tokens=sum(s['supervised_tokens'] for s in report['stages'] if s['stage']==name);target=report_target[name]
        for group in opt.param_groups:group['lr']=lr
        before=measure(m,val,202);start_tokens=report['training_tokens_processed']
        for i in range(steps):
            if target and prior_tokens+report['training_tokens_processed']-start_tokens>=target:break
            if time.monotonic()-start>limit:break
            m.train();x,y=fn(rng);opt.zero_grad(set_to_none=True);loss=loss_for(m,x,y)
            if not torch.isfinite(loss):raise RuntimeError('Nonfinite loss')
            loss.backward();nn.utils.clip_grad_norm_(m.parameters(),1.0);opt.step();done+=1;report['training_tokens_processed']+=int((y!=-100).sum())
            if done%50==0:print(name,done,'loss',round(float(loss),3),'stage_tokens_total',prior_tokens+report['training_tokens_processed']-start_tokens,'elapsed',round(time.monotonic()-start),flush=True)
        after=measure(m,val,202);report['stages'].append({'stage':name,'steps':done,'supervised_tokens':report['training_tokens_processed']-start_tokens,'validation_before':before,'validation_after':after,'validation_perplexity':math.exp(min(after,20)),'packing':'v2' if name=='chat' else 'plain language'});save();print(report['stages'][-1],flush=True)
    report['actual_stage_tokens']={name:sum(s['supervised_tokens'] for s in report['stages'] if s['stage']==name) for name in ('pretrain','chat')}
    report['target_met']={name:report['actual_stage_tokens'][name]>=target for name,target in report_target.items() if target}
    print('TOKEN ACCOUNTING',json.dumps({'actual':report['actual_stage_tokens'],'targets':report_target,'met':report['target_met']}),flush=True)
    prompts=['Hello! How are you?','Explain why rain falls.','What is 17 plus 26?','Who was Albert Einstein?','I am feeling frustrated today.','Do you have access to live internet?','Explain the difference between a plant and an animal.','What is the capital of Canada?']
    report['samples']=[{'prompt':q,'response':generate(m,sp,q,device)} for q in prompts];report['final']={'pretrain_loss':measure(m,vf,100),'chat_loss':measure(m,cv,101)};report['release_status']='research only: no automatic deployment; requires independent qualitative and safety evaluation';save();print(json.dumps(report['final']),flush=True)
if __name__=='__main__':main()
