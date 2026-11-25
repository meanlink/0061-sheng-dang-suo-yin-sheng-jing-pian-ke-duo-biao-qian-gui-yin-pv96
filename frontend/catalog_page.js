import {intro,table} from './readout.js';
import {feedback,onSubmit,options} from './submit.js';
import {archives,data,save} from './sound_client.js';
import {picker,labels} from './archive_scope.js';
import {filter,checkboxes} from './catalog_filters.js';
export async function render(outlet,user){
 const list=(await archives()).filter(r=>['scored','indexed'].includes(r.state));
 outlet.innerHTML=`${intro('归档检索','编辑按候选逐段签档。已签片刻可按最终声源标签查找。')}<div class="toolrow">${picker(list)}${filter()}</div><div class="split"><section class="book band"></section><div class="sign-area"></div></div>`;
 const pick=outlet.querySelector('[name=archive]'), tag=outlet.querySelector('[name=label]');
 async function results(){
   const rows=pick.value?await data(pick.value,'index'+(tag.value?'?label='+encodeURIComponent(tag.value):'')):[];
   outlet.querySelector('.book').innerHTML=table('已归档的片刻',['片刻','秒段','签发标签','编辑凭据'],rows.map(r=>[r.number,`${r.start_s}–${r.end_s}`,r.labels.map(x=>labels[x]).join('、'),r.note]));
 }
 async function draw(){
   await results();
   const sign=outlet.querySelector('.sign-area');sign.innerHTML='';
   if(user.role!=='reviewer'||!pick.value||list.find(r=>r.code===pick.value).state!=='scored')return;
   const [evidence,existing,clips]=await Promise.all([data(pick.value,'labels'),data(pick.value,'index'),data(pick.value,'clips')]);
   const pending=clips.filter(c=>!existing.some(x=>x.number===c.number));
   if(!pending.length)return;
   sign.innerHTML=`<form class="entry"><h2>签片刻索引</h2><label>片刻<select name="number">${options(pending.map(x=>[x.number,'片刻 '+x.number]))}</select></label><div class="picks"></div><label>归档备注<textarea name="note" required minlength="6"></textarea></label><button>签发片刻</button>${feedback}</form>`;
   const form=sign.querySelector('form'), number=form.querySelector('select');
   function tags(){ sign.querySelector('.picks').innerHTML=checkboxes(evidence.scores.filter(r=>r.number===+number.value && Number(r.score)>=evidence.threshold).map(r=>r.label)); }
   number.onchange=tags;tags();
   onSubmit(form,async input=>{await save(pick.value,'index/'+input.number,{labels:new FormData(form).getAll('tag'),note:input.note});await draw();return '片刻已签发';});
 }
 pick.onchange=draw;tag.onchange=results;await draw();
}
