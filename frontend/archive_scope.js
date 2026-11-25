import {options} from './submit.js';
export const states={listening:'试听',sealed:'证据已封',scored:'已归因',indexed:'已归档'};
export const labels={crowd:'来往人群',motor:'马达与船流',water:'水面与浪声'};
export const factors={voices:'可辨人声',movement:'脚步/运动',engines:'引擎',surf:'浪涌',baseline:'基线'};
export const picker=items=>`<label>声档卷号<select name="archive">${options(items.map(r=>[r.code,r.code+' · '+r.title]))}</select></label>`;
