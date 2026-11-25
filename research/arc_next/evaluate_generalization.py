"""Generate fresh compositional tests after training; never feed cases back to the trainer."""
import argparse, collections, hashlib, json, pathlib, random, re, secrets, unicodedata
from inference import Session
def norm(s):return re.sub(r'\W+',' ',unicodedata.normalize('NFKC',s).lower()).strip()
def cases(seed,n):
    r=random.Random(seed)
    colors=['amber','violet','silver','teal','orange','green','white','indigo']
    nouns=['box','lantern','cup','kite','book','stone','hat','bag']
    for i in range(n):
        # Novel proper names, arbitrary associations, and random operand pairs.
        name='Z'+''.join(r.choice('abcdefghjkmnpqrstuvwxyz') for _ in range(6))
        x,y=r.sample(colors,2);a,b=r.sample(nouns,2)
        yield ('context_binding', [f'The {a} is {x}. The {b} is {y}. What color is the {a}? Answer with one word.'],x)
        yield ('context_switch', [f'{name} owns a {a}. Another person owns a {b}. What does {name} own? One word.'],a)
        yield ('multiturn_memory',[f'My code word is {name}.','I will remember your code word.','What is my code word? Reply with only the code word.'],name)
        m,k=r.randint(11,99),r.randint(11,99)
        yield ('arithmetic',[f'What is {m} plus {k}? Give only the number.'],str(m+k))
        letters=r.sample(list('ABCDEFGHJKLMNPQRSTUV'),3)
        yield ('instruction_following',[f'Reply with only the middle letter in this sequence: {letters[0]}, {letters[1]}, {letters[2]}.'],letters[1])
        yield ('unknown_information',[f'I have not told you my favorite color. What is it? Reply unknown if you cannot know.'],'unknown')
def evaluate(session,seed,n):
    rows=[];counts=collections.defaultdict(lambda:[0,0])
    for kind,turns,expected in cases(seed,n):
        try:r=session.answer(turns,max_new=16)
        except ValueError as e:r={'text':'','generated_tokens':0,'stop':str(e)}
        ok=norm(r['text'])==norm(expected)
        counts[kind][0]+=int(ok);counts[kind][1]+=1
        rows.append({'category':kind,'turns':turns,'expected':expected,'actual':r['text'],'correct':ok,'stop':r['stop']})
    by={k:{'correct':v[0],'total':v[1]} for k,v in counts.items()}
    return {'seed':seed,'examples_per_category':n,'categories':by,'correct':sum(v[0] for v in counts.values()),'total':len(rows),'examples':rows,'note':'Randomized synthetic compositional tests. Strict exact answers. Multi-turn histories contain a supplied assistant acknowledgement, not an end-to-end generated conversation. Not a general intelligence or safety benchmark.'}
def main():
    p=argparse.ArgumentParser();p.add_argument('checkpoint');p.add_argument('--seed',type=int);p.add_argument('--n',type=int,default=20);p.add_argument('--out',default='generalization.json');a=p.parse_args()
    if a.n<1:raise ValueError('n must be positive')
    s=Session(a.checkpoint);seed=a.seed if a.seed is not None else secrets.randbits(64)
    report=evaluate(s,seed,a.n)
    report['checkpoint_sha256']=hashlib.sha256(pathlib.Path(a.checkpoint).read_bytes()).hexdigest()
    report['training_tokens']=s.report.get('training_tokens_processed')
    pathlib.Path(a.out).write_text(json.dumps(report,indent=2,ensure_ascii=False))
    print(json.dumps({k:v for k,v in report.items() if k!='examples'},indent=2))
if __name__=='__main__':main()
