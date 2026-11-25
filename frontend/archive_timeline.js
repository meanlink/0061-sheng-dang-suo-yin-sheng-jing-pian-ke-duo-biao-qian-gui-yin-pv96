import {h} from './base.js';
export function timeline(clips){
 return `<div class="trace">${clips.map(x=>`<div class="slice"><strong>片刻 ${h(x.number)}</strong><span>${h(x.start_s)}–${h(x.end_s)} 秒</span></div>`).join('')}</div>`;
}
