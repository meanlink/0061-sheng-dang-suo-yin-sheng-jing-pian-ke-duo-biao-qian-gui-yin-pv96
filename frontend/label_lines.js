import {h} from './base.js';
import {factors,labels} from './archive_scope.js';
export function spectra(rows,threshold){
 if(!rows.length)return '<p>等待监听时长达到归因要求。</p>';
 return `<div class="labeler">${rows.map(x=>`<article class="spectrum"><strong>片刻 ${h(x.number)} · ${h(labels[x.label])}</strong> <meter min="0" max="1" value="${h(x.score)}"></meter> ${h(x.score)} · ${Number(x.score)>=threshold?'候选':'未达阈值'}
   <details><summary>证据贡献</summary><p>${Object.entries(x.factors).map(([key,value])=>h(factors[key])+': '+h(value)).join(' / ')}</p></details></article>`).join('')}</div>`;
}
