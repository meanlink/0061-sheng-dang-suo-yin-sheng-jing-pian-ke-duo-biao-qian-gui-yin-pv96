import {api} from './base.js';
const path='/api/sound-archives';
export const archives=()=>api(path);
export const data=(code,scope)=>api(`${path}/${encodeURIComponent(code)}/${scope}`);
export const save=(code,scope,input)=>api(`${path}/${encodeURIComponent(code)}/${scope}`,'POST',input);
