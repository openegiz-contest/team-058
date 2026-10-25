'use strict';
const $=id=>document.getElementById(id);
const state={page:'operations',frame:null,report:null,config:null,connected:null,assets:null,demo:false,advice:null,scenario:null,selected:null,assetTab:'trucks',scenarioKind:'shovel_outage',scenarioError:null,refreshing:false,applyPending:false,chosenPolicy:null};
const n=(v,d=0)=>Number(v??0).toLocaleString('en-US',{maximumFractionDigits:d,minimumFractionDigits:d});
const pct=v=>Number(v??0).toFixed(1)+'%';
const fmtTime=m=>'Day '+(Math.floor(m/1440)+1)+' · '+String(Math.floor(((m%1440)+1440)%1440/60)).padStart(2,'0')+':'+String(Math.floor(((m%1440)+1440)%60)).padStart(2,'0');
const esc=s=>String(s??'—').replace(/[&<>"']/g,c=>({'&':'&amp;','<':'&lt;','>':'&gt;','"':'&quot;',"'":'&#39;'}[c]));
let mapRouteView='active'; // Presentation-only: 'active', 'all', 'issues'; never changes dispatch
const policyNames={nearest:'Nearest route',balanced:'Queue-aware',smart:'OreFlow optimizer'};
const prettyStatus={queue_load:'Load queue',queue_dump:'Dump queue',queue_fuel:'Fuel queue',shift_change:'Shift relief',to_fuel:'Driving to fuel',hauling:'Hauling loaded',returning:'Returning empty',loading:'Loading',unloading:'Unloading',refueling:'Refueling',outbound:'To shovel',maintenance:'Maintenance',idle:'Idle'};
const colors={hauling:'#6cb9f1',returning:'#5acfd1',loading:'#59dab3',queue_load:'#efa969',queue_fuel:'#f4b36c',unloading:'#c4a5e8',refueling:'#8eb7fa',maintenance:'#ee7e85',idle:'#8b9aab'};
function say(message){const node=$('toast');node.textContent=message;node.style.display='block';clearTimeout(say.timer);say.timer=setTimeout(()=>node.style.display='none',3600)}
async function req(path,options={}){const response=await fetch(path,{cache:'no-store',...options});let data;try{data=await response.json()}catch(e){throw Error('Invalid API response')};if(!response.ok||data.error)throw Error(data.error||`API error ${response.status}`);return data}
function post(path,body){return req(path,{method:'POST',headers:{'Content-Type':'application/json'},body:JSON.stringify(body)})}
function nav(page){state.page=page;document.querySelectorAll('.page').forEach(el=>el.classList.toggle('active',el.id==='page-'+page));document.querySelectorAll('#nav button').forEach(el=>el.classList.toggle('active',el.dataset.page===page));$('pageCrumb').textContent=page==='equipment'?'EQUIPMENT':page.toUpperCase();$('simControls').style.display=page==='operations'?'flex':'none';window.scrollTo(0,0);renderPage()}
function kpi(label,value,note){return `<div class="kpi"><span class="kpi-title">${esc(label)}</span><strong>${esc(value)}</strong><small>${esc(note)}</small></div>`}
function barRow(label,v,max,color='#64cada',suffix=''){const frac=Math.max(0,Math.min(100,Number(v||0)/Math.max(1,max)*100));return `<div class="bar-row"><span>${esc(label)}</span><div class="bar-track"><div class="bar-fill" style="width:${frac}%;background:${color}"></div></div><b>${n(v)}${suffix}</b></div>`}
function seriesChart(series,key='delivered_t',compare=null){if(!series||!series.length)return '<div class="placeholder compact">No event records available.</div>';const data=series.slice(-24);const mx=Math.max(1,...data.map(x=>Number(x[key]||0)),...(compare||[]).map(x=>Number(x[key]||0)));const W=670,H=180,top=14,bot=153,left=25,right=658,width=(right-left)/Math.max(1,data.length);let svg=`<svg viewBox="0 0 ${W} ${H}" preserveAspectRatio="none" role="img" aria-label="Measured simulated hourly ${key}">`;
 for(let j=0;j<=3;j++){let y=top+(bot-top)*j/3;svg+=`<line class="gridline" x1="${left}" y1="${y}" x2="${right}" y2="${y}"/><text x="3" y="${y+3}">${n(mx*(3-j)/3)}</text>`}
 for(let i=0;i<data.length;i++){let v=Number(data[i][key]||0),h=v/mx*(bot-top);const x=left+i*width+3;const bw=compare?Math.max(2,width*.39):Math.max(2,width-6);svg+=`<rect x="${x.toFixed(2)}" y="${(bot-h).toFixed(2)}" width="${bw.toFixed(2)}" height="${h.toFixed(2)}" rx="2.2" fill="#62bde9"><title>${n(v,1)} ${key==='fuel_l'?'L':'t'}</title></rect>`;if(compare){let other=Number(compare[i]?.[key]||0),h2=other/mx*(bot-top);svg+=`<rect x="${(x+width*.44).toFixed(2)}" y="${(bot-h2).toFixed(2)}" width="${Math.max(2,width*.39).toFixed(2)}" height="${h2.toFixed(2)}" fill="#efb568" rx="1"><title>${n(other,1)} comparison</title></rect>`}}
 svg+=`<text x="${left}" y="174">Start</text><text x="${(left+right)/2-28}" y="174">${data.length} recorded hourly bins</text><text x="${right-27}" y="174">End</text></svg>`;return svg}
function threeOutcomeBars(rows){
 const mx=Math.max(1,...rows.map(r=>r.tonnes));return `<div class="tri-outcomes">${rows.map(r=>`<div class="tri-outcome"><div class="tri-title" style="color:${r.color}">${esc(r.name)}</div><strong>${n(r.tonnes)} t</strong><div class="tri-track"><i style="background:${r.color};width:${Math.max(.2,r.tonnes/mx*100)}%"></i></div><small>${n(r.fuel_l)} L · ${n(r.waiting_truck_hours,1)} waiting h</small></div>`).join('')}</div>`
}
function scenarioMiniMap(sample,label){
 if(!sample||!state.config)return '';
 const assets=sample.assets||{};
 const loads=state.config.load_sites.map((v,i)=>({id:'L'+i,p:position(...v.position)}));
 const dumps=state.config.dump_sites.map((v,i)=>({id:'D'+i,p:position(...v.position)}));
 const sitePoints=Object.fromEntries([...loads,...dumps].map(o=>[o.id,o.p]));
 const affected=new Set(sample.affected||[]);
 const used={};for(const t of sample.trucks||[]){const a=(t.route||'').split(/\s*→\s*/);if(a.length===2&&a[0]!==a[1])used[a[0]+'->'+a[1]]=(used[a[0]+'->'+a[1]]||0)+1}
 let svg=`<svg viewBox="0 0 960 450" role="img" aria-label="${esc(label)}: modeled mine routes and equipment states"><defs><pattern id="sm-grid-${esc(label.replace(/\W/g,''))}" width="38" height="38" patternUnits="userSpaceOnUse"><path d="M38 0H0V38" fill="none" stroke="#24475b" stroke-width=".7"/></pattern></defs><rect width="960" height="450" fill="#0c2436"/><rect width="960" height="450" fill="url(#sm-grid-${esc(label.replace(/\W/g,''))})"/>`;
 for(const a of loads)for(const b of dumps){const key=a.id+'->'+b.id,rev=b.id+'->'+a.id;
  const forward=assets.roads?.[key]?.state||'open', backward=assets.roads?.[rev]?.state||'open';
  const broken=forward==='closed'||backward==='closed';const degraded=forward==='degraded'||backward==='degraded';const active=(used[key]||0)+(used[rev]||0)>0;
  if(!active&&!broken&&!degraded)continue;
  svg+=`<path d="M${a.p[0]} ${a.p[1]}L${b.p[0]} ${b.p[1]}" stroke="${broken?'#ff757b':degraded?'#f3ae64':'#3c9eb2'}" stroke-width="${broken?'6':active?'2.8':'2'}" stroke-dasharray="${broken?'11 9':degraded?'5 5':''}" opacity="${active||broken?'.92':'.7'}"><title>${esc(key)}: ${esc(forward)}; return: ${esc(backward)}</title></path>`;
 }
 for(const a of loads){const shovelDown=Object.values(assets.shovels||{}).filter(x=>x.site===a.id&&x.state==='failed').length;svg+=`<g><circle cx="${a.p[0]}" cy="${a.p[1]}" r="${shovelDown?18:13}" fill="#204a65" stroke="${shovelDown?'#ff747c':'#78d2ed'}" stroke-width="${shovelDown?4:2}"/><text x="${a.p[0]+18}" y="${a.p[1]+6}" fill="#d8efff" font-size="17" font-weight="700">${a.id}${shovelDown?' !':''}</text></g>`}
 for(const a of dumps)svg+=`<g><rect x="${a.p[0]-12}" y="${a.p[1]-12}" width="24" height="24" rx="5" fill="#473c2e" stroke="#fac487" stroke-width="2"/><text x="${a.p[0]+18}" y="${a.p[1]+6}" fill="#f0e2c9" font-size="17" font-weight="700">${a.id}</text></g>`;
 for(const id of ['L0','L3']){const a=sitePoints[id],st=assets.fuel_stations?.[id]?.state||'available';if(a)svg+=`<g><rect x="${a[0]-25}" y="${a[1]-38}" width="51" height="19" rx="4" fill="${st==='unavailable'?'#72373e':'#205c6c'}" stroke="${st==='unavailable'?'#ff737a':'#65d6dc'}"/><text x="${a[0]-21}" y="${a[1]-24}" font-size="12" fill="white">FUEL</text></g>`}
 // Positions come from the scenario branch, never interpolated guesses.
 const grouped={};for(const tr of sample.trucks||[]){const [x,y]=position(tr.x,tr.y),key=`${Math.round(x/8)},${Math.round(y/8)}`,j=grouped[key]||0;grouped[key]=j+1;const angle=j*2.39996,r=j?8+Math.sqrt(j)*4:0;const px=x+Math.cos(angle)*r,py=y+Math.sin(angle)*r;const focus=affected.has(tr.id);svg+=`<circle cx="${px.toFixed(1)}" cy="${py.toFixed(1)}" r="${focus?7.2:3.8}" fill="${focus?'#ff777d':tr.capacity===77?'#8fd3ff':tr.capacity===55?'#ffd08c':'#68e4c7'}" stroke="#0b1c2b" stroke-width="1.4"><title>${esc(tr.id)} · ${esc(tr.status)}</title></circle>`}
 svg+='</svg>';
 const unavailable=Object.values(assets.shovels||{}).filter(x=>x.state==='failed').length+Object.values(assets.fuel_stations||{}).filter(x=>x.state==='unavailable').length;
 return `<div class="scenario-map"><div class="scenario-map-header"><strong>${esc(label)}</strong><span>${(sample.trucks||[]).length} trucks · ${unavailable} unavailable assets</span></div>${svg}<div class="scenario-map-key"><i class="key-dot" style="background:#ff757b"></i> outage / affected &nbsp; <i class="key-dot" style="background:#78d2ed"></i> loading &nbsp; <i class="key-dot" style="background:#fac487"></i> dump</div></div>`;
}
function threeWayProductionChart(normal,disrupted,recovery){
 const all=[normal||[],disrupted||[],recovery||[]].map(a=>a.slice());const length=Math.max(...all.map(a=>a.length),0);
 if(!length)return '<div class="placeholder compact">No hourly results returned by the simulation.</div>';
 const max=Math.max(1,...all.flatMap(a=>a.map(x=>Number(x.delivered_t||0))));
 const W=720,H=210,L=53,R=706,T=14,B=171;
 let svg=`<svg class="triple-line-chart" viewBox="0 0 ${W} ${H}" preserveAspectRatio="xMidYMid meet" role="img" aria-label="Hourly delivery tonnes: normal, disrupted and recovery simulation"><title>Calculated hourly deliveries for normal, disrupted and recovery branches</title>`;
 for(let i=0;i<=4;i++){const yy=B-(B-T)*i/4;svg+=`<line x1="${L}" y1="${yy}" x2="${R}" y2="${yy}" stroke="#294c60"/><text x="5" y="${yy+4}" fill="#9abacc" font-size="12">${n(max*i/4)}</text>`}
 for(let i=0;i<length;i+=Math.max(1,Math.floor(length/6))){const xx=L+(R-L)*(length===1?.5:i/(length-1));svg+=`<text x="${xx}" y="195" text-anchor="middle" fill="#96bacc" font-size="11">+${i+1}h</text>`}
 [['Normal','#64c7ee'],['Disrupted','#f0a274'],['Recovery','#6fe1b9']].forEach(([name,color],idx)=>{
  const a=all[idx];if(!a.length)return;const points=a.map((o,i)=>`${L+(R-L)*(length===1?.5:i/(length-1))},${B-(B-T)*Number(o.delivered_t||0)/max}`).join(' ');
  svg+=`<polyline points="${points}" fill="none" stroke="${color}" stroke-width="3" stroke-linejoin="round" stroke-linecap="round"><title>${name}: ${a.length} hourly simulated values</title></polyline>`;
  for(let i=0;i<a.length;i++){const x=L+(R-L)*(length===1?.5:i/(length-1)),y=B-(B-T)*Number(a[i].delivered_t||0)/max;svg+=`<circle cx="${x}" cy="${y}" r="2.8" fill="${color}"><title>${name} hour ${i+1}: ${n(a[i].delivered_t,1)} tonnes</title></circle>`}
 });return svg+'</svg><div class="outcome-legend"><span><i style="background:#64c7ee"></i> Normal</span><span><i style="background:#f0a274"></i> Disrupted</span><span><i style="background:#6fe1b9"></i> Recovery</span></div>';
}
function position(x,y){return [60+Number(x)*780,402-Number(y)*344]}
function map(){
 const {frame,config}=state;if(!frame||!config)return;
 const loads=config.load_sites.map((node,i)=>({id:'L'+i,point:position(...node.position),type:'load'}));
 const dumps=config.dump_sites.map((node,i)=>({id:'D'+i,point:position(...node.position),type:'dump'}));
 const dep=position(...config.charging_site.position);
 const points=Object.fromEntries([...loads,...dumps,{id:'C',point:dep}].map(x=>[x.id,x.point]));
 const activeRoads={};for(const tr of frame.trucks||[]){const found=(tr.route||'').match(/^([CLD]\d*)\s*→\s*([CLD]\d*)$/);if(found&&found[1]!==found[2]){const key=found[1]+'->'+found[2];activeRoads[key]=(activeRoads[key]||0)+1}}
 const roadAssets=state.assets?.roads||{};let visible=0,problem=0;
 let html=`<defs><pattern id="network-grid" width="32" height="32" patternUnits="userSpaceOnUse"><path d="M32 0H0V32" fill="none" stroke="#25495e" stroke-width=".7"/></pattern><marker id="routeArrow" markerWidth="7" markerHeight="7" refX="5.5" refY="3.5" orient="auto"><path d="M0 0L7 3.5L0 7Z" fill="#58bace"/></marker></defs><rect width="960" height="450" fill="#0c2538"/><rect width="960" height="450" fill="url(#network-grid)"/>`;
 // Complete directed road data comes from the API, never from fabricated geometry.
 for(const road of Object.values(roadAssets)){
  const a=points[road.from],b=points[road.to];if(!a||!b)continue;
  const count=activeRoads[road.from+'->'+road.to]||0;
  const broken=['closed','degraded','unavailable'].includes(road.state);
  if(broken)problem++;
  if(mapRouteView==='active'&&!count&&!broken || mapRouteView==='issues'&&!broken)continue;
  const reverse=roadAssets[road.to+'->'+road.from];const twoWay=Boolean(reverse);const dx=b[0]-a[0],dy=b[1]-a[1],len=Math.hypot(dx,dy)||1;
  const perpendicular=twoWay?3.5:0,offsetX=-dy/len*perpendicular,offsetY=dx/len*perpendicular;
  const x1=a[0]+dx*.08+offsetX,y1=a[1]+dy*.08+offsetY,x2=b[0]-dx*.11+offsetX,y2=b[1]-dy*.11+offsetY;
  const col=road.state==='closed'?'#f77480':road.state==='degraded'?'#f6b66c':count?'#65bdcf':'#386b80';
  const op=broken?'.98':count?'.8':'.16', width=broken?4.6:count?Math.min(4,1.5+count*.4):.9;
  html+=`<path class="map-road ${broken?'map-road-alert':count?'map-road-active':''}" data-road="${esc(road.from+'->'+road.to)}" d="M${x1.toFixed(1)} ${y1.toFixed(1)}L${x2.toFixed(1)} ${y2.toFixed(1)}" stroke="${col}" stroke-width="${width}" opacity="${op}" stroke-dasharray="${road.state==='closed'?'9 6':road.state==='degraded'?'3 6':''}" fill="none" ${count&&!broken?'marker-end="url(#routeArrow)"':''}><title>${esc(road.from)} → ${esc(road.to)} · ${esc(road.state)} · ${n(road.length_km,2)} km · ${count} trucks assigned</title></path>`;
  visible++;
 }
 const noRoutes=mapRouteView==='issues'&&!problem;
 if(noRoutes)html+=`<g class="map-no-alerts"><rect x="355" y="9" width="250" height="27" rx="13" fill="#183f4b"/><text x="480" y="27" text-anchor="middle" fill="#9de9cd" font-size="13">No road closures or restrictions</text></g>`;
 // Real load-site queues from frame.sites are distinguished from failed equipment.
 for(const item of [...loads,...dumps]){
  const load=item.type==='load', queue=load?Number(frame.sites?.[item.id]?.queue||0):0;
  const failed=load&&Object.values(state.assets?.shovels||{}).some(s=>s.site===item.id&&s.state==='failed');
  html+=`<g class="map-node" data-node="${item.id}"><circle cx="${item.point[0]}" cy="${item.point[1]}" r="${load?16:14}" fill="${load?'#20455e':'#55432f'}" stroke="${failed?'#ff8088':load?'#7bd3e7':'#edc080'}" stroke-width="${failed?4:2.5}"/>`;
  html+=load?`<path d="M${item.point[0]-6} ${item.point[1]+4}v-8h12v8Z" fill="#8bdff0"/>`:`<path d="M${item.point[0]-7} ${item.point[1]-5}l7-5 7 5v10h-14Z" fill="#edc080"/>`;
  html+=`<text x="${item.point[0]+22}" y="${item.point[1]+6}" fill="#e9f4fa" font-size="15" font-weight="800">${item.id}</text>`;
  if(queue>0){const bx=item.point[0]-15,by=item.point[1]-21;html+=`<circle cx="${bx}" cy="${by}" r="12.5" fill="${queue>=8?'#b95f33':'#255e74'}" stroke="#d9f6ff" stroke-width="1.5"/><text x="${bx}" y="${by+4.5}" fill="white" font-size="12" font-weight="800" text-anchor="middle">${queue}</text>`}
  if(failed)html+=`<circle cx="${item.point[0]}" cy="${item.point[1]}" r="24" fill="none" stroke="#ff777e" stroke-width="2.2" stroke-dasharray="5 4"/>`;
  html+=`<title>${load?'Loading site':'Dump site'} ${item.id}${queue?` · ${queue} waiting`:''}${failed?' · shovel failure':''}</title></g>`;
 }
 html+=`<g class="map-node" data-node="C"><circle cx="${dep[0]}" cy="${dep[1]}" r="12" fill="#245b5d" stroke="#74daca" stroke-width="2.5"/><text x="${dep[0]+19}" y="${dep[1]+4}" fill="#d6ffec" font-size="12" font-weight="800">DEPOT</text></g>`;
 // Shovels are selectable and show failed/working/available state independently.
 for(const [li,site] of config.load_sites.entries()){
  const p=loads[li].point;
  site.shovels.forEach((sh,j)=>{
   const id=`shovel-${li+1}-${j+1}`,st=state.assets?.shovels?.[id]?.state||'unknown';
   const phi=j*2.39996,radius=30+Math.floor(j/6)*14;
   const x=p[0]+Math.cos(phi)*radius,y=p[1]+Math.sin(phi)*radius;
   const broken=st==='failed',loading=st==='loading';
   html+=`<g class="map-shovel" data-shovel="${id}"><rect x="${x-6}" y="${y-6}" width="12" height="12" rx="2" transform="rotate(45 ${x} ${y})" fill="${broken?'#c95463':loading?'#e8b76b':'#58bba2'}" stroke="${broken?'#ffd4d5':'#102638'}" stroke-width="1.8"/>${broken?`<path d="M${x-4} ${y-4}l8 8m0-8l-8 8" stroke="white" stroke-width="2"/>`:''}<title>${esc(id)} · ${esc(st)}</title></g>`;
  });
 }
 for(const id of ['L0','L3']){const p=loads.find(x=>x.id===id)?.point;if(!p)continue;const fs=state.assets?.fuel_stations?.[id]||{};const down=fs.state==='unavailable',waiting=fs.waiting_trucks||0;
  html+=`<g class="map-node" data-node="fuel-${id}"><rect x="${p[0]+19}" y="${p[1]-37}" width="82" height="22" rx="5" fill="${down?'#6b333e':'#206276'}" stroke="${down?'#ff8589':'#77deed'}" stroke-width="1.5"/><text x="${p[0]+26}" y="${p[1]-22}" fill="#f5fcff" font-size="11" font-weight="750">FUEL ${id}${waiting?' · '+waiting+' wait':''}</text><title>Fuel ${id} · ${esc(fs.state||'unknown')} · ${waiting} waiting</title></g>`;
 }
 const occupied=[];
 for(const tr of frame.trucks){const [ox,oy]=position(tr.x,tr.y);let x=ox,y=oy;
  for(let j=0;j<150;j++){if(!occupied.some(p=>(p[0]-x)**2+(p[1]-y)**2<192))break;const phi=j*2.39996,rad=14+Math.sqrt(j)*6;x=Math.max(10,Math.min(950,ox+Math.cos(phi)*rad));y=Math.max(12,Math.min(438,oy+Math.sin(phi)*rad))}
  occupied.push([x,y]);const selected=state.selected?.id===tr.id;const vehicleColor=tr.capacity===77?'#8ecfff':tr.capacity===55?'#ffc27f':'#62e1c5';const problemState=['maintenance','queue_load','queue_fuel','queue_dump'].includes(tr.status);const travelling=['hauling','returning','outbound','to_fuel'].includes(tr.status);
  html+=`<g class="map-truck map-truck-group ${selected?'selected':''}" tabindex="0" role="button" data-truck="${esc(tr.id)}" aria-label="Inspect ${esc(tr.id)}"><circle cx="${x.toFixed(1)}" cy="${y.toFixed(1)}" r="${selected?10:problemState?8.6:7.5}" fill="#092438" stroke="${problemState?'#f1ad6c':selected?'#f8f5d3':'#42768a'}" stroke-width="${selected?3:1.3}"/>${travelling?`<path d="M${(x-4).toFixed(1)} ${(y-3).toFixed(1)}h8v6h-8z" fill="${vehicleColor}"/><path d="M${(x+1).toFixed(1)} ${(y-2).toFixed(1)}l5 2-5 2" fill="${vehicleColor}"/>`:`<circle cx="${x.toFixed(1)}" cy="${y.toFixed(1)}" r="3.9" fill="${vehicleColor}"/>`}<title>${esc(tr.id)} · ${esc(prettyStatus[tr.status]||tr.status)} · ${tr.capacity} tonnes</title></g>`;
 }
 const svg=$('mapSvg');svg.innerHTML=html;
 svg.querySelectorAll('[data-truck]').forEach(el=>{const open=()=>assetDrawer('truck',el.dataset.truck);el.onclick=open;el.onkeydown=e=>{if(e.key==='Enter'||e.key===' '){e.preventDefault();open()}}});
 svg.querySelectorAll('[data-node]').forEach(el=>el.onclick=()=>assetDrawer('node',el.dataset.node));
 svg.querySelectorAll('[data-shovel]').forEach(el=>el.onclick=()=>assetDrawer('shovel',el.dataset.shovel));
 svg.querySelectorAll('[data-road]').forEach(el=>el.onclick=()=>assetDrawer('road',el.dataset.road));
 if($('mapRouteInfo'))$('mapRouteInfo').textContent=`${visible} roads shown · ${Object.keys(activeRoads).length} routes with assigned trucks · ${problem} restricted`;
}
function assetDrawer(kind,id){const f=state.frame;if(!f)return;let html='';if(kind==='truck'){const t=f.trucks.find(x=>x.id===id);if(!t)return;html=`<h3>${esc(t.id)} · ${n(t.capacity)}t</h3><p>${esc(prettyStatus[t.status]||t.status)} · ${esc(t.route)}</p><div class="asset-data">${[['Payload',n(t.payload)+'t'],['Fuel',n(t.fuel_l,1)+' / '+n(t.tank_l)+' L'],['Fuel level',pct(t.fuel_pct)],['Assignment',t.current_destination],['Speed setting',n(t.speed)+' km/h'],['Route progress',pct(t.progress*100)]].map(([a,b])=>`<div><small>${esc(a)}</small><b>${esc(b)}</b></div>`).join('')}</div>`}else if(kind==='shovel'){
 const info=state.assets?.shovels?.[id];
 html=`<h3>${esc(id)}</h3><p>${esc(info?.state||'unknown')} · ${esc(info?.site||'loading site')}</p><div class="asset-data"><div><small>Bucket</small><b>${n(info?.bucket_t,1)} t</b></div><div><small>Cycle time</small><b>${n(info?.cycle_min,1)} min</b></div></div>`
 }else if(kind==='road'){const road=state.assets?.roads?.[id]||{};const count=state.frame.trucks.filter(t=>t.route.replace(/\s*→\s*/g,'->')===id).length;html=`<h3>Road ${esc(id.replace('->',' → '))}</h3><p>${esc(road.state||'unknown')} · directed connection</p><div class="asset-data"><div><small>Configured length</small><b>${n(road.length_km,2)} km</b></div><div><small>Trucks on route</small><b>${count}</b></div><div><small>Current status</small><b>${esc(road.state||'unknown')}</b></div></div>`;}else if(id.startsWith('fuel-')){const key=id.substring(5),trucks=f.trucks.filter(t=>t.current_destination===key&&['refueling','queue_fuel','to_fuel'].includes(t.status));
 const ref=trucks.filter(t=>t.status==='refueling').length,queue=trucks.filter(t=>t.status==='queue_fuel').length,inbound=trucks.filter(t=>t.status==='to_fuel').length;
 html=`<h3>Fuel station ${esc(key)}</h3><p>Refueling operations · model assumption</p><div class="asset-data"><div><small>Refueling now</small><b>${ref} trucks</b></div><div><small>Waiting</small><b>${queue} trucks</b></div><div><small>Driving to station</small><b>${inbound}</b></div><div><small>Pump capacity</small><b>2 modeled pumps</b></div></div><p style="margin-top:17px">Station-specific fuel dispensed and pump occupancy history are not reported by the current API. No estimates are invented.</p>`}else{const row=f.sites?.[id];html=`<h3>${esc(id==='C'?'Depot':id.startsWith('L')?'Loading site '+id:'Dumping site '+id)}</h3><p>${id.startsWith('L')?'Mine loading operations':id.startsWith('D')?'Ore unloading location':'Starting location'}</p>`+(row?`<div class="asset-data"><div><small>Queue</small><b>${row.queue}</b></div><div><small>Loading</small><b>${row.loading}</b></div></div>`:'')}
 state.selected={kind,id};
 const twinThing=(kind==='truck'||kind==='shovel')?id.toLowerCase():kind==='road'?'road-'+id.toLowerCase().replace('->','-'):id.startsWith('fuel-')?id.toLowerCase():id.startsWith('L')?'load-'+(Number(id.slice(1))+1):id.startsWith('D')?'dump-'+(Number(id.slice(1))+1):null;
 if(twinThing)html+='<div id="drawerDitto" class="detail-note">Reading stored equipment state from Ditto…</div>';
 $('assetContents').innerHTML=html;$('assetDrawer').classList.add('open');map();
 if(twinThing&&!state.demo)req('/api/ditto/'+twinThing).then(r=>{
  if(state.selected?.id!==id)return;
  const el=$('drawerDitto');if(!el)return;
  el.textContent=r.verified&&r.matches_active_run?'Ditto confirms the current simulation run · stored minute '+n(r.sim_minute,1):'Ditto readback not verified';
 }).catch(()=>{const el=$('drawerDitto');if(el)el.textContent='Ditto connection unavailable'});
}
function drawOperations(){const f=state.frame,r=state.report?.current;if(!f)return;const total=f.trucks?.length||0,queues=(f.states?.queue_load||0)+(f.states?.queue_fuel||0)+(f.states?.queue_dump||0),unavailable=(f.states?.maintenance||0)+(f.states?.shift_change||0)+(f.states?.idle||0);$('mainKpi').innerHTML=kpi('Delivered · since start',n(f.tonnes)+' t',`${n(f.completed_trips)} trips`)+kpi('Fleet available',`${total-unavailable} / ${total}`,'Excludes maintenance and relief')+kpi('Trucks waiting',n(queues),`Of ${total} vehicles`)+kpi('Modeled fuel · cumulative',n(f.fuel_used_l)+' L','Truck diesel estimate')+kpi('Fuel per tonne · past 24h',r?.fuel_l_per_t?n(r.fuel_l_per_t,3)+' L/t':'—','Based on event records');map();$('mapClock').textContent=fmtTime(f.minute);
 const alerts=f.alerts||[];$('issuesCount').textContent=alerts.length+' observed';$('issueList').innerHTML=alerts.length?alerts.slice(0,3).map(a=>`<div class="issue"><strong>⚑ ${esc(a.title)}</strong><p>${esc(a.message)}</p></div>`).join(''):'<div class="issue"><strong>No major queue alert</strong><p>Mine monitoring is active.</p></div>';
 const sites=Object.entries(f.sites||{});const mx=Math.max(1,...sites.map(x=>x[1].queue));$('queueBars').innerHTML=sites.map(([k,v])=>barRow(k,v.queue,mx,v.queue>=8?'#f5b16d':'#63c4d4')).join('');const sorted=Object.entries(f.states||{}).filter(([,x])=>x>0).sort((a,b)=>b[1]-a[1]).slice(0,6);$('fleetBars').innerHTML=sorted.map(([k,v])=>`<div class="statebar"><span>${esc(prettyStatus[k]||k)}</span><div class="bar-track"><div class="bar-fill" style="width:${v/Math.max(1,total)*100}%;background:${colors[k]||'#64bdd3'}"></div></div><strong>${v}</strong></div>`).join('');$('opsProduction').innerHTML=seriesChart(r?.hourly?.filter(x=>x.minute>=r.start_min-60&&x.minute<=r.end_min));
 const fuelStats=['L0','L3'].map(node=>({node,refueling:state.assets?.fuel_stations?.[node]?.refueling_trucks??0,waiting:state.assets?.fuel_stations?.[node]?.waiting_trucks??0,toFuel:state.assets?.fuel_stations?.[node]?.incoming_trucks??0,state:state.assets?.fuel_stations?.[node]?.state??'unknown'}));
 $('fuelCards').innerHTML=fuelStats.map(a=>`<button type="button" class="fuel-card" data-fuel="${a.node}"><strong>⛽ Fuel station ${a.node}</strong><small>${a.refueling} refueling · ${a.waiting} queuing · ${a.toFuel} driving to station</small><small>2 modeled pumps · see equipment details →</small></button>`).join('');
 $('fuelQuick').innerHTML=fuelStats.map(a=>`<button type="button" class="station-quick" data-station="${a.node}"><b>⛽ ${a.node}</b><span><strong>${a.refueling}</strong> refueling &nbsp; <strong>${a.waiting}</strong> waiting</span><span>${a.toFuel} inbound · 2 pumps</span></button>`).join('');
 document.querySelectorAll('#fuelCards [data-fuel]').forEach(el=>el.onclick=()=>assetDrawer('node','fuel-'+el.dataset.fuel));
 document.querySelectorAll('#fuelQuick [data-station]').forEach(el=>el.onclick=()=>assetDrawer('node','fuel-'+el.dataset.station));
}
function drawRecommendation(){const f=state.frame,alert=f?.alerts?.[0];$('recQueueBadge').textContent=alert?.site||'All sites';$('recBottleneck').innerHTML=alert?`<strong>⚑ ${esc(alert.title)}</strong>${esc(alert.message)}. Test whether another policy improves waiting without a production penalty.`:'<strong>Current monitoring</strong>No high-loading queue alert in the latest snapshot.';const a=state.advice;if(!a){$('recVerdict').innerHTML='<p>No dispatch comparison has been run in this session.</p>';$('planAction').innerHTML='';$('adviceDataLabel').textContent='NOT RUN';$('policyCharts').innerHTML='<p class="muted">Choose a forecast horizon and compare strategies.</p>';$('adviceTable').innerHTML='<p class="muted">No results yet.</p>';return}
 $('adviceHorizon').value=String(a.horizon_hours);$('adviceDataLabel').textContent=state.demo?'SAVED SIMULATOR RESULT':`FROM MINE · ${a.horizon_hours}H`;
 const goal=$('adviceGoal').value, current=a.options.find(x=>x.policy===a.current_policy);const result=goal==='production'?a.options.reduce((x,y)=>x.tonnes>=y.tonnes?x:y):goal==='fuel'?a.options.reduce((x,y)=>x.fuel_l_per_t<=y.fuel_l_per_t?x:y):a.options.find(x=>x.policy===a.recommended_policy);const bestTonnes=Math.max(...a.options.map(x=>x.tonnes));const other=a.options.find(x=>x.policy==='balanced');const queueNote=other&&other.policy!==result.policy?` Compared with queue-aware, this policy forecasts ${n(result.queue_truck_hours-other.queue_truck_hours,1)} additional truck-hours in queues.`:'';const reason=goal==='production'?'Highest forecast delivered tonnes. Fuel and waiting are shown separately.':goal==='fuel'?'Lowest modeled litres per tonne. Check the delivery penalty before adopting it.':a.reason; $('recVerdict').innerHTML=`<strong>${result.policy===a.current_policy?'Keep '+esc(policyNames[a.current_policy]):'Consider '+esc(policyNames[result.policy])}</strong><p>${esc(reason)} ${result.policy==='smart'&&other?esc('Queue-aware saves '+n(result.fuel_l_per_t-other.fuel_l_per_t,3)+' L/t but delivers '+n(result.tonnes-other.tonnes)+' fewer tonnes if switched to queue-aware.'):''}</p>`;

 // A policy switch affects FUTURE assignments only. Do not imply that already-queued
 // trucks will be removed from L3, or that a hypothetical outage will occur.
 const elapsed=(state.frame?.minute??a.at_min)-a.at_min;
 const stale=elapsed>5||elapsed<-.1;
 const same=result.policy===a.current_policy;
 state.chosenPolicy=!same&&!stale?result.policy:null;
 const site=alert?.site;
 const observedQueue=site?state.frame?.sites?.[site]?.queue:0;
 const siteNote=observedQueue>=8?`<p class="small-warning">${n(observedQueue)} trucks are already queued at ${esc(site)}. A policy switch changes only later assignments; it does not instantly reroute them. This model does not yet test specific truck-by-truck reassignment.</p>`:'';
 const delta=result.tonnes-(current?.tonnes??result.tonnes),liters=result.fuel_l-(current?.fuel_l??result.fuel_l);
 $('planAction').innerHTML=siteNote+(same?'<div class="action-status">No policy switch is justified by these tests. Keep operating and investigate the specific queue or shovel capacity.</div>':stale?'<div class="action-status">The mine has advanced. Re-run the comparison before making an operational change.</div>':`<div class="action-status">Tested action: change FUTURE dispatches to <strong>${esc(policyNames[result.policy])}</strong><br>Forecast vs current over ${n(a.horizon_hours)} h: <b>${delta>=0?'+':''}${n(delta)} t</b>, <b>${liters>=0?'+':''}${n(liters)} L</b>.</div><button id="applyPlan" class="primary" type="button" ${state.demo?'disabled':''}>Use this dispatch plan for future assignments →</button>${state.demo?'<p class="mini-help">Recorded preview is read-only. Connect to V2.3 to apply an approved plan.</p>':''}`);
 const relief=a.site_relief;
 if(relief){
  $('planAction').insertAdjacentHTML('beforeend',`<div class="queue-relief-card"><strong>Specific queue test · ${esc(relief.site)} (${n(relief.queued_now)} waiting)</strong><p>${esc(relief.action)} for ${n(relief.duration_min)} simulated minutes. Forecast ${relief.change_t>=0?'+':''}${n(relief.change_t)} t; waiting ${relief.change_wait_truck_hours>=0?'+':''}${n(relief.change_wait_truck_hours,1)} truck-h versus current dispatch. ${esc(relief.reason)}</p>${relief.recommended&&!stale&&!state.demo?`<button class="secondary-action" id="applyRelief">Apply tested queue relief for FUTURE trucks</button>`:''}<small>Existing shovel reservations remain unchanged.</small></div>`);
  const reliefBtn=$('applyRelief');if(reliefBtn)reliefBtn.onclick=()=>applyQueueRelief(relief.site,a.at_min);
 }
 const applyBtn=$('applyPlan');if(applyBtn)applyBtn.onclick=()=>applyTestedPolicy(result.policy,a.at_min);
 const colorsP={nearest:'#f0b676',balanced:'#59ceba',smart:'#75bafd'};let bars='';for(const m of [{key:'tonnes',title:'DELIVERED TONNES',unit:'t',max:Math.max(...a.options.map(o=>o.tonnes))},{key:'fuel_l_per_t',title:'FUEL EFFICIENCY · LOWER IS BETTER',unit:'L/t',max:Math.max(...a.options.map(o=>o.fuel_l_per_t||0))},{key:'queue_truck_hours',title:'WAITING · LOWER IS BETTER',unit:'h',max:Math.max(...a.options.map(o=>o.queue_truck_hours))}]){bars+=`<div class="policy-charts-header">${m.title}</div>`+a.options.map(o=>`<div class="policy-chart-row"><span class="policy-name">${esc(policyNames[o.policy])}</span><div class="bar-track"><div class="bar-fill" style="width:${Math.max(0,Number(o[m.key]||0))/Math.max(1e-6,m.max)*100}%;background:${colorsP[o.policy]}"></div></div><span class="policy-val">${n(o[m.key],m.key==='tonnes'?0:3)} ${m.unit}</span></div>`).join('')}
 $('policyCharts').innerHTML=bars;$('adviceTable').innerHTML=`<table><thead><tr><th>Policy</th><th>Delivered</th><th>Fuel L/t</th><th>Queue truck-hours</th><th>Decision</th></tr></thead><tbody>${a.options.map(o=>`<tr class="${o.policy===result.policy?'winner':''}"><td>${esc(policyNames[o.policy])}</td><td>${n(o.tonnes)} t</td><td>${n(o.fuel_l_per_t,3)}</td><td>${n(o.queue_truck_hours,1)}</td><td>${o.policy===result.policy?'Selected for goal':o.policy===a.current_policy?'Current':'Alternative'}</td></tr>`).join('')}</tbody></table>`}
const scenarioLabels={fuel_station_outage:'Fuel station outage',shovel_outage:'Shovel failure',road_closure:'Road closure',truck_failure:'Truck breakdown',crusher_outage:'Dump-site outage',road_degradation:'Poor road conditions'};
function setupScenarioTargets(){const kind=state.scenarioKind;let items=[];const cfg=state.config;if(!cfg)return;if(kind==='fuel_station_outage')items=['L0','L3'];else if(kind==='truck_failure')items=state.frame?.trucks.map(t=>t.id)||[];else if(kind==='crusher_outage')items=['D0','D1','D2','D3','D4'];else if(kind==='shovel_outage')items=cfg.load_sites.flatMap((s,i)=>s.shovels.map((sh,j)=>`shovel-${i+1}-${j+1}`));else items=['L0','L1','L2','L3','L4','D0','D1','D2','D3','D4'];$('scenarioTarget').innerHTML=items.map(x=>`<option value="${x}">${kind==='shovel_outage'?x.replaceAll('-',' ').replace('shovel','Shovel'):x}</option>`).join('');if(kind==='fuel_station_outage')$('scenarioTarget').value='L3';if(kind==='shovel_outage')$('scenarioTarget').value='shovel-4-1';$('roadToBlock').style.display=kind.includes('road_')?'block':'none';updateRoadTargets();$('scenarioHint').textContent='Runs are isolated from the operating mine. No live changes will be applied.'}
function updateRoadTargets(){const from=$('scenarioTarget').value;const to=from.startsWith('D')?['L0','L1','L2','L3','L4']:['D0','D1','D2','D3','D4'];$('scenarioRoadTo').innerHTML=to.map(x=>`<option value="${x}">${x}</option>`).join('')}
function drawScenario(){const s=state.scenario;if(!s){$('scenarioBadge').textContent=state.scenarioError?'FAILED':'NOT CALCULATED';$('impactSummary').innerHTML=state.scenarioError?'<div class="scenario-error"><strong>What-If calculation failed</strong><p>'+esc(state.scenarioError)+'</p><small>Nothing changed in the running mine. See backend logs for details.</small></div>':'<div class="placeholder"><span>⌁</span><strong>Run a scenario</strong><small>See the production, queues and fuel changes.</small></div>';$('scenarioChart').innerHTML='<div class="placeholder compact">No comparison calculated yet.</div>';$('scenarioMineDiff').innerHTML='';$('scenarioRecovery').innerHTML='<p class="muted">A recommendation appears after the simulation comparison.</p>';$('scenarioPlanAction').innerHTML='';return}
 $('scenarioBadge').textContent=state.demo?'RECORDED SIMULATION RESULT':'MODELED FORECAST';const diff=s.tonnes_delta,sign=diff>0?'+':'';const mx=Math.max(1,s.normal.tonnes,s.changed.tonnes);$('impactSummary').innerHTML=`<div class="impact-headline" style="color:${Math.abs(diff)<=.01*Math.max(1,s.normal.tonnes)?'#b6e6ef':diff<0?'#f4b76b':'#60d8b0'}">${Math.abs(diff)<=.01*Math.max(1,s.normal.tonnes)?'No material production change':diff<0?'Production decreases':'Production increases in this model'}</div><div class="impact-metrics"><div><span>Normal</span><b>${n(s.normal.tonnes)} t</b><small>${n(s.normal.fuel_l)} L estimated fuel</small></div><div><span>Disrupted</span><b>${n(s.changed.tonnes)} t</b><small>${n(s.changed.fuel_l)} L estimated fuel</small></div><div><span>Difference</span><b>${sign}${n(diff)} t</b><small>${s.fuel_delta_l>0?'+':''}${n(s.fuel_delta_l)} L fuel</small></div></div><p class="muted" style="margin:12px 0 0">${esc(s.interpretation)}</p>`;
 const a=s.normal.hourly||[],b=s.changed.hourly||[];const m=s.mitigation;
 const rec=s.recovered||s.changed;
 $('scenarioChart').innerHTML=threeOutcomeBars([
  {name:'Normal',color:'#63bee8',...s.normal},{name:'Disrupted',color:'#ef9e76',...s.changed},
  {name:'Recovery plan',color:'#69d9b4',...rec}
 ])+threeWayProductionChart(a,b,rec.hourly||[]);
 const preview=s.scenario_preview;
 if(preview){const normal={trucks:preview.normal_trucks,assets:preview.normal_assets};
 const disruption={trucks:preview.disrupted_trucks,assets:preview.disrupted_assets,affected:preview.affected_truck_ids};
 $('scenarioMineDiff').innerHTML=`<div class="scenario-map-title">Same simulated minute · ${n(preview.at_min,1)} · ${preview.affected_truck_ids.length} differing truck states/assignments</div>`+
 scenarioMiniMap(normal,'Normal')+scenarioMiniMap(disruption,'With disruption')+`<div class="scenario-map-note">Recovery production is shown in the three-way chart. A recovery truck-position snapshot is not supplied by the current API.</div>`;
 }else{$('scenarioMineDiff').innerHTML=''};const changedPolicy=m.recommended_policy!==state.frame?.active_policy;
 $('scenarioRecovery').innerHTML=`<strong style="display:block;color:#7bdbc3;font-size:15px">${changedPolicy?'Recovery candidate: '+esc(policyNames[m.recommended_policy]):'No superior dispatch recovery found'}</strong><p class="small-warning">${esc(m.reason)}</p><p class="mini-help">This is a simulated outage, not a live incident. Switching policy here would not introduce the failure or immediately clear existing truck queues.</p>`;
 $('scenarioPlanAction').innerHTML=changedPolicy?`<div class="action-status">To use a recovery policy safely, first test it against the actual current mine—without the hypothetical outage.</div><button class="primary" id="checkLiveRecovery" type="button">Check this recovery plan on the live mine →</button>`:'<div class="action-status">Do not change dispatch without evidence of a better option. Check affected equipment and queue capacity.</div>';
 if($('checkLiveRecovery'))$('checkLiveRecovery').onclick=()=>{nav('recommendations');runJob('advice',{horizon_hours:Number($('adviceHorizon').value)},$('runAdvice'))};
}
function equipItems(){const f=state.frame,cfg=state.config;if(!f||!cfg)return[];const tab=state.assetTab;if(tab==='trucks')return f.trucks.map(t=>({id:t.id,stat:prettyStatus[t.status]||t.status,extra:n(t.capacity)+' t',data:t}));if(tab==='shovels')return cfg.load_sites.flatMap((s,i)=>s.shovels.map((sh,j)=>({id:`shovel-${i+1}-${j+1}`,stat:`Loading site L${i}`,extra:`${n(sh.tons,2)} t/bucket`,data:{site:'L'+i,tons:sh.tons,cycle_time:sh.cycle_time,shovel:sh.name}})));if(tab==='fuel')return ['L0','L3'].map(id=>({id,stat:'Fuel station',extra:'2 pumps · modeled',data:{station:id}}));if(tab==='loads')return cfg.load_sites.map((s,i)=>({id:'L'+i,stat:'Loading site',extra:(f.sites?.['L'+i]?.queue||0)+' queued',data:{site:'L'+i,shovels:s.shovels.length}}));if(tab==='roads')return Object.values(state.assets?.roads||{}).map(r=>({id:r.from+'→'+r.to,stat:r.state,extra:n(r.length_km,2)+' km',data:r}));return cfg.dump_sites.map((s,i)=>({id:'D'+i,stat:'Dump site',extra:s.dumpers.reduce((a,u)=>a+u.count,0)+' dumpers',data:{site:'D'+i}}))}
function drawEquipment(){const terms=$('equipmentSearch').value.trim().toLowerCase(),items=equipItems().filter(x=>(x.id+' '+x.stat+' '+x.extra).toLowerCase().includes(terms));const title={trucks:'Trucks',shovels:'Shovels',fuel:'Fuel stations',loads:'Loading sites',dumps:'Dump sites',roads:'Directed roads'}[state.assetTab];$('equipmentListTitle').textContent=title;$('assetCount').textContent=items.length+' shown';if(!state.selected||state.selected.tab!==state.assetTab||!items.some(x=>x.id===state.selected.id))state.selected={tab:state.assetTab,id:items[0]?.id};$('equipmentRows').innerHTML=items.length?items.map(x=>`<button class="equip-row ${state.selected?.id===x.id?'selected':''}" data-eid="${esc(x.id)}"><strong>${esc(x.id)}</strong><span>${esc(x.stat)}</span><small>${esc(x.extra)}</small></button>`).join(''):'<p class="muted">No matching equipment.</p>';document.querySelectorAll('#equipmentRows [data-eid]').forEach(el=>el.onclick=()=>{state.selected={tab:state.assetTab,id:el.dataset.eid};drawEquipment()});const entry=items.find(x=>x.id===state.selected?.id);if(!entry){$('equipmentInfo').innerHTML='<p class="muted">Choose equipment.</p>';return}
 const d=entry.data,r=state.report?.current;let fields=[];if(state.assetTab==='trucks')fields=[['State',prettyStatus[d.status]||d.status],['Class',d.capacity+' tonnes'],['Current load',d.payload+' t'],['Fuel',n(d.fuel_l,1)+' / '+n(d.tank_l)+' L'],['Fuel %',pct(d.fuel_pct)],['Route',d.route],['Configured speed',d.speed+' km/h'],['Route progress',pct(d.progress*100)]];else if(state.assetTab==='shovels'){const sh=r?.shovels.find(x=>x.shovel.endsWith(entry.data.shovel))||r?.shovels.find(x=>x.shovel.includes(entry.id.split('-').slice(1).join('')));fields=[['Site',d.site],['Per bucket',n(d.tons,2)+' t'],['Cycle time',n(d.cycle_time,1)+' min'],['Busy last 24h',sh?n(sh.busy_min,1)+' min':'Data not separated in API'],['Loaded last 24h',sh?n(sh.tonnes,0)+' t':'See Reports']]}else if(state.assetTab==='fuel'){const trucks=state.frame.trucks.filter(x=>x.current_destination===entry.id&&['refueling','queue_fuel','to_fuel'].includes(x.status));fields=[['Fuel station',entry.id],['Pumps','2 modeled'],['Refueling now',trucks.filter(x=>x.status==='refueling').length],['In fuel queue',trucks.filter(x=>x.status==='queue_fuel').length],['En route to station',trucks.filter(x=>x.status==='to_fuel').length],['Fuel dispensed',n(state.assets?.fuel_stations?.[entry.id]?.fuel_dispensed_l??0,1)+' L'],['Station status',state.assets?.fuel_stations?.[entry.id]?.state??'unknown']]}else if(state.assetTab==='roads'){fields=[['From',d.from],['To',d.to],['Condition',d.state],['Configured distance',n(d.length_km,2)+' km'],['Data source','OpenMines distance matrix']]}else if(state.assetTab==='loads'){const site=state.frame.sites?.[entry.id]||{};const perf=r?.load_sites.find(x=>x.site===entry.id);fields=[['Shovels',d.shovels],['Waiting trucks',site.queue||0],['Loading trucks',site.loading||0],['Loaded 24h',perf?n(perf.loaded_t)+' t':'—']]}else{fields=[['Dump',entry.id],['Function','Material unloading'],['Configured unloaders',d.site?entry.extra:'—']]}
 $('equipmentInfo').innerHTML=`<div class="detail-title">${esc(entry.id)}</div><div class="detail-sub">${esc(title.slice(0,-1))} · Simulated operating asset</div><div class="detail-grid">${fields.map(([a,b])=>`<div><small>${esc(a)}</small><b>${esc(b)}</b></div>`).join('')}</div>${state.assetTab==='trucks'?`<div class="fuel-meter"><i style="width:${Math.max(0,Math.min(100,d.fuel_pct))}%"></i></div>`:''}<div class="detail-note" id="equipmentSync">${state.demo?'Recorded simulator state; live synchronization not tested.':'Checking the connected equipment twin…'}</div><div id="equipmentPersisted" class="twin-persisted"></div>`;if(!state.demo)checkSelectedTwin(entry.id)}
function dualChart(rows){
 if(!rows?.length)return '<div class="placeholder compact">No hourly records available</div>';
 const a=rows.slice(-24),mT=Math.max(1,...a.map(x=>x.delivered_t)),mF=Math.max(1,...a.map(x=>x.fuel_l));
 let s=`<div class="metric-legend" style="margin-bottom:9px"><span style="color:#61c4de">■ Tonnes / hour</span><span style="color:#f2b76c">● Fuel L / hour</span></div><svg viewBox="0 0 670 180" preserveAspectRatio="none" role="img" aria-label="Hourly tonnes and liters with independent scales">`;
 for(let j=0;j<4;j++){let y=15+j*45;s+=`<line class="gridline" x1="28" y1="${y}" x2="638" y2="${y}"/>`}
 const w=605/a.length;let pts=[];
 a.forEach((row,i)=>{let h=(row.delivered_t/mT)*136,x=32+w*i;s+=`<rect x="${x+2}" y="${151-h}" width="${Math.max(2,w-5)}" height="${h}" fill="#5bbce6" rx="1.5"><title>${n(row.delivered_t)} t</title></rect>`;pts.push(`${x+w/2},${151-row.fuel_l/mF*136}`)});
 s+=`<polyline points="${pts.join(' ')}" fill="none" stroke="#f4ba73" stroke-width="2.5"/>`;
 s+=`<text x="30" y="175">Tonnes scale 0–${n(mT)}</text><text x="400" y="175">Fuel scale 0–${n(mF)} L</text></svg>`;return s
}
let lastTwinKey='',lastTwinCheck=0;
async function checkSelectedTwin(id){
 const thingId=state.assetTab==='fuel'?'fuel-'+id.toLowerCase():state.assetTab==='loads'?'load-'+(Number(id.slice(1))+1):state.assetTab==='dumps'?'dump-'+(Number(id.slice(1))+1):state.assetTab==='roads'?'road-'+id.replace('→','-').toLowerCase():id.toLowerCase();const key=state.frame?.run_id+':'+thingId;if(key===lastTwinKey&&Date.now()-lastTwinCheck<15000)return;
 lastTwinKey=key;lastTwinCheck=Date.now();
 try{const r=await req('/api/ditto/'+thingId);const active=state.selected?.id===id;if(!active)return;const el=$('equipmentSync');if(!el)return;
 if(r.verified&&r.matches_active_run){
  const lag=state.frame?.minute-Number(r.sim_minute||0);
  el.textContent=lag>=0?'Ditto stored this equipment state · '+n(lag,1)+' simulated minutes behind.':'Ditto twin confirmed · stored run matches.';
  el.style.color='#75d8b6';
  const props=r.properties||{};const allowed=['state','payload_t','fuel_l','fuel_pct','queue_trucks','waiting_trucks','refueling_trucks','fuel_dispensed_l','closure_active','sim_minute'];
  const vals=allowed.filter(k=>props[k]!==undefined).map(k=>`<span><small>${esc(k.replaceAll('_',' '))}</small><b>${esc(typeof props[k]==='number'?n(props[k],1):props[k])}</b></span>`).join('');
  const persisted=$('equipmentPersisted');if(persisted)persisted.innerHTML='<strong>Persisted in Eclipse Ditto</strong><div class="twin-persisted-grid">'+(vals||'<small>Stored run identifier verified</small>')+'</div>';
 }else{el.textContent='Twin not verified for the current run';el.style.color='#f1b16d';const persisted=$('equipmentPersisted');if(persisted)persisted.innerHTML=''}
 }catch(e){const el=$('equipmentSync');if(el){el.textContent='External twin readback unavailable';el.style.color='#f1b16d'}}
}
function drawReports(){const r=state.report?.current;if(!r)return;$('reportKpi').innerHTML=kpi('Material · last 24h',n(r.tonnes)+' t',`${n(r.trips)} completed trips`)+kpi('Truck fuel · last 24h',n(r.fuel_l)+' L','Model estimate')+kpi('Fleet utilization',pct(r.avg_fleet_utilization_pct),'Time spent on operations')+kpi('Truck queue time',n(r.waiting_truck_hours,1)+' h','Summed across the fleet')+kpi('Litres per tonne',r.fuel_l_per_t?n(r.fuel_l_per_t,3):'—','Modeled fuel efficiency');$('reportProduction').innerHTML=dualChart(r.hourly?.filter(x=>x.minute>=r.start_min-60&&x.minute<=r.end_min));const max=Math.max(1,...r.load_sites.map(x=>x.loaded_t));$('sitePerformance').innerHTML=r.load_sites.map(x=>barRow(x.site,x.loaded_t,max,'#64c9d7',' t')).join('');const activities=Object.entries(r.fleet_state_hours||{}).sort((a,b)=>b[1]-a[1]).slice(0,7),mx=Math.max(1,...activities.map(x=>x[1]));$('activityChart').innerHTML=activities.map(([k,v])=>`<div class="bar-row" style="grid-template-columns:90px 1fr 60px"><span>${esc(prettyStatus[k]||k)}</span><div class="bar-track"><div class="bar-fill" style="width:${v/mx*100}%;background:${colors[k]||'#77bcd0'}"></div></div><b>${n(v,1)}h</b></div>`).join('');const sh=(r.shovels||[]).slice(0,8),smax=Math.max(1,...sh.map(x=>x.tonnes));$('shovelChart').innerHTML=sh.map(x=>`<div class="bar-row" style="grid-template-columns:115px 1fr 62px"><span title="${esc(x.shovel)}">${esc(x.site+' · '+x.shovel.split('-').slice(-1)[0])}</span><div class="bar-track"><div class="bar-fill" style="width:${x.tonnes/smax*100}%;background:#79bff0"></div></div><b>${n(x.tonnes)} t</b></div>`).join('');const days=state.report?.completed_days||[];$('completedDays').innerHTML=days.length?`<table><thead><tr><th>Day</th><th>Delivered</th><th>Fuel used</th><th>Completed trips</th></tr></thead><tbody>${days.slice(-10).reverse().map(d=>`<tr><td>Day ${d.day}</td><td>${n(d.tonnes)} t</td><td>${n(d.fuel_l,1)} L</td><td>${n(d.trips)}</td></tr>`).join('')}</tbody></table>`:'<p class="muted">First full-day report is generated after simulated minute 1,440.</p>'}
function drawHeader(){const f=state.frame;if(!f)return;$('clock').textContent=fmtTime(f.minute);$('togglePause').textContent=f.playing?'Ⅱ Pause':'▶ Resume';$('speed').value=String(f.rate);$('recordedPill').textContent=state.demo?'RECORDED API SNAPSHOT':'LIVE API · SIMULATED MINE';$('recordedPill').className=state.demo?'pill gray':'pill live';const h=state.connected,ok=h?.mqtt&&h?.ditto&&h?.run_matches&&h?.twin_fresh;$('healthLed').className='status-dot '+(ok?'good':'');$('healthText').textContent=ok?'Twins verified':state.demo?'External sync not tested':'Sync unverified'}
function renderPage(){drawHeader();if(state.page==='operations')drawOperations();if(state.page==='recommendations')drawRecommendation();if(state.page==='scenarios')drawScenario();if(state.page==='equipment')drawEquipment();if(state.page==='reports')drawReports()}
async function runJob(kind,payload,btn){if(state.demo){const valid=kind==='advice'?Number(payload.horizon_hours)===2:kind==='scenario'&&payload.scenario==='fuel_station_outage'&&payload.affected==='L3'&&payload.duration_min===100&&payload.delay_min===0&&Number(payload.horizon_hours)===2;if(!valid){say('Recorded preview only supports the saved 2-hour example. Connect your running OreFlow V2.3 to calculate other settings.');return};const data=await req('/api/recorded/'+kind);if(kind==='advice')state.advice=data;else state.scenario=data;renderPage();return}
 btn.disabled=true;btn.textContent='Calculating…';try{await post('/api/v22/evaluate',{kind,...payload});let result;for(let t=0;t<120;t++){await new Promise(r=>setTimeout(r,500));const job=await req('/api/v22/job');if(job.status==='done'){result=job.result;break}if(job.status==='error')throw Error(job.detail)}if(!result)throw Error('Computation not yet complete');if(kind==='advice')state.advice=result;else{state.scenario=result;state.scenarioError=null}renderPage()}catch(e){if(kind==='scenario'){state.scenario=null;state.scenarioError=e.message;drawScenario()}say(e.message)}finally{btn.disabled=false;btn.textContent=kind==='advice'?'Run comparison →':'Calculate impact →'}}
async function applyTestedPolicy(policy, evaluatedAt) {
 if(state.applyPending || state.demo) return;
 if(!('nearest balanced smart'.split(' ')).includes(policy)){say('Unknown policy');return}
 if(!state.advice || state.advice.at_min!==evaluatedAt){say('Comparison changed. Re-run it first.');return}
 try{
  const current=await req('/api/v22/now');
  if(current.minute-evaluatedAt>5 || current.minute<evaluatedAt-.1){say('Plan is stale: mine state advanced. Compare again before applying.');return}
  if(current.active_policy===policy){say('This dispatch policy is already active.');return}
  const ok=window.confirm(`Apply ${policyNames[policy]} to FUTURE truck dispatch decisions?\n\nAlready-queued trucks are NOT moved. No road closure or equipment failure will be applied.\n\nThis changes the live simulator.`);
  if(!ok)return;
  state.applyPending=true;
  await post('/api/v22/policy',{policy});
  state.advice=null;state.chosenPolicy=null;
  say('Dispatch policy applied for future assignments. No incident applied.');
  await refresh();
 } catch(e){say('Could not apply plan: '+e.message)}finally{state.applyPending=false}
}
async function applyQueueRelief(site,evaluatedAt){
 if(state.demo || !state.advice || state.advice.at_min!==evaluatedAt)return;
 const current=await req('/api/v22/now');
 if(current.minute-evaluatedAt>5){say('Mine advanced. Evaluate the queue again.');return}
 if(!window.confirm(`Temporarily exclude ${site} from NEW truck assignments?\nAlready queued trucks will remain. No incident will be caused.`))return;
 try{await post('/api/v23/queue-relief',{site});state.advice=null;say('Tested queue-relief assignment rule activated for future trucks.');await refresh()}
 catch(e){say('Queue-relief action failed: '+e.message)}
}
async function refresh(){if(state.refreshing)return;state.refreshing=true;try{const [f,r,assets]=await Promise.all([req('/api/v22/now'),req('/api/v22/reports'),req('/api/v22/assets')]);state.frame=f;state.report=r;state.assets=assets;renderPage()}catch(e){say('OreFlow API unavailable: '+e.message)}finally{state.refreshing=false}}
async function checkStatus(){try{state.connected=await req('/api/v22/status')}catch(e){state.connected=null}drawHeader()}
function exportCsv(){
 if(state.demo){say('This recorded preview cannot export live mine data.');return}
 const kind=$('exportType').value;
 const a=document.createElement('a');a.href='/api/v23/export?kind='+encodeURIComponent(kind);
 a.download='oreflow_'+kind+'.csv';document.body.append(a);a.click();a.remove();
}
async function startFreshMine(){
 if(state.demo){say('Start a fresh mine from the running Docker application.');return}
 if(!window.confirm('Start a NEW simulated mine from Day 1? This archives the previous checkpoint and daily reports. The current mine will be replaced.'))return;
 if(!window.confirm('Confirm fresh start: all current simulated trucks, trips, fuel and progress will reset to initial values. Original OpenMines configuration is unchanged.'))return;
 try{
  const response=await post('/api/v23/fresh-start',{confirm:'START_FRESH'});
  state.advice=null;state.scenario=null;state.scenarioError=null;state.selected=null;
  await refresh(); await checkStatus();
  say('Fresh mine started. Day 1, new run '+response.run_id+'. Previous simulated history archived.');
 }catch(e){say('Fresh start failed: '+e.message)}
}
async function setup(){$('mapRoadMode').onchange=e=>{mapRouteView=e.target.value;map()};for(const btn of document.querySelectorAll('#nav button'))btn.onclick=()=>nav(btn.dataset.page);for(const btn of document.querySelectorAll('[data-goto]'))btn.onclick=()=>nav(btn.dataset.goto);$('closeDrawer').onclick=()=>{$('assetDrawer').classList.remove('open');state.selected=null;map()};$('closeModal').onclick=()=>$('modal').hidden=true;$('assumptionsLink').onclick=()=>$('modal').hidden=false;$('healthBtn').onclick=()=>say(state.demo?'Recorded snapshot; live Ditto status not claimed.':state.connected?.message||('MQTT '+(state.connected?.mqtt?'connected':'unverified')+' · Ditto '+(state.connected?.ditto?'readable':'unverified')));
 $('equipmentSearch').oninput=drawEquipment;$('exportCsv').onclick=exportCsv;$('startFresh').onclick=startFreshMine;for(const btn of document.querySelectorAll('#assetTabs button'))btn.onclick=()=>{state.assetTab=btn.dataset.tab;state.selected=null;$('equipmentSearch').value='';document.querySelectorAll('#assetTabs button').forEach(b=>b.classList.toggle('active',b===btn));drawEquipment()};
 for(const btn of document.querySelectorAll('#scenarioTypes .choice'))btn.onclick=()=>{state.scenarioKind=btn.dataset.kind;state.scenario=null;state.scenarioError=null;document.querySelectorAll('#scenarioTypes .choice').forEach(x=>x.classList.toggle('active',x===btn));setupScenarioTargets();drawScenario()};$('scenarioTarget').onchange=()=>{state.scenario=null;state.scenarioError=null;updateRoadTargets();drawScenario()}; for(const id of ['scenarioRoadTo','scenarioDelay','scenarioDuration','scenarioHorizon'])$(id).onchange=()=>{state.scenario=null;state.scenarioError=null;drawScenario()};
 $('adviceGoal').onchange=drawRecommendation; $('runAdvice').onclick=()=>runJob('advice',{horizon_hours:Number($('adviceHorizon').value)},$('runAdvice'));
 $('runScenario').onclick=()=>{const kind=state.scenarioKind;let payload={scenario:kind,delay_min:Number($('scenarioDelay').value),duration_min:Number($('scenarioDuration').value),horizon_hours:Number($('scenarioHorizon').value)};if(kind.includes('road_')){payload.road_from=$('scenarioTarget').value;payload.road_to=$('scenarioRoadTo').value}else payload.affected=$('scenarioTarget').value;runJob('scenario',payload,$('runScenario'))};
 $('togglePause').onclick=async()=>{if(state.demo){say('Recorded preview is read-only. Connect your OreFlow V2.3 API to control playback.');return}try{state.frame=await post('/api/v22/control',{playing:!state.frame.playing});renderPage();say(state.frame.playing?'Mine resumed':'Mine paused')}catch(e){say(e.message)}};$('speed').onchange=async()=>{if(state.demo){say('Recorded preview: speed changes require a live API');$('speed').value=String(state.frame.rate);return}try{state.frame=await post('/api/v22/control',{rate:Number($('speed').value)});renderPage()}catch(e){say(e.message)}};
 try{const meta=await req('/api/prototype-info');state.demo=Boolean(meta.recorded);state.config=await req('/api/source-config');if(state.demo){state.advice=await req('/api/recorded/advice');state.scenario=await req('/api/recorded/scenario');$('adviceHorizon').value='2'}setupScenarioTargets();await refresh();await checkStatus();if(!state.demo){setInterval(refresh,4000);setInterval(checkStatus,25000)}else say('Preview showing a recorded OreFlow simulation — no live data claimed')}catch(e){say('Could not load OreFlow: '+e.message);console.error(e)}}
setup();
