export const MAX_ATTEMPTS=2;
export function canDraft(project,incident,patch){
 return project.enabled&&project.auto_propose&&project.auto_draft===true&&incident.kind==='ci'&&patch.decision==='repair'&&(patch.attempt||1)<=MAX_ATTEMPTS;
}
export function retryEligible(project,patch,verification){
 return project.enabled&&project.auto_propose&&project.auto_draft===true&&patch.engine===true&&patch.autoDraft===true&&(patch.attempt||1)<MAX_ATTEMPTS&&verification.exact===true&&verification.conclusion==='failure';
}
export function exactRun(pr,run,workflow,repo,base){
 return !!(pr&&run&&pr.state==='open'&&pr.base?.ref===base&&pr.base?.repo?.full_name===repo&&pr.head?.repo?.full_name===repo&&run.head_repository?.full_name===repo&&run.head_branch===pr.head.ref&&run.head_sha===pr.head.sha&&String(run.workflow_id)===String(workflow)&&['push','pull_request'].includes(run.event)&&run.status==='completed');
}
