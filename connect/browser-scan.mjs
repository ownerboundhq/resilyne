const ignore=new Set(['.git','node_modules','dist','build','.next','coverage','.turbo','.cache','.data','vendor','__pycache__']);
export const MAX_FILES=20000;
export const MAX_READ=160000;
const testPath=/(?:^|\/)(?:test|tests|__tests__)(?:\/|$)|\.(?:test|spec)\.[cm]?[jt]sx?$/i;
export function normalizeFiles(files){
 const list=[];let truncated=false,root=null,visited=0;
 for(const file of files){
  if(++visited>MAX_FILES){truncated=true;break;}
  const raw=file.webkitRelativePath||file.name||'';
  const parts=raw.split('/');
  if(parts.some(x=>!x||x==='.'||x==='..'||x.includes('\\')))continue;
  if(file.webkitRelativePath){if(root===null)root=parts[0];if(root!==parts[0]){truncated=true;continue;}parts.shift();}
  if(!parts.length||parts.some(x=>ignore.has(x)))continue;
  list.push({path:parts.join('/'),file});
 }
 return {list,truncated,root};
}
const item=(id,title,state,detail,action,priority='normal')=>({id,title,state,detail,action,priority});
const hasScript=(m,k)=>typeof m?.scripts?.[k]==='string'&&m.scripts[k].trim()!==''&&!/no test specified/i.test(m.scripts[k]);
export async function inspect(files,{read=async f=>f.text()}={}){
 const {list,truncated,root}=normalizeFiles(files),paths=new Set(list.map(x=>x.path)),byPath=new Map(list.map(x=>[x.path,x.file]));
 const has=re=>[...paths].some(x=>re.test(x));
 const missing=truncated?'unknown':'attention';
 let pkg=null,manifestState='missing',manifestError=false;
 if(byPath.has('package.json')){
  const f=byPath.get('package.json');
  try{if(f.size>MAX_READ)throw Error('too large');pkg=JSON.parse(await read(f));if(!pkg||typeof pkg!=='object'||Array.isArray(pkg))throw Error('invalid');manifestState='ok';}catch{manifestState='unknown';manifestError=true;}
 }
 const node=manifestState==='ok',nested=has(/\/package\.json$/),checks=[];
 const add=(...args)=>checks.push(item(...args));
 add('manifest','Project structure',node?'pass':manifestError?'unknown':missing,node?'Root Node.js manifest is readable.':manifestError?'Root manifest could not be read.':nested?'Nested Node projects found; choose the application folder for precise checks.':'No root Node.js manifest found.','Choose the application folder containing package.json.','high');
 const lock=['package-lock.json','pnpm-lock.yaml','yarn.lock','bun.lock','bun.lockb','npm-shrinkwrap.json'].filter(x=>paths.has(x));
 add('lock','Reproducible dependencies',!node?'unknown':lock.length===1?'pass':lock.length>1?'attention':missing,!node?'Node project not identified.':lock.length===1?'One root lockfile is present.':lock.length>1?'Multiple root lockfiles can cause inconsistent installs.':'No root dependency lockfile found.','Use one package manager and commit its lockfile.','high');
 const tests=has(testPath),testScript=hasScript(pkg,'test');
 add('tests','Automated test setup',!node?'unknown':tests&&testScript?'pass':missing,tests&&testScript?'Test script and conventional test files found.':'A test script and conventional test files were not both found.','Add tests for critical user journeys and a working test command.','high');
 const workflows=[...paths].filter(x=>/^\.github\/workflows\/[^/]+\.ya?ml$/i.test(x));
 add('ci','Continuous integration',workflows.length?'pass':missing,workflows.length?workflows.length+' GitHub workflow configuration file(s) found.':'No GitHub Actions workflow found in the selected files.','Set up a CI workflow that runs checks on proposed changes.','high');
 const env=[...paths].filter(x=>/(?:^|\/)\.env(?:\.(?!example$|sample$|template$)[^/]+)?$/i.test(x));
 const keys=has(/(?:^|\/)(?:id_rsa|id_ed25519|credentials\.json|service-account[^/]*\.json)$|\.(?:pem|p12|pfx|key)$/i);
 add('secrets','Potential secret-bearing files',env.length||keys?'attention':truncated?'unknown':'pass',env.length||keys?'Potentially sensitive filenames are present. Contents were not read; local ignored files may be intentional.':'No matching sensitive filenames were found in the selected files.','Check that secrets are excluded from Git and browser bundles. Rotate any exposed credential.','high');
 add('ignore','Repository exclusions',paths.has('.gitignore')?'pass':missing,paths.has('.gitignore')?'A root .gitignore is present; its rules were not evaluated.':'No root .gitignore found.','Exclude local secrets, dependency folders and generated output.','high');
 add('build','Build command',!node?'unknown':hasScript(pkg,'build')?'pass':missing,hasScript(pkg,'build')?'A build script is declared; not executed.':'No build script detected. Some server-only apps do not require one.','Document how to build or start the application.');
 add('lint','Static quality checks',!node?'unknown':hasScript(pkg,'lint')||hasScript(pkg,'typecheck')||hasScript(pkg,'check')?'pass':missing,'Checks only for declared lint, typecheck or check scripts.','Add a lint or typecheck command appropriate to the stack.');
 add('runtime','Runtime version',!node?'unknown':typeof pkg.engines?.node==='string'||paths.has('.nvmrc')||paths.has('.node-version')?'pass':missing,'Looks for a declared Node version, not its support status.','Pin a supported Node version in the project and hosting environment.');
 const docs=has(/^readme(?:\.[^/]+)?$/i);
 add('docs','Setup documentation',docs?'pass':missing,docs?'Root README present; contents not assessed.':'No root README found.','Document setup, environment variables, deployment and recovery steps.');
 add('env-template','Environment template',has(/(?:^|\/)\.env\.(?:example|sample|template)$/i)?'pass':env.length?missing:'unknown','Checks for a sample environment file, without reading its contents.','Provide placeholder-only configuration examples if your application uses environment variables.');
 const migrations=has(/(?:^|\/)(?:migrations|prisma\/migrations)\/[^/]+/i);
 const db=node&&Object.keys({...pkg.dependencies,...pkg.devDependencies}).some(x=>/^(?:pg|prisma|@prisma\/client|mysql2|sequelize|drizzle-orm|typeorm|knex|mongoose|better-sqlite3)$/.test(x));
 add('database','Database change management',migrations?'pass':db?missing:'unknown',migrations?'Migration directory detected.':db?'A database dependency was detected, but no conventional migration directory.':'Database usage could not be established.','Use versioned migrations where appropriate and test restore procedures.');
 for(const [id,title,action] of [['live-ci','Actual test results','Connect a CI provider or run the tests.'],['vulnerability','Known dependency vulnerabilities','Run your package manager’s vulnerability audit or connect repository security alerts.'],['uptime','Live application health','Configure an external uptime check.'],['backup','Verified recovery','Create backups and perform a restore test.'],['cost','Operating costs','Review actual cloud and API invoices.']])add(id,title,'unknown','Not measured by a local file inspection.',action);
 const counts=Object.fromEntries(['pass','attention','unknown'].map(s=>[s,checks.filter(c=>c.state===s).length]));
 return {version:1,generatedAt:new Date().toISOString(),project:root||'Selected files',filesExamined:list.length,truncated,counts,checks,scope:'File-structure and manifest indicators only. No source analysis, code execution, live tests or vulnerability database lookup. Passing indicators are not a security or launch certification.'};
}
