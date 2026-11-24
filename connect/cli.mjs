import {localScan} from './scan.mjs';
const command=process.argv[2]||'scan';
if(command!=='scan'){console.error('Usage: npm run scan -- [scan]');process.exitCode=1;}
else try{console.log(JSON.stringify(await localScan(process.env.RESILYNE_PROJECT_ROOT||process.cwd()),null,2));}catch(e){console.error('Scan failed: '+e.message);process.exitCode=1;}
