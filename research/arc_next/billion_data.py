"""Prepare an expanded, disk-backed BPE corpus from the original pinned source.
Run on your own machine. A billion processed tokens is not a billion unique tokens.
"""
import argparse, hashlib, json, pathlib, struct
from itertools import zip_longest
from prepare import clean

def sha_file(path):
    h=hashlib.sha256()
    with open(path,'rb') as f:
        for b in iter(lambda:f.read(8*1024*1024),b''):h.update(b)
    return h.hexdigest()

def main():
    from datasets import load_dataset
    import sentencepiece as spm
    p=argparse.ArgumentParser()
    p.add_argument('--original-data',required=True);p.add_argument('--tokenizer',required=True)
    p.add_argument('--out',required=True);p.add_argument('--corpus-tokens',type=int,default=1000000000)
    p.add_argument('--min-corpus-tokens',type=int,default=250000000)
    a=p.parse_args()
    if not 0<a.min_corpus_tokens<=a.corpus_tokens: p.error('Invalid corpus targets')
    old=pathlib.Path(a.original_data);out=pathlib.Path(a.out);out.mkdir(parents=True,exist_ok=True)
    if (out/'manifest.json').exists() or (out/'train.u16').exists():raise RuntimeError('Refusing to overwrite existing corpus')
    prior=json.loads((old/'provenance.json').read_text())
    for name,meta in prior['files'].items():
        if sha_file(old/name)!=meta['sha256']:raise ValueError('Original file hash mismatch '+name)
    source=next(s for s in prior['sources'] if s['dataset']=='HuggingFaceTB/cosmopedia')
    sp=spm.SentencePieceProcessor(model_file=a.tokenizer)
    if sp.vocab_size()!=4096:raise ValueError('Wrong Arc Next tokenizer')
    seen=set()
    for name in ('pretrain.jsonl','pretrain_val.jsonl'):
        with (old/name).open(encoding='utf-8') as f:
            for line in f:seen.add(hashlib.sha256(json.loads(line)['text'].encode()).digest())
    names=('web_samples_v2','openstax','stanford')
    streams=[iter(load_dataset(source['dataset'],n,split='train',streaming=True,revision=source['revision'])) for n in names]
    total=0;docs=0;skipped=0;by_source={n:0 for n in names};bufpath=out/'train.u16.partial'
    with bufpath.open('wb') as f:
        for group in zip_longest(*streams):
            for name,row in zip(names,group):
                if row is None:continue
                text=clean(row['text'])[:12000]
                if len(text)<100:continue
                digest=hashlib.sha256(text.encode()).digest()
                # Exclude exact duplicates, original documents, and the original hash-based holdout partition.
                if digest in seen or int.from_bytes(digest[:4],'big')%40==0:skipped+=1;continue
                seen.add(digest)
                ids=sp.encode(text)+[sp.eos_id()]
                ids=ids[:a.corpus_tokens-total]
                if ids:ids[-1]=sp.eos_id()
                if not ids:break
                f.write(struct.pack('<'+'H'*len(ids),*ids));total+=len(ids);docs+=1;by_source[name]+=len(ids)
                if docs%10000==0:print('Corpus tokens',total,'documents',docs,flush=True)
                if total>=a.corpus_tokens:break
            if total>=a.corpus_tokens:break
    if total<a.min_corpus_tokens:raise RuntimeError(f'Source exhausted at {total} tokens; minimum not reached. No training corpus published.')
    manifest={'format':'arc-next-u16le-v1','source':source,'subsets':names,'tokenizer_sha256':sha_file(a.tokenizer),'original_provenance_sha256':sha_file(old/'provenance.json'),'token_positions':total,'requested_corpus_tokens':a.corpus_tokens,'documents':docs,'skipped_exact_duplicates_or_holdout':skipped,'source_token_positions':by_source,'sha256':sha_file(bufpath),'file':'train.u16','note':'Expanded synthetic educational text, exact-deduplicated after cleaning. No guarantee of unique ideas, correctness, safety, or rights clearance. Original held-out documents excluded by hash; near duplicates are possible.'}
    bufpath.rename(out/'train.u16')
    tmp=out/'manifest.tmp';tmp.write_text(json.dumps(manifest,indent=2));tmp.replace(out/'manifest.json')
    print(json.dumps(manifest),flush=True)
if __name__=='__main__':main()
