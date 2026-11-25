import {intro,table} from './readout.js';
import {feedback,onSubmit} from './submit.js';
import {archives,data,save} from './sound_client.js';
import {picker,factors} from './archive_scope.js';
const numeric=(name,label,min,max,step='1')=>`<label>${label}<input type="number" name="${name}" min="${min}" max="${max}" step="${step}" required></label>`;

const FEATURE_FIELDS=Object.entries(factors).filter(([key])=>key!=='baseline');

function correctionGrid(rows,draftVersion){
 return `<form class="entry correction-entry"><h2>补正听辨特征 · 同一卷多段</h2>
 <p class="hint">直接修改需要更正的片刻后一次提交。未改动的片刻会沿用原签发记录；提交重试不会新增版本。${draftVersion?`当前为补正草稿第 ${draftVersion} 版。`:''}</p>
 <div class="correction-grid">
 ${rows.map(r=>`<fieldset class="correction-row" data-number="${r.number}">
   <legend>片刻 ${r.number}${r.revised?' · 已改':''}${r.inherited?' · 沿用签发':''}</legend>
   <div class="correction-times">
     <label>开始<input type="number" data-field="start_s" value="${r.start_s}" min="0" max="3600" step="1"></label>
     <label>结束<input type="number" data-field="end_s" value="${r.end_s}" min="1" max="3600" step="1"></label>
   </div>
   <div class="correction-features">
   ${FEATURE_FIELDS.map(([key,label])=>`<label>${label}<input type="number" data-field="${key}" min="0" max="1" step=".01" value="${r[key]}"></label>`).join('')}
   </div>
 </fieldset>`).join('')}
 </div>
 <button type="submit">提交本卷多段补正</button>${feedback}
 <p class="correction-done" role="status" aria-live="polite"></p>
 </form>`;
}

export async function render(outlet,user){
 const list=await archives();
 outlet.innerHTML=`${intro('片刻证据','用不重叠的秒数区间登记监听现象。听辨特征范围为 0 到 1。签档后的卷宗可在此一次补正多段特征。')}<div class="toolrow">${picker(list)}</div><div class="split"><div class="cuts band"></div><div class="side-forms">
 ${user.role==='operator'?`<form class="entry"><h2>登记监听区间</h2>
 ${numeric('number','片刻号',1,100)}${numeric('start_s','开始 / 秒',0,3600)}${numeric('end_s','结束 / 秒',1,3600)}
 ${FEATURE_FIELDS.map(([key,label])=>numeric(key,label,0,1,'.01')).join('')}
 <button>保存片刻</button>${feedback}</form>`:''}
 ${(user.role==='operator'||user.role==='reviewer')?'<div class="correction-slot"></div>':''}
 </div></div>`;
 const select=outlet.querySelector('[name=archive]');
 const slot=outlet.querySelector('.correction-slot');

 async function draw(){
  if(!select.value)return;
  const code=select.value;
  const arc=list.find(x=>x.code===code);
  const live=await data(code,'clips');
  outlet.querySelector('.cuts').innerHTML=table('听辨卡（当前签发/登记值）',['片刻','秒段','人声','运动','引擎','浪涌'],live.map(r=>[r.number,`${r.start_s}–${r.end_s}`,r.voices,r.movement,r.engines,r.surf]));
  if(slot){
   let rows=live;
   let draftVersion=arc?.draft_version??null;
   if(draftVersion){
    try{const detail=await data(code,'versions/draft');rows=detail.clips??live;draftVersion=detail.version;}catch{/* 无草稿时用线上值 */}
   }
   slot.innerHTML=correctionGrid(rows,draftVersion);
   const form=slot.querySelector('form');
   form.addEventListener('submit',async event=>{
    event.preventDefault();
    const button=form.querySelector('button[type=submit]');
    const status=form.querySelector('[role=status]');
    button.disabled=true;
    try{
     const clips=[...form.querySelectorAll('.correction-row')].map(field=>{
      const number=+field.dataset.number;
      const item={number};
      field.querySelectorAll('[data-field]').forEach(input=>{item[input.dataset.field]=+input.value;});
      return item;
     });
     const result=await save(code,'corrections',{clips});
     const message=`已保存补正草稿第 ${result.version} 版，改动片刻 ${(result.changed||[]).join('、')||'无'}；待重签 ${(result.pending||[]).join('、')||'无'}。签齐前归档检索仍显示完整旧版。`;
     const fresh=await archives();
     const updated=fresh.find(x=>x.code===code);
     if(updated&&arc){Object.assign(arc,updated);}
     await draw();
     const done=slot?.querySelector('.correction-done');
     if(done){done.dataset.type='success';done.textContent=message;}
    }catch(error){
     status.dataset.type='error';
     status.textContent=error.message;
    }finally{button.disabled=false;}
   });
  }
 }
 select.onchange=draw;
 onSubmit(outlet.querySelector('form.entry:not(.correction-entry)'),async entry=>{
  await save(select.value,'clips',Object.fromEntries(Object.entries(entry).map(([k,v])=>[k,+v])));
  await draw();
  return '片刻已保存';
 });
 await draw();
}
