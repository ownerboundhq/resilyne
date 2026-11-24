import test from 'node:test';
import assert from 'node:assert/strict';
import {randomUUID} from 'node:crypto';
test('database persistence, deduplication, account budget and project scope',{skip:process.env.RESILYNE_DB_TEST!=='true'},async()=>{
 const {poolFor,tx,one,enqueue,incident,dailyRepair}=await import('../saas/db.mjs');
 const pool=poolFor({db:process.env.DATABASE_URL}),account=String(Date.now()),other=String(Date.now()+1),p=randomUUID(),q=randomUUID();
 try{
   await pool.query('INSERT INTO accounts(id,login) VALUES($1,$2),($3,$4)',[account,'test-owner',other,'other-owner']);
   await pool.query('INSERT INTO projects(id,account_id,installation_id,repository_id,repo,base_branch,workflow_id) VALUES($1,$2,1,1,$3,$4,1),($5,$6,2,2,$7,$4,2)',[p,account,'test/repo','main',q,other,'other/repo']);
   assert.equal(await one(pool,'SELECT id FROM projects WHERE id=$1 AND account_id=$2',[p,other]),undefined);
   const i=await incident(pool,p,'test','ci','Test',{x:1}),same=await incident(pool,p,'test','ci','Updated',{x:2});
   assert.equal(i.id,same.id);assert.equal(same.title,'Updated');
   assert.ok(await enqueue(pool,p,'scan','test:'+p));assert.equal(await enqueue(pool,p,'scan','test:'+p),undefined);
   await tx(pool,async c=>{await one(c,'SELECT id FROM accounts WHERE id=$1 FOR UPDATE',[account]);await dailyRepair(c,{id:p,account_id:account},i.id,'src/a.ts',1);});
   await assert.rejects(tx(pool,async c=>{await one(c,'SELECT id FROM accounts WHERE id=$1 FOR UPDATE',[account]);await dailyRepair(c,{id:p,account_id:account},i.id,'src/b.ts',1);}),/budget/);
 }finally{await pool.query('DELETE FROM accounts WHERE id=ANY($1::bigint[])',[[account,other]]);await pool.end();}
});
