import {waitJob} from './base.js';
import {intro} from './readout.js';
import {feedback,onSubmit} from './submit.js';
import {archives,data,save} from './sound_client.js';
import {picker} from './archive_scope.js';
import {spectra} from './label_lines.js';
export async function render(outlet,user){
 const list=await archives();
 outlet.innerHTML=`${intro('候选归因','每种声源独立评分。展开说明查看听辨特征给候选带来的贡献。')}<form class="toolrow">${picker(list)}${user.role==='reviewer'?'<button>冻结监听并归因</button>':''}${feedback}</form><div class="scores band"></div>`;
 const select=outlet.querySelector('select');
 async function draw(){if(!select.value)return;const detail=await data(select.value,'labels');outlet.querySelector('.scores').innerHTML=spectra(detail.scores,detail.threshold);}
 select.onchange=draw;
 onSubmit(outlet.querySelector('form'),async()=>{const job=await save(select.value,'labels');await waitJob(job.job_id);await draw();return '候选标签已生成';});
 await draw();
}
