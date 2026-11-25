import base64,hashlib,json,pathlib,sys,torch
source=pathlib.Path(sys.argv[1]);out=pathlib.Path(sys.argv[2]);out.parent.mkdir(parents=True,exist_ok=True)
weights=torch.load(source/'weights.pt',map_location='cpu',weights_only=True)
vocab=json.loads((source/'vocab.json').read_text());report=json.loads((source/'report.json').read_text())
assert len(vocab)==215 and sum(t.numel() for t in weights.values())==102871
obj={'format':'neuravale.n0.f32le.v1','model':'Neuravale N0 Chat 003','checkpoint_sha256':hashlib.sha256((source/'weights.pt').read_bytes()).hexdigest(),'vocab':vocab,'development_score':{'correct':report['test']['correct'],'total':report['test']['total']},'tensors':{k:{'shape':list(t.shape),'data':base64.b64encode(t.detach().contiguous().numpy().astype('<f4').tobytes()).decode()} for k,t in weights.items()}}
out.write_text(json.dumps(obj,separators=(',',':')))
print(out, out.stat().st_size, obj['checkpoint_sha256'], obj['development_score'])
