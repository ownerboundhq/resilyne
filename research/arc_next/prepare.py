"""Prepare a bounded, provenance-recorded corpus. No downloaded model weights."""
import argparse, hashlib, json, pathlib, random, re
from itertools import islice
def sha(s): return hashlib.sha256(s.encode()).hexdigest()
def write_jsonl(path,rows):
    path.write_text(''.join(json.dumps(x,ensure_ascii=False)+'\n' for x in rows),encoding='utf-8')
def clean(s):
    s=s.strip().replace('\x00','')
    s=re.sub(r'[\w.+-]+@[\w.-]+\.[A-Za-z]{2,}', '[redacted email]',s)
    s=re.sub(r'(?<!\w)(?:\+?\d[\d ()-]{8,}\d)(?!\w)', '[redacted number]',s)
    for word in ('<user>','<assistant>','<end>'):s=s.replace(word,'')
    return s
def main():
    from datasets import load_dataset
    from huggingface_hub import HfApi
    ap=argparse.ArgumentParser();ap.add_argument('--out',default='research/arc_next/data');ap.add_argument('--docs',type=int,default=10000);ap.add_argument('--cosmo-revision');ap.add_argument('--oasst-revision');args=ap.parse_args()
    p=pathlib.Path(args.out);p.mkdir(parents=True,exist_ok=True)
    api=HfApi();cosmo='HuggingFaceTB/cosmopedia';oasst='OpenAssistant/oasst1'
    cr=args.cosmo_revision or api.dataset_info(cosmo).sha; ar=args.oasst_revision or api.dataset_info(oasst).sha
    train=[];val=[];seen=set()
    for cfg in ('web_samples_v2','openstax','stanford'):
        stream=load_dataset(cosmo,cfg,split='train',streaming=True,revision=cr)
        for row in islice(stream, max(1,args.docs//3)):
            text=clean(row['text'])[:12000]
            if len(text)<100:continue
            digest=sha(text)
            if digest in seen:continue
            seen.add(digest)
            (val if int(digest[:8],16)%40==0 else train).append({'text':text,'source':cfg})
        print('Pretraining documents',len(train),len(val),flush=True)
    if len(train)<100 or len(val)<5:raise RuntimeError('Insufficient pretraining data')
    random.Random(42).shuffle(train);write_jsonl(p/'pretrain.jsonl',train);write_jsonl(p/'pretrain_val.jsonl',val)
    def eligible(r):
        if r.get('lang')!='en' or r.get('deleted') or r.get('review_result') is False or r.get('synthetic'):return False
        labels=r.get('labels') or {}
        if 'name' in labels and 'value' in labels:labels=dict(zip(labels['name'],labels['value']))
        for k in ('pii','spam','not_appropriate','hate_speech','sexual_content','toxicity','violence'):
            v=labels.get(k)
            if isinstance(v,dict):v=v.get('value')
            if isinstance(v,(int,float)) and v>=.5:return False
        return True
    pair_seen=set();tree_sets={}
    for split,filename in [('train','chat.jsonl'),('validation','chat_val.jsonl')]:
        rows=list(load_dataset(oasst,split=split,revision=ar))
        lookup={r['message_id']:r for r in rows}
        pairs=[];tree_sets[split]=set()
        for r in rows:
            if r['role']!='assistant' or r.get('rank') not in (0,None) or not eligible(r):continue
            chain=[];cur=r
            for _ in range(7):
                if not cur or not eligible(cur):break
                chain.append(cur);cur=lookup.get(cur.get('parent_id'))
            chain.reverse()
            if chain and chain[0]['role']=='assistant':chain=chain[1:]
            if len(chain)<2 or any(x['role']!=('prompter' if i%2==0 else 'assistant') for i,x in enumerate(chain)):continue
            turns=[clean(x['text'])[:2500] for x in chain]
            if any(not t for t in turns):continue
            key=sha(turns[-2].lower().strip())
            if key in pair_seen:continue
            pair_seen.add(key);tree_sets[split].add(r['message_tree_id'])
            pairs.append({'turns':turns[:-1],'answer':turns[-1]})
        if len(pairs)<(100 if split=='train' else 20):raise RuntimeError('Insufficient human conversation data '+split)
        random.Random(42).shuffle(pairs);write_jsonl(p/filename,pairs);print(split,len(pairs),flush=True)
    if tree_sets['train'] & tree_sets['validation']:raise RuntimeError('Conversation tree leakage')
    report={'sources':[{'dataset':cosmo,'revision':cr,'license':'Apache-2.0','note':'Synthetic text generated with Mixtral; no Mixtral weights loaded.'},{'dataset':oasst,'revision':ar,'license':'Apache-2.0','note':'Filtered human messages; basic automated filtering is not a complete safety or privacy review.'}],'files':{f.name:{'sha256':hashlib.sha256(f.read_bytes()).hexdigest(),'rows':sum(1 for _ in f.open())} for f in p.glob('*.jsonl')}}
    (p/'provenance.json').write_text(json.dumps(report,indent=2));print(json.dumps(report),flush=True)
if __name__=='__main__':main()
