import { createHash } from 'node:crypto';

export function repoName(value) {
  if (!/^[A-Za-z0-9_.-]+\/[A-Za-z0-9_.-]+$/.test(value || '') || value.split('/').some(x => x === '.' || x === '..')) throw Error('Set GITHUB_REPO to owner/repository');
  return value;
}
export function sourcePath(value) {
  if (typeof value !== 'string' || value.length > 240 || !/^(?:src|app|pages|lib|components|server|routes|utils)\/(?:[A-Za-z0-9_-]+\/)*[A-Za-z0-9_-]+(?:\.[A-Za-z0-9_-]+)*\.(?:js|jsx|ts|tsx|mjs|cjs)$/.test(value) || /(?:^|\/)(?:secrets?|credentials?|tokens?|auth|config|env)(?:[./_-]|$)/i.test(value)) throw Error('Choose an ordinary JavaScript/TypeScript source file in a supported source folder');
  return value;
}
export function gitPath(path) { return path.split('/').map(encodeURIComponent).join('/'); }
export function incidentId(kind, key) { return createHash('sha256').update(kind+':'+key).digest('hex').slice(0,20); }
export function upsertIncident(state, kind, key, fields, at = new Date().toISOString()) {
  const id = incidentId(kind,key);
  const previous = state.incidents.find(x=>x.id===id);
  if (previous) { Object.assign(previous, fields, {lastSeen:at}); return previous; }
  const item = {id,kind,status:'open',firstSeen:at,lastSeen:at,...fields};
  state.incidents.unshift(item);
  return item;
}
export function validateProposal(result, original) {
  if (!result || typeof result.summary!=='string' || typeof result.replacement!=='string' || result.summary.length>2000 || !result.summary.trim() || !result.replacement.trim() || result.replacement===original || Buffer.byteLength(result.replacement)>60000) throw Error('Invalid or unchanged repair proposal');
  return {summary:result.summary,replacement:result.replacement};
}
export function assertFresh(expected, actual) {
  if (expected !== actual) throw Error('Repository changed since proposal. Generate a fresh proposal.');
}
