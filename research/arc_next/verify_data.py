"""Verify an already reconstructed corpus without downloading it again."""
import argparse, hashlib, json, pathlib
def main():
    p=argparse.ArgumentParser()
    p.add_argument('original_provenance')
    p.add_argument('data')
    a=p.parse_args()
    root=pathlib.Path(a.data)
    prior=json.loads(pathlib.Path(a.original_provenance).read_text(encoding='utf-8'))
    for name,meta in prior['files'].items():
        f=root/name
        digest=hashlib.sha256(f.read_bytes()).hexdigest()
        with f.open(encoding='utf-8') as inp:
            rows=sum(1 for _ in inp)
        if digest!=meta['sha256'] or rows!=meta['rows']:
            raise RuntimeError(f'Corpus mismatch: {name}; do not resume training')
        print(f'{name}: {rows} rows, SHA256 verified',flush=True)
    if {f.name for f in root.glob('*.jsonl')}!=set(prior['files']):
        raise RuntimeError('Unexpected JSONL files in corpus directory')
    tmp=root/'provenance.tmp'
    tmp.write_bytes(pathlib.Path(a.original_provenance).read_bytes())
    tmp.replace(root/'provenance.json')
    print('Exact corpus hashes and row counts verified.',flush=True)
if __name__=='__main__':main()
