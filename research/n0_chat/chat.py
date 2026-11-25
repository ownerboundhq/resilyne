"""Interactive local demo; experimental synthetic dialogue model."""
import torch
from train import Model, v, generate, P
m=Model(len(v));m.load_state_dict(torch.load(P/'weights.pt',map_location='cpu',weights_only=True));m.eval()
history=[]
print('Neuravale N0 Chat 003 — narrow experimental model. Type /reset or /quit.')
while True:
 try: q=input('You: ').strip()
 except (EOFError,KeyboardInterrupt):break
 if q=='/quit':break
 if q=='/reset':history=[];continue
 if not q:continue
 if len(q)>160:print('Please use a short message.');continue
 history=history[-6:]+[q]
 from train import prefix
 while len(prefix(history))>85 and len(history)>1:history=history[2:]
 if len(prefix(history))>85:history=[];print('Message too long.');continue
 a=generate(m,history);history.append(a);print('Neuravale:',a)
