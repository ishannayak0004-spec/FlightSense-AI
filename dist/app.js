import {setupComparison} from './compare.js';
import {showNonstop} from './nonstop.js';
import {loadEngine} from './engine.js';
const $ = id => document.getElementById(id);
const paths = {
 plane:'<path d="m21 3-6.8 17-2.7-7.5L4 9.8 21 3Z"/><path d="m11.5 12.5 5-5"/>',
 database:'<ellipse cx="12" cy="5" rx="8" ry="3"/><path d="M4 5v13c0 4 16 4 16 0V5M4 11c0 4 16 4 16 0"/>',
 globe:'<circle cx="12" cy="12" r="9"/><ellipse cx="12" cy="12" rx="4" ry="9"/><path d="M3 12h18"/>',
 sliders:'<path d="M3 6h5m4 0h9M3 17h10m4 0h4"/><circle cx="10" cy="6" r="2"/><circle cx="15" cy="17" r="2"/>',
 swap:'<path d="M3 8h17l-4-4M21 16H4l4 4"/>',spark:'<path d="m12 3 2.2 6.8L21 12l-6.8 2.2L12 21l-2.2-6.8L3 12l6.8-2.2L12 3Z"/>',pulse:'<path d="M2 13h5l3-8 4 14 3-8 2 2h3"/>'
};
document.querySelectorAll('[data-i]').forEach(el=>{el.outerHTML='<svg class="ic" viewBox="0 0 24 24" aria-hidden="true">'+paths[el.dataset.i]+'</svg>';});
const codes={Delhi:'DEL',Mumbai:'BOM',Bangalore:'BLR',Chennai:'MAA',Hyderabad:'HYD',Kolkata:'CCU'};
const labels={zero:'Nonstop',one:'1 stop',two_or_more:'2+ stops',Indigo:'IndiGo',GO_FIRST:'Go First',Air_India:'Air India',Early_Morning:'Early morning',Late_Night:'Late night'};
const fields=['source_city','destination_city','class','airline','stops','departure_time','arrival_time'];
const money=x=>'₹'+Math.round(x).toLocaleString('en-IN');
const pct=x=>(100*x).toFixed(1)+'%';
let engine,option;
function navigate(){const id=location.hash.slice(1);const active=['lab','dataset','international','workspace','live'].includes(id)?id:'world';
 document.querySelector('.sys').lastChild.textContent=active==='live'?' Live search':' Historical model';
 document.querySelectorAll('.view').forEach(el=>el.hidden=el.id!==active);
 document.querySelectorAll('nav a').forEach(a=>{const on=a.hash==='#'+active;a.classList.toggle('on',on);if(on)a.setAttribute('aria-current','page');else a.removeAttribute('aria-current');});}
window.addEventListener('hashchange',navigate);navigate();
function configure(preferred){
 let matches=engine.options;
 for(const field of fields){
  const select=$(field),wanted=preferred[field]||select.value;
  const values=[...new Set(matches.map(r=>r[field]))].sort();
  select.replaceChildren(...values.map(v=>new Option(codes[v]?v+' ('+codes[v]+')':labels[v]||v,v)));
  select.value=values.includes(wanted)?wanted:values[0];
  matches=matches.filter(r=>r[field]===select.value);
 }
 option=matches[0];const duration=$('duration'),days=$('days_left');
 duration.min=option.durationMin;duration.max=option.durationMax;duration.value=option.durationMedian;
 days.min=option.daysMin;days.max=option.daysMax;days.value=Math.max(option.daysMin,Math.min(option.daysMax,+days.value));
 $('minDay').textContent=option.daysMin+'d';$('maxDay').textContent=option.daysMax+'d';dayValue();
}
function dayValue(){$('dayvalue').textContent=$('days_left').value+' days ahead';}
function drawCurve(rec){
 const pts=[];for(let d=option.daysMin;d<=option.daysMax;d++)pts.push({d,p:engine.predict({...rec,days_left:d}).price});
 const min=Math.floor(Math.min(...pts.map(q=>q.p))/500)*500, max=Math.max(min+500,Math.ceil(Math.max(...pts.map(q=>q.p))/500)*500);
 const x=d=>46+(d-option.daysMin)*390/Math.max(1,option.daysMax-option.daysMin), y=p=>92-77*(p-min)/(max-min);
 const line=pts.map(({d,p},i)=>(i?'L':'M')+x(d).toFixed(2)+' '+y(p).toFixed(2)).join(' ');
 const ticks=[min,(max+min)/2,max];const tickDay=[...new Set([option.daysMin,Math.round((option.daysMin+option.daysMax)/2),option.daysMax])];
 const active=pts.find(q=>q.d===rec.days_left);
 $('chart').innerHTML='<svg class="graph" viewBox="0 0 456 119" role="img" aria-label="Predicted fare by booking lead time"><defs><linearGradient id="fill" x1="0" x2="0" y1="0" y2="1"><stop stop-color="#51decd" stop-opacity=".28"/><stop offset="1" stop-color="#51decd" stop-opacity="0"/></linearGradient></defs>'+ticks.map(v=>'<path stroke="#2b4050" stroke-dasharray="3 4" d="M46 '+y(v)+'h390"/><text x="39" y="'+(y(v)+4)+'" text-anchor="end" fill="#a6b8c7" font-size="11">'+(v/1000).toFixed(1)+'k</text>').join('')+'<path fill="url(#fill)" d="'+line+' L'+x(pts.at(-1).d)+' 92 L46 92Z"/><path d="'+line+'" fill="none" stroke="#65eadb" stroke-width="2.6" stroke-linejoin="round"/><circle cx="'+x(active.d)+'" cy="'+y(active.p)+'" r="4.5" fill="#7bffee" stroke="#0c242e" stroke-width="2"/>'+tickDay.map(d=>'<text x="'+x(d)+'" y="112" text-anchor="middle" font-size="11" fill="#a6b8c7">'+d+'d</text>').join('')+'</svg>';
 $('chartNote').textContent=pts.length>1?'Historical model estimates as booking lead time varies. All other flight details are held fixed.':'This itinerary has one observed booking lead time.';
}
function estimate(){try{
 const rec={...option,duration:+$('duration').value,days_left:+$('days_left').value},pred=engine.predict(rec);
 for(const [field,city] of [['from',rec.source_city],['to',rec.destination_city]]){$(field+'Code').textContent=codes[city];$(field+'Name').textContent=city;}
 showNonstop($('indiaNonstop'),codes[rec.source_city],codes[rec.destination_city]);
 $('cabin').textContent=rec.class;$('price').textContent=money(pred.price);$('interval').textContent=money(pred.low)+' – '+money(pred.high);
 drawCurve(rec);$('error').textContent='';const box=document.querySelector('.result');box.classList.remove('flash');requestAnimationFrame(()=>box.classList.add('flash'));
 }catch(e){$('error').textContent=e.message;}}
function dirty(){$('error').textContent='Flight details changed. Select Estimate airfare to update the result.';}
function renderTables(){
 const r=engine.report;$('metricsIntro').textContent='Evaluated on '+r.testRows.toLocaleString()+' fares from '+r.flightGroups[3]+' flight numbers excluded from training, tuning, and interval calibration. The deployed blend uses 85% gradient boosting and 15% neural-network predictions.';
 $('metrics').innerHTML=r.metrics.map(m=>'<tr><td>'+m.name+'</td><td>'+money(m.mae)+'</td><td>'+money(m.rmse)+'</td><td>'+m.r2.toFixed(4)+'</td><td>'+pct(m.within10)+'</td></tr>').join('');
 $('coverage').textContent='The range uses cabin-specific errors from a separate calibration set. It contained '+pct(r.coverage)+' of held-out fares. Actual booking prices today can differ because routes, airlines, and market conditions have changed since 2022.';
 $('airports').innerHTML=Object.entries(codes).map(([city,code])=>{const rows=engine.options.filter(r=>r.source_city===city);return '<tr><td>'+code+'</td><td>'+city+'</td><td>'+new Set(rows.map(r=>r.destination_city)).size+'</td><td>'+new Set(rows.map(r=>r.airline)).size+'</td></tr>';}).join('');
}
try{
 engine=await loadEngine();configure({source_city:'Delhi',destination_city:'Mumbai',class:'Economy',airline:'Indigo',stops:'zero',departure_time:'Morning',arrival_time:'Morning'});
 $('estimate').disabled=false;renderTables();estimate();
 setupComparison(engine,codes,record=>{
  configure(record);
  $('duration').value=record.duration;
  $('days_left').value=record.days_left;
  dayValue();
  $('singleEstimate').open=true;
  estimate();
  $('singleEstimate').scrollIntoView({block:'start'});
 });
 for(const f of fields)$(f).addEventListener('change',()=>{configure({});dirty();});
 $('swap').addEventListener('click',()=>{configure({source_city:$('destination_city').value,destination_city:$('source_city').value});dirty();});
 $('days_left').addEventListener('input',()=>{dayValue();dirty();});$('duration').addEventListener('input',dirty);
 $('form').addEventListener('submit',e=>{e.preventDefault();estimate();});
}catch(e){$('price').textContent='Unavailable';$('error').textContent='The model could not be loaded. Reload to try again.';$('compareMeta').textContent='The India model could not be loaded. Reload to try again.';console.error(e);}
