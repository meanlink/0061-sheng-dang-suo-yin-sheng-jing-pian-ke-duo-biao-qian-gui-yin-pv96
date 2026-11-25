import {intro,stats} from './readout.js';
import {archives,data} from './sound_client.js';
import {picker,states} from './archive_scope.js';
import {timeline} from './archive_timeline.js';
export async function render(outlet) {
 const list=await archives();
 outlet.innerHTML=`${intro('声档卷宗','卷宗记录收录日期、音轨时长和试听区间。归档检索依赖后续签过的片刻标签。')}<div class="toolrow">${picker(list)}</div><div class="split"><section class="tape"></section><aside class="callout"><h2>环境声叠加</h2><p>同一时窗可出现多种声源。人群与马达或浪声可能同时通过阈值。</p></aside></div>`;
 const select=outlet.querySelector('select');
 async function draw(){ if(!select.value)return; const r=list.find(x=>x.code===select.value);const clips=await data(r.code,'clips');outlet.querySelector('.tape').innerHTML=stats([['状态',states[r.state]],['音轨',r.duration+' 秒'],['采录日期',r.record_date]])+timeline(clips); }
 select.onchange=draw;await draw();
}
