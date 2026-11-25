import {showNonstop} from './nonstop.js';
import {inRupees,exchangeNote,onRateChange} from './exchange.js';
const $=id=>document.getElementById(id);
const norm=value=>value.normalize('NFKD').replace(/[\u0300-\u036f]/g,'').toLowerCase().trim();
const continents={AF:'Africa',AS:'Asia',EU:'Europe',NA:'North America',SA:'South America',OC:'Oceania',AN:'Antarctica'};
const countries=new Intl.DisplayNames(['en'],{type:'region'});
const fareINR=amount=>inRupees(amount,'USD');
const airportLabel=a=>a[0]+' · '+a[1]+' · '+a[3];
const kmFormat=n=>Math.round(n).toLocaleString()+' km';
export function greatCircle(a,b){
 const rad=Math.PI/180, lat1=a[5]*rad,lat2=b[5]*rad;
 const h=Math.sin((lat2-lat1)/2)**2+Math.cos(lat1)*Math.cos(lat2)*Math.sin((a[6]-b[6])*rad/2)**2;
 return 12742*Math.asin(Math.sqrt(Math.min(1,Math.max(h,0))));
}
export function fareFor(model,a,b){
 const km=greatCircle(a,b),[slope,crossContinent]=model.fit.weights;
 return {km,price:Math.exp(model.fit.intercept+slope*Math.log(Math.max(1,km))+crossContinent*Number(a[4]!==b[4]))};
}
async function fetchData(name){
 const response=await fetch(new URL('./global/'+name+'.json',import.meta.url));
 if(!response.ok)throw Error('The '+name+' data could not be loaded.');
 return response.json();
}
try{
 const [airports,model,catalog]=await Promise.all(['airports','world-model','airlines'].map(fetchData));
 const codes=new Map(airports.map(a=>[a[0],a]));
 const searchable=airports.map(a=>({a,search:norm([a[0],a[1],a[2],a[3],countries.of(a[3]),continents[a[4]]].join(' '))})).sort((x,y)=>Number(y.a[7])-Number(x.a[7])||x.a[1].localeCompare(y.a[1]));
 function picker(id,listId){
  const input=$(id),list=$(listId);
  function suggestions(){
   const query=norm(input.value);
   const exact=codes.get(query.toUpperCase());
   const found=searchable.filter(r=>r.search.includes(query)&&r.a!==exact).slice(0,60).map(r=>r.a);
   if(exact)found.unshift(exact);
   list.replaceChildren(...found.map(a=>new Option((a[2]||a[1])+', '+countries.of(a[3]),airportLabel(a))));
  }
  input.addEventListener('input',suggestions);input.addEventListener('focus',suggestions);
  return ()=>{const v=input.value.trim();return codes.get(v.toUpperCase())||((v.includes(' · '))&&codes.get(v.split(' · ')[0].toUpperCase())&&airportLabel(codes.get(v.split(' · ')[0].toUpperCase()))===v?codes.get(v.split(' · ')[0].toUpperCase()):null);};
 }
 const from=picker('globalFrom','fromAirports'),to=picker('globalTo','toAirports');
 function marketCarrier(input,group){
  const value=norm(input);if(!value)return '';
  const explicit=value.match(/\(([a-z0-9]{3})\)$/)?.[1]||value;
  if(Object.hasOwn(group,explicit.toUpperCase()))return explicit.toUpperCase();
  return catalog.find(([name,alias,iata,icao])=>Object.hasOwn(group,icao)&&[name,alias,iata,icao].some(x=>x&&norm(x)===value))?.[3]||'';
 }
 let refreshResult=()=>{};
 function estimate(){
  const a=from(),b=to();
  if(!a||!b||a[0]===b[0]||a[3]===b[3]){
   $('flightWarning').textContent=!a||!b?'Choose both airports from the suggestions or type their exact three-letter codes.':'Choose airports in different countries for the international model.';
   showNonstop($('worldNonstop'));
   refreshResult=()=>{};$('worldFx').textContent='';$('globalPrice').textContent='—';$('worldRoute').textContent='Choose an international route';for(const id of ['worldKm','globalBasis','worldEvidence','worldContext'])$(id).textContent='';return;
  }
  const key=a[0]+'-'+b[0],{km,price}=fareFor(model,a,b),historical=model.known[key],group=model.carriers[key]||{};
  const chosen=$('worldCarrier').value.trim(),carrier=marketCarrier(chosen,group);
  $('flightWarning').textContent='';$('worldRoute').textContent=a[0]+' → '+b[0];
  showNonstop($('worldNonstop'),a[0],b[0]);
  $('worldKm').textContent=countries.of(a[3])+' → '+countries.of(b[3])+' · '+kmFormat(km)+' great-circle distance';
  refreshResult=()=>{
  $('worldFx').textContent=exchangeNote('USD');
  $('globalPrice').textContent=fareINR(price);$('globalBasis').textContent='Estimated one-way economy base fare · INR, excluding taxes and fees';
  const evidence=historical?'Recorded route. The seat-weighted median was '+fareINR(historical[0])+' across '+historical[1].toLocaleString()+' sold seats on this direction in 2024.':'Unseen route. This estimate transfers patterns learned from flights originating in Brazil. Accuracy on this route is unknown.';
  const preference=chosen?(carrier?' The recorded median for '+carrier+' was '+fareINR(group[carrier][0])+' across '+group[carrier][1].toLocaleString()+' seats.':' No matched carrier-specific fare records for '+chosen+' on this route.'):'';
  $('worldEvidence').textContent=evidence+preference;
  };
  refreshResult();
  const bounds=km<model.minKm||km>model.maxKm?' This distance is outside the training range.':'';
  const service=(!a[7]||!b[7])?' At least one airport has no scheduled service listed in the airport snapshot.':'';
  $('worldContext').textContent='Historical model estimate. Confirm current prices, travel dates and seat availability with the airline.'+bounds+service;
 }
 $('globalFrom').value=airportLabel(codes.get('DEL'));$('globalTo').value=airportLabel(codes.get('LHR'));
 $('globalForm').onsubmit=e=>{e.preventDefault();estimate();};$('globalForm').oninput=()=>{$('flightWarning').textContent='Select Estimate route fare to update the displayed result.';};
 $('reverseGlobal').onclick=()=>{const s=$('globalFrom').value;$('globalFrom').value=$('globalTo').value;$('globalTo').value=s;estimate();};
 $('globalSubmit').disabled=false;estimate();
 const regionCount=new Set(airports.map(a=>a[3])).size;
 const renderValidation=()=>{ $('worldValidation').textContent='The airport picker covers '+airports.length.toLocaleString()+' IATA codes across '+regionCount+' countries and territories. The model uses 2024 ANAC one-way economy sales from Brazil, covering '+model.seats.toLocaleString()+' seats on '+model.routes.toLocaleString()+' directional routes. It learned from '+model.trainingRoutes.toLocaleString()+' route medians supported by at least five seats. Five-fold validation kept entire airport pairs together. Average error on withheld route medians was '+fareINR(model.mae)+' versus '+fareINR(model.baselineMae)+' for a constant-median baseline. Errors for individual tickets and other origins may differ.';};
 renderValidation();onRateChange(()=>{refreshResult();renderValidation();});
 $('worldSources').innerHTML='Sources: <a href="https://sas.anac.gov.br/sas/tarifainternacional/2024/">ANAC international tariff records</a> · <a href="https://ourairports.com/data/">OurAirports geographic data</a>.';
}catch(e){$('worldRoute').textContent='Worldwide estimator unavailable';$('flightWarning').textContent=e.message+' Reload the page to retry.';}
