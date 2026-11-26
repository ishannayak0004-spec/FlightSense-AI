// Keep the indicator visible until all concurrent loads have settled.
const pending = new Set();
const panel = globalThis.document?.getElementById('flight-loading');
const caption = panel?.querySelector('.loading-caption');
function render() {
  if (!panel) return;
  const first = pending.values().next().value;
  panel.hidden = !first;
  if (first && caption.textContent !== first.label) caption.textContent = first.label;
}
export function begin(label) {
  const task = {label};
  pending.add(task);
  render();
  return () => { pending.delete(task); render(); };
}
if (panel && document.readyState !== 'complete') {
  window.addEventListener('load', begin('Loading FlightSense'), {once:true});
} else {
  render();
}
export async function loadJSON(url, label, options) {
  const finish = begin(label);
  try {
    const response = await fetch(url, options);
    if (!response.ok) throw new Error(label + ' failed. Please try again.');
    return await response.json();
  } finally {
    finish();
  }
}
