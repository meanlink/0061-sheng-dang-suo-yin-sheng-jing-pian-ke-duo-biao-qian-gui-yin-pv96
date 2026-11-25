import {h, notice} from './base.js';
export function options(items) {
  return items.map(([value, label]) => `<option value="${h(value)}">${h(label)}</option>`).join('');
}
export const feedback = '<p role="status" aria-live="polite"></p>';
export function onSubmit(form, callback) {
  if (!form) return;
  form.addEventListener('submit', async event => {
    event.preventDefault();
    const button = form.querySelector('[type=submit], button');
    const status = form.querySelector('[role=status]');
    if (button) button.disabled = true;
    try { notice(status, await callback(Object.fromEntries(new FormData(form)))); }
    catch (error) { notice(status, error.message, true); }
    finally { if (button) button.disabled = false; }
  });
}
