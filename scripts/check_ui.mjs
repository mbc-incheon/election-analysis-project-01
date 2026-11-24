// Execute the actual page script with an in-memory DOM to check review controls.
// This checks logic; it is not a rendered-browser or accessibility certification.
import fs from 'node:fs';
import path from 'node:path';
import vm from 'node:vm';
import assert from 'node:assert/strict';
import {fileURLToPath} from 'node:url';
const root=path.resolve(path.dirname(fileURLToPath(import.meta.url)),'..');
const html=fs.readFileSync(path.join(root,'election-news-server/index.html'),'utf8');
const script=html.match(/<script>([\s\S]*?)<\/script>/)[1];
const elements=new Map();
const element=id=>{
  if(!elements.has(id)) elements.set(id,{value:'',checked:false,disabled:false,options:[],listeners:{},style:{},addEventListener(event,fn){this.listeners[event]=fn;},appendChild(){}});
  return elements.get(id);
};
const sandbox={document:{getElementById:element,createElement:()=>({})},location:{protocol:'http:',host:'127.0.0.1:8102'},WebSocket:class{},setTimeout(){},URLSearchParams,URL,Blob,console};
vm.createContext(sandbox);
vm.runInContext(script,sandbox);
const checks=[];
function check(name,code){vm.runInContext(code,sandbox);checks.push({name,passed:true});}
sandbox.assert=assert;
check('New article requires explicit manual review', `
  const a={id:'UI-1',title:'TEST',author:'TEST-writer',mode:'demo',sentences:[],status:'PENDING_HUMAN',validation:{rule:'PASS',disagreement:false},ai_review:{verdict:'UNAVAILABLE'}};
  show(a); assert.equal($('approve').disabled,true);
  $('checked').checked=true; $('aiAck').checked=true; $('reason').value='근거 직접 확인'; syncApproval();
  assert.equal($('approve').disabled,false);
`);
check('Rule failure cannot enable approval', `
  current.validation.rule='FAIL'; syncApproval(); assert.equal($('approve').disabled,true);
  current.validation.rule='PASS'; current.validation.disagreement=true; syncApproval(); assert.equal($('approve').disabled,true);
`);
check('Switching article clears confirmations', `
  show({...a,id:'UI-2'}); assert.equal($('checked').checked,false); assert.equal($('aiAck').checked,false); assert.equal($('reason').value,'');
`);
check('Changing user token clears confirmations', `
  $('checked').checked=true; $('aiAck').checked=true; $('reason').value='근거 직접 확인'; $('token').listeners.input();
  assert.equal($('checked').checked,false); assert.equal($('approve').disabled,true);
`);
check('Unavailable values are never printed as zero or null', `
  assert.equal(showValue(null,'%'),'미제공'); assert.equal(showValue(0,'%'),'0%');
`);
fs.mkdirSync(path.join(root,'outputs'),{recursive:true});
fs.writeFileSync(path.join(root,'outputs/ui_logic_results.json'),JSON.stringify({at:new Date().toISOString(),method:'Node VM with DOM stubs; no rendered browser',total:checks.length,passed:checks.length,checks},null,2));
console.log(`${checks.length} UI logic checks passed`);
