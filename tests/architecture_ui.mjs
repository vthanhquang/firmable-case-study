// Optional DOM dependency: npm install --prefix tmp/onboarding-ui-test --no-save --package-lock=false linkedom@0.18.15
import assert from 'node:assert/strict';
import fs from 'node:fs';
import path from 'node:path';
import {createRequire} from 'node:module';
import {architectureLanes,architectureSvg,architectureView} from '../frontend/public/architecture.js';
const {parseHTML}=createRequire(path.resolve('tmp/onboarding-ui-test/package.json'))('linkedom');
const {document}=parseHTML('<html><body><main></main></body></html>');
globalThis.document=document;
const core=JSON.parse(fs.readFileSync('frontend/data/raw-demo.json','utf8'));
const onboarding=JSON.parse(fs.readFileSync('frontend/data/onboarding.json','utf8'));
const el=(tag,cls,...children)=>{const node=document.createElement(tag);if(cls)node.className=cls;node.append(...children.filter(x=>x!=null));return node;};
const ui={el,copy:text=>el('p','detail-copy',text),siteLink:(label,part)=>{const a=el('a','source-link',label);a.href='/?part='+part;return a;}};
const root=document.querySelector('main');
architectureView(core,root,ui,onboarding);
assert.equal(architectureLanes(core).length,6);
assert.equal(root.querySelectorAll('.architecture-graphic svg a').length,30);
assert.equal(root.querySelectorAll('.architecture-mobile-lane').length,6);
assert.equal([...root.querySelectorAll('.architecture-mobile-lane')].filter(node=>node.open).length,1);
assert.equal(root.querySelectorAll('.architecture-evidence tbody tr').length,3);
for(const [index,source] of onboarding.sources.entries()){
 const row=root.querySelectorAll('.architecture-evidence tbody tr')[index];
 assert.equal(row.querySelector('a').textContent,source.name);
 assert.equal(new URL(row.querySelector('a').href,'http://localhost').searchParams.get('dataset'),source.key);
 assert.equal(row.children[2].textContent,new Intl.NumberFormat('en-AU').format(source.metrics.observations));
 assert.equal(row.children[4].textContent,String(source.review_queue.length));
}
for(const a of root.querySelectorAll('a[href^="/?"]')){
 const url=new URL(a.getAttribute('href'),'http://localhost');
 assert.ok(['onboarding','discovery','mapping','identity','profiles','write-up'].includes(url.searchParams.get('part')));
 if(url.searchParams.has('stage'))assert.ok(Number(url.searchParams.get('stage'))>=1&&Number(url.searchParams.get('stage'))<=7);
}
assert.match(root.textContent,/automatic promotion/);
assert.match(root.textContent,/synthetic decisions/);
assert.match(root.textContent,/Human precision and review time remain unmeasured/);
assert.ok(!root.textContent.includes('[object Object]'));
assert.ok(!root.textContent.includes('NaN'));
assert.equal(fs.readFileSync('frontend/public/system-architecture.svg','utf8'),architectureSvg(core));
assert.equal(fs.readFileSync('frontend/dist/system-architecture.svg','utf8'),architectureSvg(core));
console.log('Architecture checks passed: 6 lanes, 30 linked nodes, 3 evidence rows, mobile disclosures, SVG/build parity.');
