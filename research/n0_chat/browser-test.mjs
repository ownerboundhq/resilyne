import fs from 'node:fs';import {createModel} from '../../docs/n0-engine.mjs';
const model=createModel(JSON.parse(fs.readFileSync('docs/n0-model.json','utf8')));
const report=JSON.parse(fs.readFileSync('research/n0_chat/report.json','utf8'));
let matches=0;for(const row of report.test.examples){const actual=model.generate(row.turns);if(actual===row.actual)matches++;}
console.log('Browser engine matches Python generated answers:',matches,'/',report.test.examples.length);
if(matches!==report.test.examples.length)process.exitCode=1;
