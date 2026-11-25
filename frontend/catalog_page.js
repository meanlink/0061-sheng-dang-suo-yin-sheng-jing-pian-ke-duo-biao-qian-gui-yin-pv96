import {intro,table} from './readout.js';
import {feedback,onSubmit,options} from './submit.js';
import {archives,data,save} from './sound_client.js';
import {picker,labels as labelNames} from './archive_scope.js';
import {filter,checkboxes} from './catalog_filters.js';

function versionPicker(versions,arc){
 const current=arc?.current_version??1;
 const draft=arc?.draft_version??null;
 const opts=[['current',`当前签发版（第 ${current} 版）`]];
 if(draft)opts.push(['draft',`补正草稿（第 ${draft} 版 · 签齐后切换）`]);
 (versions||[]).filter(v=>v.version!==current).forEach(v=>{
  opts.push([String(v.version),`第 ${v.version} 版${v.status==='published'?'（已归档）':'（草稿）'}`]);
 });
 return `<label>按版本查阅<select name="version">${options(opts)}</select></label>`;
}

export async function render(outlet,user){
 const list=await archives();
 outlet.innerHTML=`${intro('归档检索','编辑按候选逐段签档。补正新版签齐前，这里始终展示完整旧版；签齐后一次性切换。历史版本可按版本复查标签与签发依据。')}<div class="toolrow">${picker(list)}${filter()}<span class="version-slot"></span></div><div class="split"><section class="book band"></section><div class="sign-area"></div></div>`;
 const pick=outlet.querySelector('[name=archive]'), tag=outlet.querySelector('[name=label]');
 const versionSlot=outlet.querySelector('.version-slot');
 let versions=[];

 async function versionQuery(){
  const ver=outlet.querySelector('[name=version]')?.value||'current';
  const params=new URLSearchParams();
  if(tag.value)params.set('label',tag.value);
  if(ver!=='current')params.set('version',ver);
  const qs=params.toString();
  return 'index'+(qs?`?${qs}`:'');
 }

 async function results(){
  const rows=pick.value?await data(pick.value,await versionQuery()):[];
  outlet.querySelector('.book').innerHTML=table('已归档的片刻',['片刻','秒段','签发标签','签发依据 / 签发人'],rows.map(r=>[r.number,`${r.start_s}–${r.end_s}`,(r.labels||[]).map(x=>labelNames[x]||x).join('、'),`${r.note}${r.signer?` — ${r.signer}`:''}${r.inherited?'（沿用原签发记录）':''}`]));
 }

 async function draw(){
  if(!pick.value)return;
  const arc=list.find(r=>r.code===pick.value);
  try{versions=await data(pick.value,'versions');}catch{versions=[];}
  const priorVersion=outlet.querySelector('[name=version]')?.value||'current';
  versionSlot.innerHTML=versionPicker(versions,arc);
  const verSel=versionSlot.querySelector('select');
  if([...verSel.options].some(o=>o.value===priorVersion))verSel.value=priorVersion;
  verSel.onchange=results;
  await results();

  const sign=outlet.querySelector('.sign-area');sign.innerHTML='';
  if(user.role!=='reviewer'||!pick.value)return;

  if(arc?.draft_version){
   // 补正草稿：只列尚未签齐的片刻，候选带乐观锁 token。
   const [detail,evidence]=await Promise.all([
     data(pick.value,'versions/draft'),
     data(pick.value,'labels?version=draft'),
   ]);
   const pending=detail.pending||[];
   if(!pending.length){sign.innerHTML='<p class="empty-state">草稿已签齐，正在切换版本…</p>';return;}
   const tokenByNumber={};
   (evidence.scores||[]).forEach(s=>{tokenByNumber[s.number]=s.token??s.content_hash;});
   sign.innerHTML=`<form class="entry"><h2>按新候选重签片刻</h2>
     <p class="hint">改过的片刻须用新候选重新签档；提交时会核对候选指纹，片刻若再次被补正，旧候选将被拒绝。</p>
     <label>片刻<select name="number">${options(pending.map(x=>[x,'片刻 '+x]))}</select></label>
     <div class="picks"></div>
     <input type="hidden" name="token" value="">
     <label>归档备注（签发依据）<textarea name="note" required minlength="6"></textarea></label>
     <button>签发片刻</button>${feedback}</form>`;
   const form=sign.querySelector('form'), number=form.querySelector('[name=number]');
   function tags(){
    const rows=(evidence.scores||[]).filter(r=>r.number===+number.value && Number(r.score)>=evidence.threshold);
    sign.querySelector('.picks').innerHTML=checkboxes(rows.map(r=>r.label));
    form.querySelector('[name=token]').value=tokenByNumber[number.value]||rows[0]?.token||'';
   }
   number.onchange=tags;tags();
   onSubmit(form,async input=>{
    const payload={labels:new FormData(form).getAll('tag'),note:input.note};
    if(input.token)payload.token=input.token;
    const done=await save(pick.value,'index/'+input.number,payload);
    if(done?.published){
     const fresh=await archives();list.splice(0,list.length,...fresh);
    }
    await draw();
    return done?.published?'全部签齐，已一次性切换到新版':'片刻已签发';
   });
   return;
  }

  if(arc?.state!=='scored')return;
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
