import {intro,table} from './readout.js';
import {feedback,onSubmit} from './submit.js';
import {archives,data,save} from './sound_client.js';
import {picker,factors} from './archive_scope.js';
const numeric=(name,label,min,max,step='1')=>`<label>${label}<input type="number" name="${name}" min="${min}" max="${max}" step="${step}" required></label>`;
export async function render(outlet,user){
 const list=await archives();
 outlet.innerHTML=`${intro('片刻证据','用不重叠的秒数区间登记监听现象。听辨特征范围为 0 到 1。')}<div class="toolrow">${picker(list)}</div><div class="split"><div class="cuts band"></div>
 ${user.role==='operator'?`<form class="entry"><h2>登记监听区间</h2>
 ${numeric('number','片刻号',1,100)}${numeric('start_s','开始 / 秒',0,3600)}${numeric('end_s','结束 / 秒',1,3600)}
 ${Object.entries(factors).filter(([key])=>key!=='baseline').map(([key,label])=>numeric(key,label,0,1,'.01')).join('')}
 <button>保存片刻</button>${feedback}</form>`:''}</div>`;
 const select=outlet.querySelector('[name=archive]');
 async function draw(){if(select.value)outlet.querySelector('.cuts').innerHTML=table('听辨卡',['片刻','秒段','人声','运动','引擎','浪涌'],(await data(select.value,'clips')).map(r=>[r.number,`${r.start_s}–${r.end_s}`,r.voices,r.movement,r.engines,r.surf]));}
 select.onchange=draw;
 onSubmit(outlet.querySelector('form'),async entry=>{await save(select.value,'clips',Object.fromEntries(Object.entries(entry).map(([k,v])=>[k,+v])));await draw();return '片刻已保存';});
 await draw();
}
