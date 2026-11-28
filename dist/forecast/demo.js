const host = document.querySelector('#lab');
async function showStudy(){
  const section = document.createElement('section');
  section.className='card info directory';
  const heading=document.createElement('h3');
  heading.textContent='Next-day fare study';
  section.append(heading);
  const get = async file => {const response=await fetch(new URL(file,import.meta.url));if(!response.ok)throw Error();return response.json();};
  const [report,model]=await Promise.all([get('evaluation.json'),get('model.json')]);
  const summary=document.createElement('p');
  summary.textContent='Historical U.S. nonstop fares, in USD. The next-day model and the unchanged-fare baseline both had a mean absolute error of $'+report.test.modelMAE.toFixed(2)+' across '+report.test.pairs+' held-out quote pairs on '+report.testSearch[0]+'.';
  const label=document.createElement('label'),select=document.createElement('select'),out=document.createElement('p');
  label.textContent='Explore a held-out itinerary';
  report.examples.forEach((x,i)=>select.add(new Option(x.route+' · departure '+x.departure,i)));
  function render(){
    const ex=report.examples[Number(select.value)];
    let delta=model.initial;
    for(const tree of model.trees){
      let node=tree[0];
      while(node.length>1)node=tree[ex.features[node[0]]<=node[1]?node[2]:node[3]];
      delta+=model.rate*node[0];
    }
    out.textContent='Quoted $'+ex.features[0].toFixed(2)+' · Next-day estimate $'+Math.max(0,ex.features[0]+delta).toFixed(2)+' · Observed next day $'+ex.actual.toFixed(2);
  }
  select.onchange=render;label.append(select);out.setAttribute('aria-live','polite');render();
  section.append(summary,label,out);host.append(section);
}
if(host)showStudy().catch(()=>{});
