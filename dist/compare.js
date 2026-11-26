export function compareAirlines(engine, route, days) {
  const carriers = new Map();
  for (const profile of engine.options) {
    if (profile.source_city !== route.from || profile.destination_city !== route.to || profile.class !== route.cabin) continue;
    if (!carriers.has(profile.airline)) carriers.set(profile.airline, null);
    if (days < profile.daysMin || days > profile.daysMax) continue;
    const record = {...profile, duration: profile.durationMedian, days_left: days};
    const {price} = engine.predict(record);
    const best = carriers.get(profile.airline);
    if (!best || price < best.price) carriers.set(profile.airline, {record, price});
  }
  return [...carriers].sort(([a,x], [b,y]) => (x?.price ?? Infinity) - (y?.price ?? Infinity) || a.localeCompare(b));
}

const logoCodes = {Indigo:'6E',Air_India:'AI',SpiceJet:'SG',Vistara:'UK',GO_FIRST:'G8',AirAsia:'I5'};
const names = {Indigo:'IndiGo',Air_India:'Air India',GO_FIRST:'Go First',AirAsia:'AirAsia India'};
const stopNames = {zero:'Nonstop',one:'1 stop',two_or_more:'2+ stops'};
const money = new Intl.NumberFormat('en-IN',{style:'currency',currency:'INR',maximumFractionDigits:0});
const el = id => document.getElementById(id);
function node(tag, text, className) {
  const element = document.createElement(tag);
  if (text) element.textContent = text;
  if (className) element.className = className;
  return element;
}
export function setupComparison(engine, codes, inspect) {
  const from = el('compareFrom'), to = el('compareTo'), cabin = el('compareCabin'), days = el('compareDays');
  function selectValues(select, values, preferred) {
    const choices = [...new Set(values)].sort();
    select.replaceChildren(...choices.map(value => new Option(codes[value] ? value+' ('+codes[value]+')' : value,value)));
    select.value = choices.includes(preferred) ? preferred : choices[0];
  }
  function setRoute(origin, destination) {
    from.value = origin;
    const routes = engine.options.filter(row => row.source_city === origin);
    selectValues(to,routes.map(row => row.destination_city),destination);
    const profiles = routes.filter(row => row.destination_city === to.value);
    selectValues(cabin,profiles.map(row => row.class),cabin.value || 'Economy');
  }
  function compare() {
    if (!el('compareForm').reportValidity()) return;
    const results = compareAirlines(engine,{from:from.value,to:to.value,cabin:cabin.value},days.valueAsNumber);
    const supported = results.filter(([,best]) => best).length;
    const lowest = results.find(([,best]) => best)?.[1]?.price;
    const highest = Math.max(...results.map(([,best]) => best?.price || 0));
    const sort = el('compareSort').value;
    if (sort !== 'price') results.sort(([a,x],[b,y]) => {
      if (!x || !y) return Number(Boolean(y)) - Number(Boolean(x));
      if (sort === 'duration') return x.record.duration-y.record.duration || x.price-y.price;
      return (names[a] || a).localeCompare(names[b] || b);
    });
    el('compareTitle').textContent = from.value+' → '+to.value;
    el('compareMeta').textContent = cabin.value+' · '+days.value+' days ahead · '+supported+' of '+results.length+' airlines with an estimate';
    const rows = results.map(([airline,best]) => {
      const row = node('article',null,'fare-row');
      const mark = node('div',null,'fare-mark'), code = logoCodes[airline];
      mark.setAttribute('aria-hidden','true');
      if (code) {
        const image = new Image();
        image.alt = '';
        image.onerror = () => mark.replaceChildren(code);
        image.src = new URL('./airline-logos/'+code+'.png',import.meta.url);
        mark.append(image);
      }
      const info = node('div'), amount = node('div',null,'compare-amount');
      info.append(node('h4',names[airline] || airline));
      if (best) {
        const r = best.record, minutes = Math.round(r.duration*60);
        info.append(node('p',stopNames[r.stops]+' · '+Math.floor(minutes/60)+'h '+minutes%60+'m · '+r.departure_time.replaceAll('_',' ').toLowerCase()+' departure'));
        if (best.price === lowest && supported > 1) {
          row.classList.add('best-fare');
          info.querySelector('h4').append(node('span','Lowest fare','lowest-label'));
        }
        const bar = node('span',null,'fare-meter');
        bar.setAttribute('aria-hidden','true');
        bar.style.setProperty('--fare-ratio',String(best.price / highest));
        const details = node('button','Fare details');
        details.type = 'button';
        details.setAttribute('aria-label','View fare details for '+(names[airline] || airline));
        details.onclick = () => inspect(r);
        amount.append(node('strong',money.format(best.price)),bar,details);
      } else {
        info.append(node('p','No supported itinerary at this booking lead time.'));
        amount.append(node('span','Unavailable'));
      }
      row.append(mark,info,amount);
      return row;
    });
    el('compareList').replaceChildren(...rows);
  }
  selectValues(from,engine.options.map(row => row.source_city),'Delhi');
  setRoute(from.value,'Mumbai');
  days.min = Math.min(...engine.options.map(row => row.daysMin));
  days.max = Math.max(...engine.options.map(row => row.daysMax));
  el('compareButton').disabled = false;
  el('compareForm').onsubmit = event => {event.preventDefault();compare();};
  from.onchange = to.onchange = () => {setRoute(from.value,to.value);compare();};
  cabin.onchange = compare;
  el('compareSort').onchange = compare;
  days.oninput = () => {el('compareList').replaceChildren();el('compareMeta').textContent='Select Compare fares to update the estimates.';};
  el('compareSwap').onclick = () => {setRoute(to.value,from.value);compare();};
  compare();
}
