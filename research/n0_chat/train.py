import json,random,re,time,pathlib,torch
from torch import nn
from torch.nn import functional as F
P=pathlib.Path(__file__).parent
random.seed(42);torch.manual_seed(42);torch.set_num_threads(4)
# Original synthetic dialogue corpus; hold out prompt variants and context combinations.
intents=[('hello|hi|hey|hello there','hello ! how can i help you ?'),('how are you|how is it going|how are things|how are you today','i am ready to help . how are you ?'),('who are you|what is your name|tell me your name|introduce yourself','i am neuravale , a small experimental conversational ai .'),('who made you|who built you|who developed you|where did you come from','i was trained from scratch for neuravale .'),('what can you do|how can you help|what are your abilities|what can you help with','i can handle simple conversations . my knowledge is limited .'),('can you browse the web|can you access the internet|can you search online|do you have internet access','no . i do not have live internet access .'),('thank you|thanks|thanks for your help|thank you very much','you are welcome !'),('goodbye|bye|see you later|talk to you later','goodbye ! take care .'),('i feel sad|i am unhappy|i am feeling down|i had a bad day','i am sorry to hear that . would you like to talk about it ?'),('i feel happy|i am excited|i had a good day|i am feeling great','that is wonderful ! what made your day good ?'),('tell me a joke|make me laugh|do you know a joke|say something funny','why did the computer get cold ? it left its windows open .'),('can you make mistakes|are you always right|are you perfect|can i trust every answer','i can make mistakes . please verify important information .'),('what is the weather today|what is the stock price today|what time is it now|what happened in the news today','i do not have live information . please check a reliable source .'),('what is artificial intelligence|explain ai|define artificial intelligence|what does ai mean','artificial intelligence is technology that performs tasks that normally require human intelligence .'),('what is a computer|define computer|explain a computer|what does a computer do','a computer is a machine that processes information .'),('can you help me|i need help|help me please|could you help','of course . what do you need help with ?'),('i do not understand|i am confused|that is confusing|can you explain again','which part would you like me to explain ?')]
tr=[];te=[]
for qs,a in intents:
 q=qs.split('|')
 for x in q[:3]:
  for pre in ('','please ','hey , '): tr.append(([pre+x],a))
  tr.append((['can you help me','of course . what do you need help with ?',x],a))
 te.append(([q[-1]],a))
for kind,vals in [('name','alex sam jordan taylor casey morgan jamie riley'),('favorite color','red blue green yellow purple orange white black'),('favorite food','pizza pasta rice soup salad apples bread tacos')]:
 for value in vals.split():
  first='my '+kind+' is '+value;ack='i will remember that .';ans='your '+kind+' is '+value+' .'
  tr.append(([first],ack))
  for query in ['what is my '+kind,'do you remember my '+kind]:
   tr.append(([first,ack,query],ans));tr.append(([first,ack,'thanks','you are welcome !',query],ans))
  te.append(([first,ack,'hello','hello ! how can i help you ?','what is my '+kind],ans))
# Vary intervening turns and context. Previous held-out examples are now development data.
for kind,vals in [('name','alex sam jordan taylor casey morgan jamie riley'),('favorite color','red blue green yellow purple orange white black'),('favorite food','pizza pasta rice soup salad apples bread tacos')]:
 for value in vals.split():
  first='my '+kind+' is '+value;ack='i will remember that .';ans='your '+kind+' is '+value+' .'
  for q,a in [('how are you','i am ready to help . how are you ?'),('who are you','i am neuravale , a small experimental conversational ai .'),('thanks','you are welcome !'),('hello','hello ! how can i help you ?')]:
   for ask in ['what is my '+kind,'do you remember my '+kind]:tr.append(([first,ack,q,a,ask],ans))
# Learn common additional paraphrases; evaluate new composed prompts separately.
for qs,a in intents:
 for q in qs.split('|'):
  for pre in ('','please ','hey , ','hello , '):tr.append(([pre+q],a))
  tr.append((['can you help me','of course . what do you need help with ?',q],a))
te=[(['please , '+qs.split('|')[-1]],a) for qs,a in intents]
for kind,vals in [('name','alex sam jordan taylor casey morgan jamie riley'),('favorite color','red blue green yellow purple orange white black'),('favorite food','pizza pasta rice soup salad apples bread tacos')]:
 for val in vals.split():te.append((['my '+kind+' is '+val,'i will remember that .','thanks','you are welcome !','hello','hello ! how can i help you ?','do you remember my '+kind],'your '+kind+' is '+val+' .'))
# Full conversation trajectories: train on varied greeting, acknowledgement and follow-up history.
for kind,vals in [('name','alex sam jordan taylor casey morgan jamie riley'),('favorite color','red blue green yellow purple orange white black'),('favorite food','pizza pasta rice soup salad apples bread tacos')]:
 for val in vals.split():
  first='my '+kind+' is '+val;ack='i will remember that .';ans='your '+kind+' is '+val+' .'
  for greeting in ['hi','hello','hey','hello there']:
   head=[greeting,'hello ! how can i help you ?']
   tr.append((head+[first],ack));head += [first,ack]
   tr.append((head+['thanks'],'you are welcome !'))
   tr.append((head+['thanks','you are welcome !','hello'],'hello ! how can i help you ?'))
   for ask in ['what is my '+kind,'do you remember my '+kind]:
    tr.append((head+[ask],ans));tr.append((head+['thanks','you are welcome !','hello','hello ! how can i help you ?',ask],ans))
for qs,a in intents:
 for q in qs.split('|'):
  tr.append((['hello','hello ! how can i help you ?',q],a))
# Train an uncertainty response on explicitly out-of-scope topics, not a universal safety guarantee.
for q in ['explain quantum physics','write a poem','how do i build a rocket','what is the capital of canada','solve this equation','what is the meaning of life','tell me about history','what is the price of gold','write a program','explain biology','how do i fix my car','what is the capital of france']:
 tr.append(([q],'i do not know enough to answer that .'))
def tok(s):return re.findall(r'[a-z0-9]+|[^\w\s]',s.lower())
v={w:i for i,w in enumerate(['<pad>','<bos>','<user>','<assistant>','<eos>','<unk>']+sorted({w for t,a in tr for s in [*t,a] for w in tok(s)}))};inv=list(v)
class Model(nn.Module):
 def __init__(self,n):
  super().__init__();self.emb=nn.Embedding(n,64);self.pos=nn.Embedding(128,64);self.layers=nn.TransformerEncoder(nn.TransformerEncoderLayer(64,4,128,dropout=0,batch_first=True,norm_first=True),2,enable_nested_tensor=False);self.out=nn.Linear(64,n)
 def forward(self,x,h=None):
  if h is not None:x=torch.cat([h,x],1)
  n=x.shape[1];mask=torch.ones(n,n,dtype=torch.bool,device=x.device).triu(1);z=self.emb(x)+self.pos(torch.arange(n,device=x.device));return self.out(self.layers(z,mask=mask)),x
def prefix(t):
 p=[1]
 for i,s in enumerate(t):p += [2 if i%2==0 else 3]+[v.get(w,5) for w in tok(s)]
 return p+[3]
def encode(r):
 p=prefix(r[0]);a=[v[w] for w in tok(r[1])]+[4];return (p+a)[:-1],[-100]*(len(p)-1)+a
@torch.no_grad()
def generate(m,t):
 m.eval();z,h=m(torch.tensor([prefix(t)]));o=[]
 for _ in range(40):
  j=int(z[0,-1].argmax());w=inv[j]
  if j<6:break
  o.append(w);z,h=m(torch.tensor([[j]]),h)
 return ' '.join(o)
def evaluate(m):
 rows=[{'turns':t,'expected':a,'actual':generate(m,t)} for t,a in te];return {'correct':sum(r['actual']==r['expected'] for r in rows),'total':len(rows),'examples':rows}
if __name__=='__main__':
 m=Model(len(v));opt=torch.optim.AdamW(m.parameters(),lr=.003);enc=[encode(r) for r in tr];before=evaluate(m);start=time.time();curve=[]
 for i in range(1250):
  m.train();b=random.choices(enc,k=32);n=max(len(x) for x,y in b);x=torch.tensor([x+[0]*(n-len(x)) for x,y in b]);y=torch.tensor([y+[-100]*(n-len(y)) for x,y in b]);opt.zero_grad();z,_=m(x);loss=F.cross_entropy(z.flatten(0,1),y.flatten(),ignore_index=-100);loss.backward();nn.utils.clip_grad_norm_(m.parameters(),1);opt.step()
  if (i+1)%100==0: print(i+1,float(loss.detach()),flush=True);curve.append({'step':i+1,'loss':float(loss.detach())})
 test=evaluate(m);report={'model':'Neuravale N0 Chat 003','architecture':'causal transformer, 2 layers, 4 heads','parameters':sum(p.numel() for p in m.parameters()),'vocabulary':len(v),'training_examples':len(tr),'steps':1250,'seconds':time.time()-start,'before':before,'test':test,'curve':curve,'limitations':'Synthetic domain-specific prompts; no evidence of general open-domain conversation. Held-out phrasing and context combinations, not unseen concepts.'};torch.save(m.state_dict(),P/'weights.pt');(P/'vocab.json').write_text(json.dumps(v));(P/'report.json').write_text(json.dumps(report,indent=2));
 for name,rows in [('train',tr),('test',te)]: (P/(name+'.jsonl')).write_text(''.join(json.dumps({'turns':t,'answer':a})+'\n' for t,a in rows))
 print({k:report[k] for k in ['parameters','vocabulary','training_examples','seconds']},test['correct'],test['total'],flush=True)
