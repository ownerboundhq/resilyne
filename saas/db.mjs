import pg from 'pg';
import {randomUUID} from 'node:crypto';
export const poolFor=cfg=>new pg.Pool({connectionString:cfg.db,max:10});
export async function tx(pool,fn){const c=await pool.connect();try{await c.query('BEGIN');const result=await fn(c);await c.query('COMMIT');return result;}catch(e){await c.query('ROLLBACK');throw e;}finally{c.release();}}
export async function one(db,sql,args=[]){return (await db.query(sql,args)).rows[0];}
export async function enqueue(db,project,kind,dedupe,payload={}){
 return one(db,'INSERT INTO jobs(id,project_id,kind,dedupe,payload) VALUES($1,$2,$3,$4,$5) ON CONFLICT(dedupe) DO NOTHING RETURNING id',[randomUUID(),project,kind,dedupe,payload]);
}
export async function audit(db,account,project,action,detail={}){await db.query('INSERT INTO audit(account_id,project_id,action,detail) VALUES($1,$2,$3,$4)',[account,project,action,detail]);}
export async function incident(db,project,fingerprint,kind,title,evidence){
 return one(db,"INSERT INTO incidents(id,project_id,fingerprint,kind,title,evidence) VALUES($1,$2,$3,$4,$5,$6) ON CONFLICT(project_id,fingerprint) DO UPDATE SET last_seen=now(),status='open',title=excluded.title,evidence=excluded.evidence RETURNING *",[randomUUID(),project,fingerprint,kind,title,evidence]);
}
export async function dailyRepair(db,project,incidentId,path,limit,automatic=false){
 // Caller holds account row lock; this makes the budget atomic across projects.
 const count=await one(db,"SELECT count(*)::int AS n FROM jobs j JOIN projects p ON p.id=j.project_id WHERE p.account_id=$1 AND j.kind='propose' AND j.created_at>=date_trunc('day',now())",[project.account_id]);
 if(count.n>=limit)throw Error('Daily repair budget exhausted');
 return enqueue(db,project.id,'propose','propose:'+project.id+':'+incidentId+':'+(path||'auto')+':'+new Date().toISOString().slice(0,10),{incidentId,path,automatic});
}
