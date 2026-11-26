import {begin,loadJSON} from './loading.js';
const $ = id => document.getElementById(id);
const make = (tag, text, cls) => {
  const el = document.createElement(tag);
  if (text != null) el.textContent = text;
  if (cls) el.className = cls;
  return el;
};
const fmt = new Intl.NumberFormat('en-IN',{style:'currency',currency:'INR',maximumFractionDigits:0});
let directory, pending;
const localDate = d => new Date(d.getTime()-d.getTimezoneOffset()*60000).toISOString().slice(0,10);
const today = new Date();
$('lvDate').min = localDate(today);
today.setDate(today.getDate()+14);
$('lvDate').value = localDate(today);
function dates() {
  const round = $('lvTrip').value === 'Round trip';
  $('lvReturnLabel').hidden = !round;
  $('lvReturn').required = round;
  $('lvReturn').min = $('lvDate').value;
  if ($('lvReturn').value < $('lvDate').value) $('lvReturn').value = $('lvDate').value;
}
dates();
$('lvTrip').onchange = dates;
$('lvDate').onchange = dates;
function ask(data,title,target) {
  if (pending) return;
  const id = crypto.randomUUID();
  pending = {id, data, title,target, finish:begin('Checking live flight prices')};
  $('lvGo').disabled = true;
  target.replaceChildren();
  $('lvStatus').textContent = 'Searching airline offers…';
  window.sendFareRequest({...data,id});
}
function render() {
  const state = window.flightState;
  $('lvGo').disabled = !directory || !state?.ready || !!pending;
  if (!state?.ready) {
    $('lvStatus').textContent = state ? 'Add your SerpApi key in Streamlit Secrets to enable search.' : 'Connecting to Streamlit…';
    return;
  }
  if (!pending) {
    if ($('lvStatus').textContent === 'Connecting to Streamlit…') $('lvStatus').textContent='';
    return;
  }
  if (state.reply?.id !== pending.id) return;
  const job = pending, reply = state.reply;
  pending = null;
  job.finish();
  $('lvGo').disabled = false;
  $('lvStatus').textContent = reply.error || '';
  if (reply.error) return;
  const section = make('section',null,'card comparison');
  job.target.replaceChildren(section);
  const sort = make('select');
  for (const [v,n] of [['price','Lowest fare'],['duration','Shortest journey'],['name','Airline name']]) sort.add(new Option(n,v));
  const heading = make('div',null,'compare-heading');
  const label = make('label','Sort by ','fare-sort');
  label.append(sort);
  heading.append(make('h3',job.title),label);
  section.append(heading,make('p',reply.offers.length+' offers · Checked '+reply.checked+' · Google Flights via SerpApi','fine'));
  if (!reply.offers.length) section.append(make('p','No fares found for this search.'));
  const list = make('div');
  section.append(list);
  const offers = reply.offers.map((o,index)=>({o,index}));
  const cheapest = Math.min(...offers.map(({o})=>o.price??Infinity));
  const highest = Math.max(...offers.map(({o})=>o.price??0));
  function rows() {
    list.replaceChildren();
    for (const {o,index} of [...offers].sort((a,b)=>sort.value==='duration'?(a.o.total_duration??Infinity)-(b.o.total_duration??Infinity):sort.value==='name'?String(a.o.flights[0].airline).localeCompare(String(b.o.flights[0].airline)):(a.o.price??Infinity)-(b.o.price??Infinity))) {
      const legs=o.flights, first=legs[0], last=legs.at(-1), logo=o.airline_logo||first.airline_logo;
      const row=make('article',null,'fare-row'), mark=make('span',first.airline?.slice(0,2),'fare-mark');
      if (logo?.startsWith('https://')) {
        const img=new Image();img.alt='';img.onload=()=>mark.replaceChildren(img);img.src=logo;
      }
      const info=make('div'), name=make('h4',[...new Set(legs.map(l=>l.airline))].join(' · '));
      if (o.price===cheapest && offers.length>1) {row.classList.add('best-fare');name.append(make('span','Lowest fare','lowest-label'));}
      const times=first.departure_airport.id+' '+first.departure_airport.time+' → '+last.arrival_airport.id+' '+last.arrival_airport.time;
      info.append(name,make('p',times),make('p',[(legs.length===1?'Nonstop':(legs.length-1)+' stop(s)'),Number.isFinite(o.total_duration)?Math.floor(o.total_duration/60)+'h '+o.total_duration%60+'m':'','Airport local times'].filter(Boolean).join(' · ')));
      const details=make('details');details.append(make('summary','Flight details'));
      legs.forEach(l=>details.append(make('p',[l.flight_number,l.departure_airport.id+' → '+l.arrival_airport.id].filter(Boolean).join(' · '))));
      info.append(details);
      const amount=make('div',null,'compare-amount');
      amount.append(make('strong',Number.isFinite(o.price)?fmt.format(o.price):'Unavailable'));
      if (highest>0 && Number.isFinite(o.price)){const meter=make('span',null,'fare-meter');meter.style.setProperty('--fare-ratio',o.price/highest);amount.append(meter);}
      if (job.data.action!=='return' && job.data.back && o.departure_token) {
        const btn=make('button','See return flights');btn.onclick=()=>ask({action:'return',index,searchId:job.id},'Return options for '+first.flight_number+' · '+times,$('lvInbound'));amount.append(btn);
      }
      row.append(mark,info,amount);list.append(row);
    }
  }
  rows();sort.onchange=rows;
  if (job.data.action==='return') section.scrollIntoView({block:'start'});
}
window.addEventListener('fare-render',render);
render();
loadJSON(new URL('./global/airports.json',import.meta.url),'Loading airports').then(data=>{
  directory = new Set(data.map(r=>r[0]));
  for (const side of ['From','To']) {
    const box=$('lv'+side), list=$('lv'+side+'List');
    box.oninput=()=>{
      box.setCustomValidity('');
      const query=box.value.trim().toLowerCase();
      list.replaceChildren(...data.filter(r=>[r[0],r[1],r[2]].some(v=>v?.toLowerCase().includes(query))).slice(0,24).map(r=>new Option(r[1]+' · '+r[2],r[0])));
    };
  }
  render();
}).catch(()=>{$('lvStatus').textContent='Failed to load airports. Reload to try again.';});
$('liveForm').onsubmit=e=>{
  e.preventDefault();
  const [origin,dest]=['From','To'].map(k=>$('lv'+k).value.trim().toUpperCase());
  for(const [k,v] of [['From',origin],['To',dest]]) if(!directory?.has(v)){
    const field=$('lv'+k);field.setCustomValidity('Select an airport or enter its three-letter IATA code.');field.reportValidity();return;
  }
  const depart=$('lvDate').value,back=$('lvTrip').value==='Round trip'?$('lvReturn').value:null;
  $('lvInbound').replaceChildren();
  ask({origin,dest,depart,back,adults:Number($('lvAdults').value),cabin:Number($('lvCabin').value),nonstop:$('lvStops').value==='Nonstop only'},origin+(back?' ⇄ ':' → ')+dest+' · '+depart+(back?' – '+back:''),$('lvResults'));
};
