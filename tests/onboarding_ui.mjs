// Run from the repository root. See docs/ONBOARDING_DEMO_REVIEW.md for the optional DOM dependency.
import fs from 'node:fs';
import assert from 'node:assert/strict';
import {createRequire} from 'node:module';
import path from 'node:path';
import vm from 'node:vm';
const {parseHTML}=createRequire(path.resolve(process.argv[2] || 'tmp/onboarding-ui-test', 'package.json'))('linkedom');
import {mountOnboarding} from '../frontend/public/onboarding.js';
const data=JSON.parse(fs.readFileSync('frontend/data/onboarding.json','utf8'));
const dom=parseHTML('<html><body><main id="root"></main></body></html>');
Object.assign(globalThis,{document:dom.document,Node:dom.Node,HTMLElement:dom.HTMLElement});
dom.HTMLElement.prototype.scrollIntoView=function(){};
// Linkedom has no writable select.value; emulate native selection for event tests.
Object.defineProperty(dom.HTMLSelectElement.prototype,'value',{get(){return this.querySelector('option[selected]')?.value || this.querySelector('option')?.value || '';},set(v){this.querySelectorAll('option').forEach(o=>o.toggleAttribute('selected',o.value===v));}});
globalThis.history={replaceState(_a,_b,url){globalThis.location=new URL(url);}};
const blobs=[];URL.createObjectURL=b=>{blobs.push(b);return 'blob:test';};URL.revokeObjectURL=()=>{};
const root=document.getElementById('root');
function mount(key,stage,standalone=false){globalThis.location=new URL(`http://localhost/?dataset=${key}&stage=${stage}`);mountOnboarding(data,root,{standalone});}
function button(text){const b=[...root.querySelectorAll('button')].find(x=>x.textContent===text);assert.ok(b,`Missing button ${text}`);b.click();}
function choose(label,value){const el=[...root.querySelectorAll('label')].find(l=>l.firstElementChild.textContent===label)?.querySelector('select');assert.ok(el,label);el.value=value;el.dispatchEvent(new dom.Event('change'));}
let renders=0, attempts=0, claims=0;
for(const source of data.sources){
 for(let stage=1;stage<=7;stage++){
  mount(source.key,stage);assert.equal(root.querySelectorAll('.ob-stage-button').length,7);assert.equal(root.querySelector('[aria-current]').textContent.slice(0,2),String(stage).padStart(2,'0'));renders++;
  assert.ok(root.textContent.includes('Recorded replay'));
  // Optional children must not create literal null text nodes.
  const walk=document.createTreeWalker(root,4);while(walk.nextNode())assert.notEqual(walk.currentNode.textContent,'null');
 }
 mount(source.key,1);button('Next rows');assert.ok(root.textContent.includes('Sample 11–20'));
 for(let n=0;n<3;n++)button('Next rows');assert.ok(root.textContent.includes('Sample 41–50'));
 assert.ok([...root.querySelectorAll('button')].find(b=>b.textContent==='Next rows').disabled);
 choose('Columns to inspect',source.plan.groups[0].name);assert.equal(root.querySelectorAll('thead th').length,source.plan.groups[0].columns.length+1);
 button('Next stage →');assert.ok(root.querySelector('h2').textContent.includes('Inspect'));
 button('← Previous stage');assert.equal(root.querySelector('h2').textContent,'Dataset arrives');
 mount(source.key,3);root.querySelector('.ob-graph-node').dispatchEvent(new dom.Event('click'));assert.ok(root.querySelector('.ob-inspector').textContent.includes('Implicit business'));
 mount(source.key,4);
 for(const owner of new Set([...source.available_concepts,...source.concepts].map(c=>c.owner))){choose('Owning entity',owner);const graph=root.querySelector('.ob-graph-node');assert.ok(graph);graph.dispatchEvent(new dom.Event('click'));assert.ok(root.querySelector('.ob-inspector h4').textContent);}
 const search=root.querySelector('input');search.value='no-such-concept-xyz';search.dispatchEvent(new dom.Event('input'));assert.ok(root.textContent.includes('No concepts match'));
 mount(source.key,5);
 for(const group of source.history){choose('Mapping group',group.name);for(let n=0;n<group.attempts.length;n++){root.querySelectorAll('.ob-attempt')[n].click();assert.equal(root.querySelectorAll('.ob-attempt[aria-pressed="true"]').length,1);attempts++;}}
 mount(source.key,6);
 for(const kind of new Set(source.review_queue.map(i=>i.kind))){choose('Contract type',kind);let next;while(next=[...root.querySelectorAll('button')].find(b=>b.textContent.startsWith('Show next ')))next.click();}
 button('Download blank review CSV');const csv=await blobs.at(-1).text();assert.equal(csv.split('\r\n').length,source.review_queue.length+1);assert.ok(csv.split('\r\n').slice(1).every(line=>line.endsWith(',"","","",""')));
 mount(source.key,7);
 for(let n=0;n<source.examples.length;n++){choose('Source-record example',String(n));const buttons=[...root.querySelectorAll('.ob-fact-link')];for(const b of buttons){b.click();assert.ok(root.querySelector('.ob-inspector h4').textContent.startsWith('Provenance:'));claims++;}}
 button('Restart replay');assert.equal(root.querySelector('h2').textContent,'Dataset arrives');
 button('Download evidence');assert.equal(JSON.parse(await blobs.at(-1).text()).source_id,source.source_id);
 choose('Replay a dataset',source.key==='ip'?'acnc':'ip');assert.equal(root.querySelector('h2').textContent,'Dataset arrives');
}
for(const stage of ['bad','1.5','0','99']){mount('missing',stage);assert.ok(root.querySelector('h2'));}
mount('wgea',7,true);assert.equal(root.querySelectorAll('a[href*="profiles"]').length,0);
const offlineHTML=fs.readFileSync('reports/dataset-onboarding.html','utf8');
const offline=parseHTML(offlineHTML);
const scripts=[...offline.document.querySelectorAll('script')];
const code=scripts.find(s=>!s.type).textContent;
vm.runInNewContext(code,{document:offline.document,Node:offline.Node,Intl,URL,URLSearchParams,Blob,setTimeout,location:new URL('file:///dataset-onboarding.html?dataset=wgea&stage=7'),history:{replaceState(){throw new Error('file history restricted');}}});
assert.equal(offline.document.querySelectorAll('.ob-stage-button').length,7);
assert.equal(offline.document.querySelector('h2').textContent,'Profile impact');
assert.equal(offline.document.querySelectorAll('a[href*="profiles"]').length,0);
console.log(JSON.stringify({status:'pass',renders,attempts,claims,downloads:blobs.length}));
