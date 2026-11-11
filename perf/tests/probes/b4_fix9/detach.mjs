import os from 'node:os';
import path from 'node:path';
import fs from 'node:fs';
import { Worker } from 'node:worker_threads';
import { pathToFileURL } from 'node:url';

const repo = process.argv[2];
if (!repo) throw new Error('usage: node <probe> <repository root>');
const witnessUrl = pathToFileURL(`${repo}/perf/runner/witness.mjs`).href;
const criteriaUrl = pathToFileURL(`${repo}/perf/runner/criteria_input.mjs`).href;
const { loadPlaywright } = await import(witnessUrl);
const { runCriteriaSuite } = await import(criteriaUrl);
const {chromium} = await loadPlaywright();
const browser = await chromium.launch({headless:true,args:['--font-render-hinting=none','--disable-lcd-text']});
const root = fs.mkdtempSync(path.join(os.tmpdir(), 'b4-probe-'));
try {
  // Real renderer crash while the suite is between C04 and C07. Use an unusual wrapper message.
  for(let i=0;i<2;i++) {
    const context=await browser.newContext(); const page=await context.newPage();
    await page.setContent('<div id="doc" contenteditable>ORIGINAL</div>');
    const cdp=await context.newCDPSession(page); let crashed=false; let probes=0; let sessionClosed=false; let detachedEvent=false; cdp.on('close',()=>sessionClosed=true); cdp.on('Detached',()=>detachedEvent=true);
    page.on('crash',()=>crashed=true);
    const proxy=new Proxy(page,{get(t,k){if(k==='evaluate') return async(fn,arg)=>{
      if(fn.name==='RESOLVE_CLICK_CLIP') {
        await cdp.detach();
        await cdp.send('Runtime.evaluate', {expression:'1'}); throw new Error('unreachable: detached session accepted command');
      }
      if(fn.toString()==='() => true') probes++;
      return page.evaluate(fn,arg);
    }; const v=t[k]; return typeof v==='function'?v.bind(t):v;}});
    const payload=await runCriteriaSuite({page:proxy,cdp,editSelector:'#doc',criteria:['C04','C07'],quiescenceMs:20,quiescenceTimeoutMs:200});
    const row={sessionClosed,detachedEvent,crashed,isClosed:page.isClosed(),probes,reason:payload.criteria.C07.failure_reason};
    fs.writeFileSync(`${root}/real-detach-${i}.json`,JSON.stringify(row,null,2)); console.log(row);
    await context.close();
  }
  if(process.argv.includes('--crash-only')) process.exitCode=0;
  else for(const mode of ['ambient','load']) {
    const workers=mode==='load'?Array.from({length:4},()=>new Worker('for(;;) { Math.sqrt(Math.random()); }',{eval:true})):[];
    try {for(let i=0;i<(mode==='load'?8:3);i++) {
      const context=await browser.newContext({viewport:{width:1280,height:900}});
      await context.grantPermissions(['clipboard-read','clipboard-write'],{origin:'http://b4.test'});
      const page=await context.newPage(); await page.route('**/*',r=>r.fulfill({contentType:'text/html',body:fs.readFileSync(`${repo}/perf/tests/fixtures/hosts/b4/control.html`,'utf8')}));
      await page.goto('http://b4.test/'); const cdp=await context.newCDPSession(page); const deltas=[];
      const proxy=new Proxy(page,{get(t,k){if(k==='evaluate')return async(fn,arg)=>{const value=await page.evaluate(fn,arg);if(arg?.count && arg?.budget)deltas.push(value);return value;};const v=t[k];return typeof v==='function'?v.bind(t):v;}});
      const payload=await runCriteriaSuite({page:proxy,cdp,editSelector:'#doc',criteria:['C08'],bulkChars:100,frameTimeoutMs:4000,expectedBodyText:'fixture line one\nfixture line two\n',correctnessAdapter:'dom_innerText'});
      fs.writeFileSync(`${root}/c08-${mode}-${i}.json`,JSON.stringify({deltas,payload},null,2));
      console.log(JSON.stringify({mode,i,interval:payload.paint_witness.frame_interval_ms,outcome:payload.criteria.C08.outcome,reason:payload.criteria.C08.failure_reason,obs:payload.criteria.C08.observations.map(o=>({input:o.input_ms,sample:o.sample_ms,after:o.witness?.after_page_ms,frame:o.witness?.frame_page_ms,failure:o.failure}))}));
      await context.close();
    }}finally{await Promise.all(workers.map(w=>w.terminate()));}
  }
}finally{await browser.close();}
