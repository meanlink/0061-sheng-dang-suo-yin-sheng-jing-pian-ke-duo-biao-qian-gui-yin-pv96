import {h} from './base.js';
import {options} from './submit.js';
import {labels} from './archive_scope.js';
export const filter=()=>`<label>按标签过滤<select name="label"><option value="">全部已签片刻</option>${options(Object.entries(labels))}</select></label>`;
export const checkboxes=items=>items.length?items.map(key=>`<label><input type="checkbox" name="tag" value="${h(key)}"> ${h(labels[key])}</label>`).join(''):'<p>本片刻无过线候选，可签无标签并注明原因。</p>';
