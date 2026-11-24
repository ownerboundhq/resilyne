import {readFile} from 'node:fs/promises';
import pg from 'pg';
if(!process.env.DATABASE_URL)throw Error('DATABASE_URL is required');
const pool=new pg.Pool({connectionString:process.env.DATABASE_URL});
try{await pool.query(await readFile(new URL('./schema.sql',import.meta.url),'utf8'));console.log('Schema ready');}finally{await pool.end();}
