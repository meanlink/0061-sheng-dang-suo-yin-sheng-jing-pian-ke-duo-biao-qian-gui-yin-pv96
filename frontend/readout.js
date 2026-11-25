import {empty, h} from './base.js';
export const intro = (name, description) => `<header class="intro"><h1>${h(name)}</h1><p>${h(description)}</p></header>`;
export function table(caption, columns, rows) {
  if (!rows.length) return empty('当前没有符合条件的记录。');
  return `<div class="data-frame"><table><caption>${h(caption)}</caption><thead><tr>${columns.map(c => `<th scope="col">${h(c)}</th>`).join('')}</tr></thead><tbody>${rows.map(row => `<tr>${row.map(x => `<td>${h(x)}</td>`).join('')}</tr>`).join('')}</tbody></table></div>`;
}
export const stats = pairs => `<dl class="statline">${pairs.map(([label,value]) => `<div><dt>${h(label)}</dt><dd>${h(value)}</dd></div>`).join('')}</dl>`;
