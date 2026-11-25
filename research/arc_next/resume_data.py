"""Recreate the exact source corpus recorded in the prior run before resuming."""
import json, pathlib, subprocess, sys
prior=pathlib.Path(sys.argv[1])
out=pathlib.Path(sys.argv[2])
provenance=json.loads(prior.read_text())
sources={s['dataset']:s['revision'] for s in provenance['sources']}
subprocess.run([sys.executable,str(pathlib.Path(__file__).with_name('prepare.py')),'--out',str(out),'--docs','10000','--cosmo-revision',sources['HuggingFaceTB/cosmopedia'],'--oasst-revision',sources['OpenAssistant/oasst1']],check=True)
actual=json.loads((out/'provenance.json').read_text())
if actual!=provenance:raise RuntimeError('Corpus changed; refusing to resume with different training data.')
print('Exact source revisions and corpus hashes verified.',flush=True)
