import {Worker, isMainThread, parentPort, workerData} from 'node:worker_threads';
import {decodePng} from './witness.mjs';
import {classifyRegion} from './b2_settle.mjs';

// PNG reconstruction is CPU work. Keep it off the CDP acknowledgement thread.
if (!isMainThread) {
  const {baseline,rects,dpr,doc,tolerance}=workerData;
  const before=decodePng(Buffer.from(baseline,'base64'));
  parentPort.on('message',data=>{
    try {
      parentPort.postMessage({value:classifyRegion(decodePng(Buffer.from(data,'base64')),before,rects,dpr,doc,tolerance)});
    } catch(error) {parentPort.postMessage({error:error.message});}
  });
}

/** Serial frame classifier; all failures propagate, and close terminates it. */
export function createRegionClassifier(options) {
  const worker=new Worker(new URL(import.meta.url),{workerData:options});
  let pending=null, failure=null;
  const fail=error=>{
    failure=error;
    if(pending) {pending.reject(error);pending=null;}
  };
  worker.on('error',fail);
  worker.on('exit',()=>fail(new Error('frame classifier closed')));
  worker.on('message',message=>{
    const request=pending;pending=null;
    if(!request) return; // A queued response can race close().
    if(message.error) request.reject(new Error(message.error));
    else request.resolve(message.value);
  });
  return {
    classify(data) {
      if(failure) return Promise.reject(failure);
      if(pending) return Promise.reject(new Error('frame classification already pending'));
      return new Promise((resolve,reject)=>{
        pending={resolve,reject};worker.postMessage(data);
      });
    },
    async close() {
      fail(new Error('frame classifier closed'));
      await worker.terminate();
    },
  };
}
