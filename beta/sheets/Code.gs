// Resilyne 1.0 private Sheets beta. Read-only external checks.
function onOpen() {
  SpreadsheetApp.getUi().createMenu('Resilyne')
    .addItem('Start monitoring','startMonitoring')
    .addItem('Run checks now','runChecks')
    .addItem('Stop monitoring','stopMonitoring').addToUi();
}
function boundWorkbook_() {
  var ss=SpreadsheetApp.getActiveSpreadsheet();
  if(!ss||!ss.getSheetByName('Control')||!ss.getSheetByName('Applications')||!ss.getSheetByName('Events'))throw new Error('Open the Resilyne Live Beta workbook.');
  return ss;
}
function startMonitoring() {
  var ss=boundWorkbook_(),lock=LockService.getScriptLock();
  lock.waitLock(10000);
  try{
    PropertiesService.getScriptProperties().setProperty('WORKBOOK_ID',ss.getId());
    ScriptApp.getProjectTriggers().filter(function(t){return t.getHandlerFunction()==='runChecks';}).forEach(function(t){ScriptApp.deleteTrigger(t);});
    ScriptApp.newTrigger('runChecks').timeBased().everyMinutes(5).create();
    ss.getSheetByName('Control').getRange('B5:B6').setValues([[true],['Trigger installed']]);
  }finally{lock.releaseLock();}
  runChecks();
}
function stopMonitoring(){
  var ss=boundWorkbook_(),lock=LockService.getScriptLock();
  lock.waitLock(10000);
  try{
    ss.getSheetByName('Control').getRange('B5:B6').setValues([[false],['Stopped — last readings retained']]);
    ScriptApp.getProjectTriggers().filter(function(t){return t.getHandlerFunction()==='runChecks';}).forEach(function(t){ScriptApp.deleteTrigger(t);});
  }finally{lock.releaseLock();}
}
function validHealthUrl_(v){
  // Only owner-selected HTTPS endpoints on ordinary public DNS names. No redirects,
  // credentials, query strings, IP literals, custom ports or private-name suffixes.
  var s=String(v||'').trim();
  var m=s.match(/^https:\/\/([a-z0-9.-]+)(\/[a-z0-9._~!$&'()*+,;=:@%\/-]*)?$/i);
  if(!m||s.length>500)return null;
  var host=m[1].toLowerCase();
  if(!/^(?:[a-z0-9](?:[a-z0-9-]{0,61}[a-z0-9])?\.)+[a-z]{2,63}$/.test(host)||/\.(?:local|internal|localhost|test|invalid|example|onion|lan|home|corp)$/.test(host))return null;
  return s;
}
function validRepo_(v){var s=String(v||'').trim();return /^[a-z0-9][a-z0-9-]{0,38}\/[a-z0-9_.-]{1,100}$/i.test(s)&&!s.endsWith('/.')&&!s.endsWith('/..')?s:null;}
function transition_(previous,failures,successes,ok){
  failures=Math.max(0,Number(failures)||0);successes=Math.max(0,Number(successes)||0);
  if(ok){successes++;return {state:previous==='DOWN'&&successes<2?'DOWN':'UP',failures:0,successes:Math.min(successes,2)};}
  failures++;return {state:previous==='DOWN'||failures>=2?'DOWN':'SUSPECT',failures:Math.min(failures,2),successes:0};
}
function safeText_(s){return "'"+String(s||'').slice(0,500);}
function probe_(url){
  if(!url)return {valid:false,ok:false,status:'',ms:'',issue:'Enter a valid public HTTPS URL'};
  var start=Date.now();
  try{
    var r=UrlFetchApp.fetch(url,{method:'get',followRedirects:false,muteHttpExceptions:true,validateHttpsCertificates:true});
    var status=r.getResponseCode();
    return {valid:true,ok:status>=200&&status<300,status:status,ms:Date.now()-start,issue:status>=200&&status<300?'':'HTTP '+status};
  }catch(e){return {valid:true,ok:false,status:'',ms:Date.now()-start,issue:'Network request failed'};}
}
function github_(path,token){
  try{
    var headers={'Accept':'application/vnd.github+json','X-GitHub-Api-Version':'2022-11-28'};
    if(token)headers.Authorization='Bearer '+token;
    var r=UrlFetchApp.fetch('https://api.github.com/repos/'+path,{headers:headers,followRedirects:false,muteHttpExceptions:true,validateHttpsCertificates:true});
    if(r.getResponseCode()!==200)return null;
    return JSON.parse(r.getContentText());
  }catch(e){return null;}
}
function signals_(repo,token){
  var result={ci:'NOT ASSESSED',alerts:'',coverage:'NOT ASSESSED'};
  if(!repo)return result;
  // Check one most recent workflow run, not the health of every workflow.
  var ci=github_(repo+'/actions/runs?per_page=1',token);
  var run=ci&&ci.workflow_runs&&ci.workflow_runs[0];
  if(run)result.ci=String(run.conclusion||run.status||'UNKNOWN').toUpperCase().replace(/[^A-Z_]/g,'').slice(0,40)||'UNKNOWN';
  // No credential means unknown, never zero alerts.
  if(token){
    var a=github_(repo+'/dependabot/alerts?state=open&per_page=100',token);
    if(Array.isArray(a)){result.alerts=a.length;result.coverage=a.length===100?'PARTIAL (100+)':'DEPENDABOT ONLY';}
  }
  return result;
}
function runChecks(){
  var lock=LockService.getScriptLock();if(!lock.tryLock(1000))return;
  var control;
  try{
    var props=PropertiesService.getScriptProperties(),id=props.getProperty('WORKBOOK_ID');
    if(!id)throw new Error('Use Start monitoring first.');
    var ss=SpreadsheetApp.openById(id),apps=ss.getSheetByName('Applications'),events=ss.getSheetByName('Events');
    control=ss.getSheetByName('Control');
    if(control.getRange('B5').getValue()!==true){control.getRange('B6').setValue('Paused — last readings retained');return;}
    var rows=apps.getRange('A4:N8').getValues(),token=props.getProperty('GITHUB_READ_TOKEN')||'',log=[],now=new Date().toISOString();
    var active=0;
    rows.forEach(function(row,i){
      var name=String(row[0]||'').trim(),url=validHealthUrl_(row[1]),repo=validRepo_(row[2]),enabled=row[3]===true;
      if(!name||!enabled){apps.getRange(i+4,5,1,10).setValues([[name?'PAUSED':'NOT ASSESSED','','','','','NOT ASSESSED','','NOT ASSESSED','','']]);props.deleteProperty('IDENTITY_'+i);return;}
      active++;
      // Reset prior observations if a row is repurposed.
      var identity=JSON.stringify([name,url,repo]),old=props.getProperty('IDENTITY_'+i)===identity?row.slice(4):[];
      var p=probe_(url),next=p.valid?transition_(old[0],old[4],old[8],p.ok):{state:'NOT ASSESSED',failures:0,successes:0};
      var g=signals_(repo,token);
      function event(signal,state,detail){log.push([now,safeText_(name),signal,state,safeText_(detail)]);}
      if(old[0]!==next.state)event('HTTP',next.state,p.issue||'Endpoint responded successfully');
      if(old[5]!==g.ci)event('CI',g.ci,'Latest observed GitHub workflow result; not all workflows');
      if(old[7]!==g.coverage||old[6]!==g.alerts)event('SECURITY',g.coverage,g.alerts===''?'Alerts not assessed':g.alerts+' open alerts observed');
      apps.getRange(i+4,5,1,10).setValues([[next.state,p.status,p.ms,now,next.failures,g.ci,g.alerts,g.coverage,next.successes,p.issue]]);
      props.setProperty('IDENTITY_'+i,identity);
    });
    if(log.length){
      var start=Math.max(4,events.getLastRow()+1),needed=start+log.length-1;
      if(needed>events.getMaxRows())events.insertRowsAfter(events.getMaxRows(),needed-events.getMaxRows());
      events.getRange(start,1,log.length,5).setValues(log);
    }
    control.getRange('B6:B7').setValues([['Last cycle completed — '+active+' enabled app(s)'],[now]]);
  }catch(e){if(control)control.getRange('B6').setValue('Cycle error — check Apps Script executions');throw e;}
  finally{lock.releaseLock();}
}
