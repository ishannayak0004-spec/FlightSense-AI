// EUR reference rates retrieved together from Frankfurter on 25 November 2026.
const bundled = {base:'EUR', date:'2026-11-25', rates:{INR:100.859, USD:1.0935, ZAR:19.3514}};
const endpoint = 'https://api.frankfurter.dev/v1/latest?symbols=INR,USD,ZAR';
const cacheKey = 'flightsense.fx.eur.v1';
const formatter = new Intl.NumberFormat('en-IN',{style:'currency',currency:'INR',maximumFractionDigits:0});
const dateFormatter = new Intl.DateTimeFormat('en-IN',{dateStyle:'medium',timeZone:'UTC'});
const listeners = new EventTarget();
let current = bundled, status = 'Checking latest rate', pending = false, lastAttempt = 0;
function valid(data) {
 return data?.base==='EUR' && /^\d{4}-\d{2}-\d{2}$/.test(data.date) &&
  Number.isFinite(Date.parse(data.date)) && ['INR','USD','ZAR'].every(code=>Number.isFinite(data.rates?.[code]) && data.rates[code]>0);
}
try {
 const cached=JSON.parse(localStorage.getItem(cacheKey));
 if(valid(cached) && cached.date>=current.date) current=cached;
} catch { /* Offline and private sessions can use the bundled observation. */ }
function rate(code) { return current.rates.INR/(code==='EUR'?1:current.rates[code]); }
export const inRupees=(amount,code)=>formatter.format(amount*rate(code));
export function exchangeNote(code){
 const asOf=dateFormatter.format(new Date(current.date+'T00:00:00Z'));
 return '1 '+code+' = ₹'+rate(code).toFixed(4)+' · Frankfurter reference rate, '+asOf+(status?' · '+status:'');
}
export function onRateChange(render){listeners.addEventListener('change',render);}
async function refresh(){
 if(pending||Date.now()-lastAttempt<60000)return;
 pending=true;lastAttempt=Date.now();
 const controller=new AbortController(),timeout=setTimeout(()=>controller.abort(),8000);
 try {
  const response=await fetch(endpoint,{cache:'no-store',signal:controller.signal});
  if(!response.ok)throw Error('Rate service unavailable');
  const data=await response.json();
  if(!valid(data)||data.date<current.date)throw Error('Invalid or older observation');
  current=data;status='';
  try{localStorage.setItem(cacheKey,JSON.stringify(data));}catch{}
 } catch {status='Saved rate · latest update unavailable';}
 finally {clearTimeout(timeout);pending=false;listeners.dispatchEvent(new Event('change'));}
}
refresh();
window.addEventListener('online',refresh);
document.addEventListener('visibilitychange',()=>{if(!document.hidden)refresh();});
setInterval(()=>{if(!document.hidden)refresh();},60*60*1000);
