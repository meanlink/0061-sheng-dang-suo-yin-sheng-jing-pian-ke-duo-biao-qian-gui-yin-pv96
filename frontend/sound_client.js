import {api} from './base.js';
const path='/api/sound-archives';
export const archives=()=>api(path);
export const archiveDetail=code=>api(`${path}/${encodeURIComponent(code)}`);
export const data=(code,scope)=>api(`${path}/${encodeURIComponent(code)}/${scope}`);
export const save=(code,scope,input,method='POST')=>api(`${path}/${encodeURIComponent(code)}/${scope}`,method,input);
export const put=(code,scope,input)=>save(code,scope,input,'PUT');
export const patch=(code,scope,input)=>save(code,scope,input,'PATCH');
