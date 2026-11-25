// Directional outbound routes. A missing airport is outside the index's coverage.
const index = fetch(new URL('./global/nonstop.json',import.meta.url))
 .then(response=>response.ok?response.json():null).catch(()=>null);
const active = new WeakMap();
export async function showNonstop(panel,from,to){
 const request=Symbol();
 active.set(panel,request);
 panel.hidden=!from||!to;
 panel.replaceChildren();
 if(panel.hidden)return;
 panel.textContent='Checking nonstop service…';
 const data=await index;
 if(active.get(panel)!==request)return;
 const departures=data?.routes?.[from],arrival=data?.routes?.[to];
 const listed=Array.isArray(departures)&&departures.includes(to);
 const covered=departures?.length>0&&Array.isArray(arrival);
 const title=document.createElement('strong');
 title.textContent=listed?'Direct flight listed':covered?'No direct flight listed for this route':'Direct-flight status unknown';
 panel.dataset.status=listed?'listed':covered?'absent':'unknown';
 const detail=document.createElement('small');
 detail.textContent=listed?'Nonstop service is listed for this direction. Check your travel date with the airline.':covered?'You may need a connecting flight.':'Route coverage is incomplete for these airports.';
 panel.replaceChildren(title,detail);
 if(data?.date){
  const source=document.createElement('a');
  source.href='https://github.com/Jonty/airline-route-data/blob/ff16a0749fd642e469a5f561a984e77ae3740b7f/README.md';
  source.textContent='Route directory · '+new Intl.DateTimeFormat('en-IN',{dateStyle:'medium',timeZone:'UTC'}).format(new Date(data.date+'T00:00:00Z'));
  detail.append(' ',source);
 }
}
