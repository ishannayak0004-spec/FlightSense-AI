import {inRupees,exchangeNote,onRateChange} from './exchange.js';
const byId = id => document.getElementById(id);
const norm = value => value.toLowerCase().normalize('NFKD').replace(/[\u0300-\u036f]/g,'').trim();
const collections = {
  africa:{title:'Southern Africa · economy', note:'Economy listings collected on 14 March 2025. Tax and baggage inclusion are unspecified.'},
  greece:{title:'Europe to Greece · 2018', note:'The source file covers two departure dates in 2018. It does not identify the airline.'}
};
const carrierAlias = {'South African':'South African Airways','Ethiopian':'Ethiopian Airlines','LAM':'LAM Mozambique Airlines','RwandAir':'Rwandair Express'};
const indiaCodes = {'AIC':'Air India','IGO':'IndiGo','GOW':'Go First','VTI':'Vistara','SEJ':'SpiceJet','IAD':'AirAsia India'};
const rowsBySource = {};
let catalog=[], limit=20;
const choices=(el,values,wanted)=>{
 el.replaceChildren(...values.map(s=>new Option(s,s)));
 if(values.includes(wanted))el.value=wanted;
};
function subset(){
 return rowsBySource[byId('collection').value]||[];
}
function configureWorld(){
 const rows=subset();
 const inputs=[['worldFrom','origin'],['worldTo','destination'],['worldMonth','month']];
 let valid=rows;
 for(const [id,field] of inputs){
  const el=byId(id), wanted=el.value;
  choices(el,[...new Set(valid.map(r=>r[field]))].sort(),wanted);
  valid=valid.filter(r=>r[field]===el.value);
 }
 const names=[...new Set(valid.map(r=>r.airline).filter(Boolean))].sort();
 byId('carrierSuggestions').replaceChildren(...names.map(v=>new Option(v,v)));
 drawWorld(valid);
}
function cell(row,value,tag='td'){const el=document.createElement(tag);el.textContent=value;row.append(el);}
function drawWorld(rows){
 const filter=norm(byId('carrierFilter').value), key=byId('collection').value;
 const selected=rows.filter(r=>!filter||[r.airline,carrierAlias[r.airline]||''].some(x=>x&&norm(x).includes(filter)));
 byId('worldTitle').textContent=byId('worldFrom').value+' → '+byId('worldTo').value;
 byId('worldBasis').textContent=byId('worldMonth').value+' departures · '+collections[key].note;
 const wrap=byId('worldList');wrap.replaceChildren();
 if(!selected.length){wrap.textContent='No carrier-specific observations match this search on this route and month. Clear the airline field to view available evidence.';byId('worldNote').textContent='';return;}
 const table=document.createElement('table'),head=table.createTHead().insertRow();
 for(const val of ['Airline','Median','Low–high','Quotes'])cell(head,val,'th');
 const body=table.createTBody();
 for(const r of selected){
  const fmt=x=>inRupees(x,r.currency);
  const tr=body.insertRow();[r.airline||'Unspecified',fmt(r.median),fmt(r.low)+'–'+fmt(r.high),r.count].forEach(x=>cell(tr,x));
 }
 wrap.append(table);
 byId('worldNote').textContent=exchangeNote(selected[0].currency)+'. Smaller samples give a less reliable picture of the usual fare.';
}
function drawDirectory(){
 const query=norm(byId('directorySearch').value);
 const matches=catalog.filter(a=>a.search.includes(query)).sort((a,b)=>{
  const score=r=>query&&(norm(r.fields[0])===query||r.fields.slice(2,4).some(c=>norm(c)===query))?0:1;
  return score(a)-score(b)||a.fields[0].localeCompare(b.fields[0]);
 });
 byId('directoryStatus').textContent=matches.length?matches.length.toLocaleString()+' matching entries · showing '+Math.min(matches.length,limit):'No directory match. The worldwide estimator still accepts this carrier as a preference.';
 const tbody=byId('directoryRows');tbody.replaceChildren();
 for(const item of matches.slice(0,limit)){
  const [name,,iata,icao,country]=item.fields;
  const row=tbody.insertRow();for(const txt of [name,[iata,icao].filter(Boolean).join(' / ')||'—',country||'Unspecified',item.coverage||'No carrier-specific fare sample'])cell(row,txt);
 }
 byId('moreAirlines').hidden=limit>=matches.length;
}
async function read(name){const response=await fetch(new URL('./global/'+name+'.json',import.meta.url));if(!response.ok)throw Error(name);return response.json();}
try{
 const [airlines,africa,greece,world]=await Promise.all(['airlines','africa','greece','world-model'].map(read));Object.assign(rowsBySource,{africa,greece});
 for(const [key,c] of Object.entries(collections))byId('collection').add(new Option(c.title,key));
 byId('collection').value='africa';configureWorld();onRateChange(configureWorld);
 for(const id of ['collection','worldFrom','worldTo','worldMonth'])byId(id).addEventListener('change',()=>{byId('carrierFilter').value='';configureWorld();});
 byId('carrierFilter').addEventListener('input',configureWorld);
 catalog=airlines.map(fields=>({fields,coverage:indiaCodes[fields[3]]?'India · historical model':''}));
 for(const name of new Set(africa.map(x=>x.airline))){
  const match=catalog.find(({fields})=>(name!=='Airlink'||fields[4]==='South Africa')&&norm(fields[0])===norm(carrierAlias[name]||name));
  if(match)match.coverage='Southern Africa · historical fares';else catalog.push({fields:[name,'','','',''],coverage:'Southern Africa · historical fares'});
 }
 for(const name of Object.values(indiaCodes)){if(!catalog.some(r=>indiaCodes[r.fields[3]]===name))catalog.push({fields:[name,'','','','India'],coverage:'India · historical model'});}
 const anacCodes=new Set(Object.values(world.carriers).flatMap(g=>Object.keys(g)));
 for(const code of anacCodes){
  const item=catalog.find(r=>r.fields[3]===code);
  if(item)item.coverage=[item.coverage,'Brazil · international sales'].filter(Boolean).join(' / ');
  else catalog.push({fields:[code,'','',code,''],coverage:'Brazil · international sales'});
 }
 for(const r of catalog)r.search=norm(r.fields.join(' '));
 byId('dirInfo').textContent='Search '+catalog.length.toLocaleString()+' entries by airline, country or code.';
 byId('directorySearch').oninput=()=>{limit=20;drawDirectory();};byId('moreAirlines').onclick=()=>{limit+=50;drawDirectory();};drawDirectory();
 const list=byId('worldAirlines');if(list){const suggest=()=>{const q=norm(byId('worldCarrier').value);list.replaceChildren(...catalog.filter(r=>q&&r.search.includes(q)).slice(0,40).map(r=>new Option(r.fields[0],r.fields[0]+(r.fields[3]?' ('+r.fields[3]+')':''))));};byId('worldCarrier').oninput=suggest;}
}catch{byId('worldTitle').textContent='Historical fare data could not be loaded. Reload to try again.';}
