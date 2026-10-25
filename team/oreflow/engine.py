"""OreFlow KZ 2.0: deterministic discrete-event open-pit dispatch and energy model.

Provenance: OpenMines North Pit JSON supplies truck counts/payload/nominal speeds,
shovel parameters, dump units, and directed road distances. Every operation,
route grade, fuel rate, tank reference and breakdown here is SIMULATED.
The engine is independent of OpenMines runtime; no actual mine telemetry.
"""
from __future__ import annotations
import bisect
import hashlib
import heapq
import json
import math
from pathlib import Path

SOURCE=Path(__file__).parent/'data'/'north_pit_mine.json'
NAMESPACE='org.openegiz.oreflow'

# Reference-class tank capacities are NOT identified equipment in North Pit.
# Tank (litres) class references: HD325-8 ~456 L, HD465-8 ~800 L,
# XCMG XDR80T ~650 L (72-t proxy for 77-t class). Fuel rates below are explicit
# *unvalidated engineering assumptions*, not manufacturer or mine measurements.
ENERGY={
 'CLTruck': {'tank_l':456., 'loaded_l_km':1.35,'empty_l_km':0.90,'idle_l_h':7.0,'reference':'36.5-t Komatsu HD325-8 class; illustrative'},
 'XHTruck': {'tank_l':800., 'loaded_l_km':2.00,'empty_l_km':1.20,'idle_l_h':10.0,'reference':'55-t Komatsu HD465-8 class; illustrative'},
 'OfficalTruck': {'tank_l':650., 'loaded_l_km':2.65,'empty_l_km':1.65,'idle_l_h':13.0,'reference':'72-t XCMG XDR80T class proxy for 77-t; illustrative'},
}
DEFAULT_PUMPS=('L0','L3')

def source():return json.loads(SOURCE.read_text(encoding='utf-8'))

def validate_config(cfg):
 assert len(cfg['charging_site']['trucks'])==3
 assert sum(x['count'] for x in cfg['charging_site']['trucks'])==71
 assert len(cfg['load_sites'])==len(cfg['dump_sites'])==5
 assert sum(len(x['shovels']) for x in cfg['load_sites'])==20
 assert len(cfg['road']['charging_to_load_road_matrix'])==5
 for k in ('l2d_road_matrix','d2l_road_matrix'):
  assert len(cfg['road'][k])==5
  assert all(len(row)==5 and all(0<x<100 for x in row) for row in cfg['road'][k])
 assert all(t['capacity']>0 and t['speed']>0 and t['type'] in ENERGY for t in cfg['charging_site']['trucks'])
 return True

def deterministic_jitter(seed,truck,cycle,stage):
 raw=int.from_bytes(hashlib.sha256(f'{seed}:{truck}:{cycle}:{stage}'.encode()).digest()[:4],'big')/2**32
 return .96+.08*raw

def _check_choice(value,values,name):
 if value not in values:raise ValueError(f'Invalid {name}: {value}')
 return value

class MineRun:
 def __setstate__(self, values):
  """Migrate older trusted pickled checkpoints to the current dispatch schema."""
  self.__dict__.update(values)
  if 'restricted_load_site' not in self.__dict__:
   self.restricted_load_site=None
  if 'restricted_until' not in self.__dict__:
   self.restricted_until=0.

 def __init__(self,*,strategy='smart',scenario='normal',seed=42,duration=1440,
              affected=None,route_from=None,route_to=None,fleet=71,
              closure_start=480,outage_start=480,outage_duration=120,
              dispatch_objective='balanced',fuel_price_kzt=350.,
              fuel_enabled=True,shift_change=True,road_grade=True,planned_maintenance=True,
              fuel_station='L0',fleet_mix=None,policy_weights=None):
  _check_choice(strategy,('nearest','balanced','smart'),'strategy')
  _check_choice(scenario,('normal','shovel_outage','road_closure','fleet_reduction',
   'truck_failure','fuel_station_outage','crusher_outage','road_degradation'),'scenario')
  _check_choice(dispatch_objective,('production','fuel','balanced'),'dispatch objective')
  self.cfg=source();validate_config(self.cfg)
  self.strategy=strategy;self.scenario=scenario;self.seed=int(seed)
  if not 1<=self.seed<=100000:raise ValueError('seed must be 1–100000')
  self.duration=int(duration)
  if not 60<=self.duration<=2880:raise ValueError('duration must be 60–2880 simulated minutes')
  if fleet_mix is not None and scenario=='fleet_reduction':
   if not isinstance(fleet_mix,dict) or set(fleet_mix)!={'OfficalTruck','CLTruck','XHTruck'}:
    raise ValueError('fleet_mix must specify the three source truck types')
   maxima={'OfficalTruck':9,'CLTruck':29,'XHTruck':33}
   self.fleet_mix={k:int(fleet_mix[k]) for k in maxima}
   if any(not 0<=self.fleet_mix[k]<=maxima[k] for k in maxima) or not sum(self.fleet_mix.values()):
    raise ValueError('invalid truck class counts')
   self.fleet=sum(self.fleet_mix.values())
  else:
   self.fleet_mix=None
   self.fleet=int(fleet) if scenario=='fleet_reduction' else 71
  if not 1<=self.fleet<=71:raise ValueError('fleet must be between 1 and 71')
  self.dispatch_objective=dispatch_objective
  self.fuel_price_kzt=float(fuel_price_kzt)
  if not 0<=self.fuel_price_kzt<=10000:raise ValueError('invalid fuel price')
  self.fuel_enabled=bool(fuel_enabled);self.shift_change=bool(shift_change);self.road_grade=bool(road_grade)
  self.planned_maintenance=bool(planned_maintenance)
  self.outage_start=float(outage_start);self.closure_start=float(closure_start)
  self.outage_duration=float(outage_duration)
  if scenario!='normal' and not(0<=self.outage_start<=self.duration and 0<=self.closure_start<=self.duration and 1<=self.outage_duration<=self.duration):raise ValueError('invalid disruption timing')
  self.affected=affected or {'shovel_outage':'shovel-3-1','truck_failure':'T001',
       'crusher_outage':'D0','fuel_station_outage':'L3'}.get(scenario,'')
  self.route_from=route_from or 'L2';self.route_to=route_to or 'D4'
  _check_choice(self.route_from,tuple(f'L{i}' for i in range(5))+tuple(f'D{i}' for i in range(5)),'road start')
  if self.route_from.startswith('L'):
   _check_choice(self.route_to,tuple(f'D{i}' for i in range(5)),'road end')
  else:_check_choice(self.route_to,tuple(f'L{i}' for i in range(5)),'road end')
  if scenario=='shovel_outage':
   _check_choice(self.affected,tuple(f'shovel-{i+1}-{j+1}' for i,l in enumerate(self.cfg['load_sites']) for j,_ in enumerate(l['shovels'])),'shovel')
  if scenario=='truck_failure':_check_choice(self.affected,tuple(f'T{i:03}' for i in range(1,72)),'truck')
  if scenario=='fuel_station_outage':_check_choice(self.affected,DEFAULT_PUMPS,'fuel station')
  if scenario=='crusher_outage':_check_choice(self.affected,tuple(f'D{i}' for i in range(5)),'dump site')
  _check_choice(fuel_station,DEFAULT_PUMPS,'fuel station')
  self.fuel_station=fuel_station
  self.policy_weights=policy_weights or {'dump':.05,'queue':.8,'site':-.2}
  # Temporary queue-relief policy: no NEW assignments to this site while active.
  # It does not magically remove already queued trucks or cancel a shovel booking.
  self.restricted_load_site=None;self.restricted_until=0.
  self.nodes={'C':{'name':'Depot','x':0.,'y':0.}}
  for i,s in enumerate(self.cfg['load_sites']):self.nodes[f'L{i}']={'name':s['name'],'x':s['position'][0],'y':s['position'][1]}
  for i,s in enumerate(self.cfg['dump_sites']):self.nodes[f'D{i}']={'name':s['name'],'x':s['position'][0],'y':s['position'][1]}
  self.all_trucks=[]
  for typ in self.cfg['charging_site']['trucks']:
   for j in range(typ['count']):
    id_=f'T{len(self.all_trucks)+1:03}'
    self.all_trucks.append({'id':id_,'type':typ['type'],'capacity':typ['capacity'],'speed':typ['speed'],
                            'tank_l':ENERGY[typ['type']]['tank_l']})
  chosen=[]
  if self.fleet_mix:
   selected_count={k:0 for k in self.fleet_mix}
   for t in self.all_trucks:
    if selected_count[t['type']]<self.fleet_mix[t['type']]:
     chosen.append(t);selected_count[t['type']]+=1
  else:chosen=self.all_trucks[:self.fleet]
  self.trucks={}
  for t in chosen:
   # deterministic but heterogeneous initial tank fills, rather than infinite fuel
   initial=t['tank_l']*(.65+.25*(deterministic_jitter(self.seed,t['id'],0,'initial-fuel')-.96)/.08)
   self.trucks[t['id']]={**t,'segments':[],'fuel_l':initial,'initial_fuel_l':initial,
      'fuel_archived_l':0.,'fuel_added_archived_l':0.,
      'delivered':0.,'trips':0,'wait':0.,'cycles':0,'fuel_used_l':0.,'fuel_added_l':0.,'last':0.}
  self.road_l2d=self.cfg['road']['l2d_road_matrix'];self.road_d2l=self.cfg['road']['d2l_road_matrix']
  self.loads=[];self.dumps=[]
  for i,l in enumerate(self.cfg['load_sites']):
   self.loads.append([{'available':0.,'tons':s['tons'],'cycle':s['cycle_time'],
      'id':s['name'],'alias':f'shovel-{i+1}-{j+1}'} for j,s in enumerate(l['shovels'])])
  for site in self.cfg['dump_sites']:
   unit=site['dumpers'][0]
   self.dumps.append([{'available':0.,'cycle':unit['cycle_time']} for _ in range(unit['count'])])
  self.pumps={s:[{'available':0.,'rate_l_min':45.} for _ in range(2)] for s in DEFAULT_PUMPS}
  self.queue=[];self.seq=0;self.deliveries=[];self.trips=[];self.actions=[];self.fuel_events=[]
  self.completed=False
  self.archived_tonnes=0.;self.archived_trips=0
  for truck in self.trucks:self._event(0,'dispatch',truck,'C')

 def _road_pairs(self):
  # Directed edges are distinct: L→D and D→L may have different distances.
  pairs={('C',f'L{i}') for i in range(5)}
  for li in range(5):
   for di in range(5):
    pairs.add((f'L{li}',f'D{di}'))
    pairs.add((f'D{di}',f'L{li}'))
  return pairs
 def road_status(self,at,frm,to):
  if self._blocked(at,frm,to):return 'closed'
  if self.scenario=='road_degradation' and frm==self.route_from and to==self.route_to and self._in_window(at,self.closure_start):return 'degraded'
  return 'open'
 def asset_states(self,at):
  # A compact, per-asset read model, derived from the SAME equipment events as
  # the production numbers. Used for MQTT digital twins and for scenario maps.
  frame=self.frame(at)
  station_states={}
  for site,pumps in self.pumps.items():
   waiting=[x for x in frame['trucks'] if x['status']=='queue_fuel' and x.get('current_destination')==site]
   refueling=[x for x in frame['trucks'] if x['status']=='refueling' and x.get('current_destination')==site]
   inbound=[x for x in frame['trucks'] if x['status']=='to_fuel' and x.get('current_destination')==site]
   closed=self.scenario=='fuel_station_outage' and self.affected==site and self._in_window(at,self.outage_start)
   dispensed=sum(x['litres'] for x in self.fuel_events if x['station']==site and x['end']<=at)
   station_states[site]={'state':'unavailable' if closed else 'available',
    'pump_capacity':len(pumps),'pumps_busy':len(refueling),'waiting_trucks':len(waiting),
    'refueling_trucks':len(refueling),'incoming_trucks':len(inbound),
    'fuel_dispensed_l':round(dispensed,1)}
  shovels={}
  for li,site in enumerate(self.loads):
   for sj,sh in enumerate(site):
    failed=(self.scenario=='shovel_outage' and sh['alias']==self.affected and self._in_window(at,self.outage_start))
    busy=any(x['start']<=at<x['end'] and x.get('shovel')==sh['id'] and x['state']=='loading'
      for truck in self.trucks.values() for x in truck['segments'][-12:])
    shovels[sh['alias']]={'site':f'L{li}','state':'failed' if failed else 'loading' if busy else 'available',
      'bucket_t':sh['tons'],'cycle_min':sh['cycle']}
  roads={f'{frm}->{to}':{'from':frm,'to':to,'state':self.road_status(at,frm,to),'length_km':self._road_length(frm,to)}
    for frm,to in sorted(self._road_pairs())}
  return {'fuel_stations':station_states,'shovels':shovels,'roads':roads}
 def _event(self,t,kind,truck,arg=None):
  self.seq+=1;heapq.heappush(self.queue,(round(t,9),self.seq,kind,truck,arg))
 def _road_length(self,frm,to):
  if frm=='C' and to.startswith('L'):return self.cfg['road']['charging_to_load_road_matrix'][int(to[1:])]
  if frm.startswith('L') and to.startswith('D'):return self.road_l2d[int(frm[1:])][int(to[1:])]
  if frm.startswith('D') and to.startswith('L'):return self.road_d2l[int(to[1:])][int(frm[1:])]
  raise ValueError(f'no configured road {frm}->{to}')
 def _in_window(self,t,start):return start<=t<start+self.outage_duration
 def _blocked(self,t,frm,to):
  return self.scenario=='road_closure' and frm==self.route_from and to==self.route_to and self._in_window(t,self.closure_start)
 def _road_blocked(self,t,frm,to):return self._blocked(t,frm,to)
 def _road_grade_pct(self,frm,to):
  if not self.road_grade or frm=='C':return 0.
  i=int(frm[1:]);j=int(to[1:]); li=i if frm[0]=='L' else j;di=j if to[0]=='D' else i
  proxy=((li*7+di*11)%11-5)*.6  # ASSUMPTION: -3 .. 3% not survey data
  return proxy if frm.startswith('L') else -proxy
 def _road_condition(self,t,frm,to):
  return 1.6 if self.scenario=='road_degradation' and frm==self.route_from and to==self.route_to and self._in_window(t,self.closure_start) else 1.
 def _travel(self,tr,frm,to,at=0):
  dist=self._road_length(frm,to);loaded=frm.startswith('L') and to.startswith('D')
  # Nominal OpenMines speed modified by ASSUMED loaded/empty behavior & grade
  grade=self._road_grade_pct(frm,to)
  condition=self._road_condition(at,frm,to)
  speed=tr['speed']*(.85 if loaded else 1.08)/(condition*(1+max(-.18,min(.18,grade*.025))))
  jitter=deterministic_jitter(self.seed,tr['id'],tr['cycles'],f'{frm}-{to}')
  return 60*dist/max(5,speed)*jitter
 def _travel_fuel(self,tr,frm,to,at=0):
  k='loaded_l_km' if frm.startswith('L') else 'empty_l_km'
  grade=self._road_grade_pct(frm,to)
  # bounded proxy multiplier; applied on *directed* road entry
  multiplier=max(.75,min(1.4,1+max(-8,min(8,grade))*.038))
  return self._road_length(frm,to)*ENERGY[tr['type']][k]*multiplier*self._road_condition(at,frm,to)
 def _add(self,tr,state,start,end,frm,to,payload=0,**meta):
  if end<start-1e-7:raise ValueError('negative segment')
  before=tr['fuel_l'];duration=max(0,end-start)
  if state in ('outbound','returning','hauling','to_fuel'):
   used=self._travel_fuel(tr,frm,to,start)
  elif state=='refueling':used=0.
  else:used=ENERGY[tr['type']]['idle_l_h']*duration/60 if state not in ('maintenance','shift_change') else 0.
  added=max(0,float(meta.pop('fuel_added_l',0)))
  # The model schedules refueling proactively; record any simulated fuel shortage explicitly.
  if self.fuel_enabled:
   if before+1e-7<used:
    tr['fuel_shortfall_l']=tr.get('fuel_shortfall_l',0.)+(used-before)
   after=max(0,min(tr['tank_l'],before-used+added))
   used=min(before,used)
  else:used=0.;added=0.;after=before
  tr['fuel_l']=after;tr['fuel_used_l']+=used;tr['fuel_added_l']+=added
  tr['segments'].append({'state':state,'start':round(start,6),'end':round(end,6),
    'from':frm,'to':to,'payload':round(payload,3),'fuel_before_l':round(before,5),
    'fuel_after_l':round(after,5),'fuel_used_l':round(used,5),'fuel_added_l':round(added,5),**meta})
 def _shovel_finish(self,site,arrival,capacity):
  options=[]
  for s in self.loads[site]:
   start=max(arrival,s['available']);service=capacity*s['cycle']/s['tons']
   if self.scenario=='shovel_outage' and s['alias']==self.affected:
    if start<self.outage_start+self.outage_duration and start+service>self.outage_start:
     start=max(start,self.outage_start+self.outage_duration)
   options.append((start+service,start,s,service))
  return min(options,key=lambda a:(a[0],a[2]['id']))
 def _choose_load(self,tr,now,frm):
  options=[]
  for i in range(5):
   node=f'L{i}'
   if node==getattr(self,'restricted_load_site',None) and now<getattr(self,'restricted_until',0.):continue
   if self._blocked(now,frm,node):continue
   distance=0. if frm==node else self._road_length(frm,node)
   arrive=now+(0. if frm==node else self._travel(tr,frm,node,now))
   finish,start,_,_=self._shovel_finish(i,arrive,tr['capacity'])
   possible=[j for j in range(5) if not self._blocked(finish,node,f'D{j}') and
             not(self.scenario=='crusher_outage' and self.affected==f'D{j}' and self._in_window(finish,self.outage_start))]
   if not possible:continue
   dump=min(possible,key=lambda j:self._travel(tr,node,f'D{j}',finish))
   haul=self._travel(tr,node,f'D{dump}',finish)
   wait=max(0,start-arrive);predicted=finish+haul+1.
   fuel=0. if frm==node else self._travel_fuel(tr,frm,node,now)
   fuel+=self._travel_fuel(tr,node,f'D{dump}',finish)
   # Distinct objectives; production protects output, fuel protects energy/tonne.
   if self.strategy=='nearest':score=distance
   elif self.strategy=='balanced':score=finish-now
   else:
    time_cost=finish-now+self.policy_weights['dump']*haul+self.policy_weights['queue']*wait+self.policy_weights['site']*i
    fuel_cost=24*fuel/tr['capacity']*(self.fuel_price_kzt/350.0)
    if self.dispatch_objective=='fuel':score=.30*time_cost+fuel_cost*2.5
    elif self.dispatch_objective=='production':score=time_cost
    else:score=.72*time_cost+.65*fuel_cost
   options.append((score,i,predicted,wait,fuel))
  if not options:raise RuntimeError('No accessible loading site')
  score,best,projected,wait,fuel=min(options)
  if self.strategy=='smart' and len(self.actions)<1200:
   self.actions.append({'t':round(now,2),'truck':tr['id'],'target':f'L{best}',
     'predicted_cycle_min':round(projected-now,2),'predicted_queue_min':round(wait,2),
     'estimated_fuel_l':round(fuel,2),'objective':self.dispatch_objective,
     'reason':'weighted estimated finish time, queue and modeled fuel; simulated heuristic'})
  return best
 def _choose_dump(self,tr,now,load):
  options=[]
  for i,units in enumerate(self.dumps):
   frm=f'L{load}';to=f'D{i}'
   if self._blocked(now,frm,to):continue
   if self.scenario=='crusher_outage' and self.affected==to and self._in_window(now,self.outage_start):continue
   dist=self._road_length(frm,to);arrive=now+self._travel(tr,frm,to,now)
   free=min(x['available'] for x in units);wait=max(0,free-arrive)
   fuel=self._travel_fuel(tr,frm,to,now)
   if self.strategy=='nearest':score=dist
   elif self.strategy=='balanced':score=arrive+wait
   elif self.dispatch_objective=='fuel':score=.35*(arrive+wait)+5*fuel*(self.fuel_price_kzt/350.0)
   elif self.dispatch_objective=='production':score=arrive+wait+units[0]['cycle']
   else:score=.75*(arrive+wait)+2.0*fuel*(self.fuel_price_kzt/350.0)
   options.append((score,i))
  if not options:raise RuntimeError('All dump routes unavailable')
  return min(options)[1]
 def _needs_fuel(self,tr,frm,now):
  if not self.fuel_enabled:return False
  # refuel if below 25%, or below bounded predicted cycle+return reserve
  reserve=.12*tr['tank_l'];threshold=.25*tr['tank_l']
  nearby=(0. if frm.startswith('L') else min(self._travel_fuel(tr,frm,station,now) for station in DEFAULT_PUMPS))
  expected_haul=min(self._travel_fuel(tr,'L2',f'D{i}',now) for i in range(5))
  expected_return=min(self._travel_fuel(tr,'D0',f'L{i}',now) for i in (0,3))
  return tr['fuel_l']<max(threshold,nearby+expected_haul+expected_return+reserve)
 def _choose_station(self,tr,frm,now):
  ranked=[]
  for station,pumps in self.pumps.items():
   if self._blocked(now,frm,station):continue
   if frm.startswith('L') and frm!=station:continue
   travel=0 if station==frm else self._travel(tr,frm,station,now)
   arrive=now+travel;free=min(p['available'] for p in pumps)
   start=max(free,arrive)
   if self.scenario=='fuel_station_outage' and self.affected==station and start<self.outage_start+self.outage_duration and start+1>self.outage_start:
    start=max(start,self.outage_start+self.outage_duration)
   ranked.append((start+travel*.15,station,arrive))
  return min(ranked)[1]
 def _hold(self,tr,t,kind,arg,site):
  # A breakdown takes effect on the next safe discrete-event boundary;
  # truck never teleports or stops at a fictional road coordinate.
  if self.scenario=='truck_failure' and tr['id']==self.affected and self._in_window(t,self.outage_start):
   stop=self.outage_start+self.outage_duration
   self._add(tr,'maintenance',t,stop,site,site,0)
   self._event(stop,kind,tr['id'],arg)
   return True
  if self.planned_maintenance and kind in ('dispatch','arrival_load','arrival_fuel'):
   # Repeat maintenance once per simulated day after noon, staggered by truck.
   day=int(t//1440)
   due=day*1440+720+(int(tr['id'][1:])*37)%90
   if t>=due and tr.get('maintenance_day',-1)!=day:
    tr['maintenance_day']=day
    end=t+18.
    self._add(tr,'maintenance',t,end,site,site,0,planned=True)
    self._event(end,kind,tr['id'],arg)
    return True
  if self.shift_change and t>=720:
   shift=int(t//720)*720
   if shift>=720 and tr.get('last_shift',-1)!=shift:
    tr['last_shift']=shift
    end=t+15
    self._add(tr,'shift_change',t,end,site,site,0)
    self._event(end,kind,tr['id'],arg)
    return True
  return False
 def simulate(self,until=None):
  # Incremental simulation leaves future events in the heap. No events are lost
  # when the mine advances in small steps. Legacy simulate() remains supported.
  stop=self.duration if until is None else float(until)
  while self.queue and self.queue[0][0]<=stop+1e-8:
   t,_,kind,key,arg=heapq.heappop(self.queue)
   tr=self.trucks[key]
   if kind=='dispatch':
    frm=arg
    if self._hold(tr,t,kind,arg,frm):continue
    if self._needs_fuel(tr,frm,t):
     station=self._choose_station(tr,frm,t)
     arrive=t if frm==station else t+self._travel(tr,frm,station,t)
     if frm!=station:self._add(tr,'to_fuel',t,arrive,frm,station,0)
     self._event(arrive,'arrival_fuel',key,station)
     continue
    # No L→L intersite roads exist in the source matrix. A truck already
    # at a loading site stays there; queue relief affects dispatches from
    # depot and dump sites only.
    site=(int(frm[1:]) if frm.startswith('L') else self._choose_load(tr,t,frm));to=f'L{site}'
    arr=t if frm==to else t+self._travel(tr,frm,to,t)
    if frm!=to:self._add(tr,'outbound' if frm=='C' else 'returning',t,arr,frm,to,0)
    self._event(arr,'arrival_load',key,site)
   elif kind=='arrival_fuel':
    station=arg
    if self._hold(tr,t,kind,arg,station):continue
    pump=min(self.pumps[station],key=lambda x:x['available'])
    start=max(t,pump['available'])
    if self.scenario=='fuel_station_outage' and self.affected==station and start<self.outage_start+self.outage_duration and start+1>self.outage_start:
     start=max(start,self.outage_start+self.outage_duration)
    if start>t:self._add(tr,'queue_fuel',t,start,station,station,0)
    added=tr['tank_l']-tr['fuel_l']
    end=start+added/pump['rate_l_min']
    self._add(tr,'refueling',start,end,station,station,0,fuel_added_l=added)
    pump['available']=end
    self.fuel_events.append({'truck':key,'station':station,'start':round(start,4),
                            'end':round(end,4),'litres':round(added,3)})
    self._event(end,'dispatch',key,station)
   elif kind=='arrival_load':
    site=int(arg)
    if self._hold(tr,t,kind,arg,f'L{site}'):continue
    finish,start,shovel,_=self._shovel_finish(site,t,tr['capacity'])
    if start>t:self._add(tr,'queue_load',t,start,f'L{site}',f'L{site}',0)
    self._add(tr,'loading',start,finish,f'L{site}',f'L{site}',tr['capacity'],shovel=shovel['id'])
    shovel['available']=finish
    self._event(finish,'finished_load',key,site)
   elif kind=='finished_load':
    load=int(arg)
    if self._hold(tr,t,kind,arg,f'L{load}'):continue
    dump=self._choose_dump(tr,t,load)
    dest=f'D{dump}';arr=t+self._travel(tr,f'L{load}',dest,t)
    self._add(tr,'hauling',t,arr,f'L{load}',dest,tr['capacity'])
    self._event(arr,'arrival_dump',key,(load,dump))
   elif kind=='arrival_dump':
    load,dump=arg;dest=f'D{dump}'
    unit=min(self.dumps[dump],key=lambda x:x['available'])
    start=max(t,unit['available']);end=start+unit['cycle']
    if start>t:self._add(tr,'queue_dump',t,start,dest,dest,tr['capacity'])
    self._add(tr,'unloading',start,end,dest,dest,tr['capacity'])
    unit['available']=end
    self._event(end,'finished_dump',key,(load,dump))
   elif kind=='finished_dump':
    load,dump=arg
    tr['delivered']+=tr['capacity'];tr['trips']+=1;tr['cycles']+=1
    self.deliveries.append({'t':round(t,5),'truck':key,'site':f'D{dump}',
                            'load_site':f'L{load}','tonnes':tr['capacity']})
    self.trips.append({'truck':key,'end_min':round(t,5),'tonnes':tr['capacity'],
      'load_site':f'L{load}','dump_site':f'D{dump}', 'source':'synthetic_simulation'})
    self._event(t,'dispatch',key,f'D{dump}')
  self.completed=until is None
  return self
 def _used_until(self,tr,at):
  used=tr.get('fuel_archived_l',0.);added=tr.get('fuel_added_archived_l',0.)
  for s in tr['segments']:
   if s['start']>=at:break
   d=max(1e-9,s['end']-s['start'])
   frac=min(1,max(0,(at-s['start'])/d))
   used+=s['fuel_used_l']*frac;added+=s['fuel_added_l']*frac
  return used,added
 def archive_before(self,cutoff):
  """Bound active-memory history after daily reports were saved to disk.

  Keep at least the most recent 48 simulated hours. Archived counters preserve
  cumulative tonnes, trips and fuel; completed daily reports preserve detail.
  """
  cutoff=float(cutoff)
  if cutoff<=0:return
  dropped=[d for d in self.deliveries if d['t']<=cutoff]
  self.archived_tonnes+=sum(d['tonnes'] for d in dropped)
  self.archived_trips+=len(dropped)
  self.deliveries=[d for d in self.deliveries if d['t']>cutoff]
  self.trips=[d for d in self.trips if d['end_min']>cutoff]
  self.fuel_events=[e for e in self.fuel_events if e['end']>cutoff]
  for tr in self.trucks.values():
   previous=[s for s in tr['segments'] if s['end']<=cutoff]
   tr['fuel_archived_l']+=sum(s['fuel_used_l'] for s in previous)
   tr['fuel_added_archived_l']+=sum(s['fuel_added_l'] for s in previous)
   tr['segments']=[s for s in tr['segments'] if s['end']>cutoff]

 def advance_to(self,minute):
  """Advance in place; preserve all queues, fuel, activity, and equipment state."""
  minute=float(minute)
  if minute<0:raise ValueError('Simulation time cannot go backward')
  # Not a finite replay. Duration means current reporting horizon for this object.
  self.duration=max(0.01,minute)
  self.simulate(until=minute)
  return self

 def metrics(self):
  tons=round(self.archived_tonnes+sum(d['tonnes'] for d in self.deliveries),2)
  waits=[];tbusy=0.;trefuel=0.;tdowntime=0.;totalfuel=0.;fill_l=0.;shortfall=0.
  for tr in self.trucks.values():
   used,added=self._used_until(tr,self.duration);totalfuel+=used;fill_l+=added
   shortfall+=tr.get('fuel_shortfall_l',0)
   for s in tr['segments']:
    span=max(0,min(self.duration,s['end'])-min(self.duration,s['start'])) if s['start']<self.duration else 0
    if s['state'] in ('hauling','loading','unloading','outbound','returning','to_fuel'):tbusy+=span
    if s['state'] in ('queue_load','queue_dump','queue_fuel'):waits.append(span)
    if s['state'] in ('refueling','queue_fuel'):trefuel+=span
    if s['state'] in ('maintenance','shift_change'):tdowntime+=span
  n=len(self.trucks)
  return {'tonnes':tons,'trips':self.archived_trips+len(self.deliveries),
   'mean_queue_min':round(sum(waits)/len(waits),2) if waits else 0,
   'truck_utilization_pct':round(100*tbusy/(self.duration*n),1),
   'tonnes_per_hour':round(tons*60/self.duration,2),'fleet':n,
   'fuel_used_l':round(totalfuel,2),'fuel_added_l':round(fill_l,2),
   'fuel_l_per_t':round(totalfuel/tons,4) if tons else None,
   'fuel_cost_kzt':round(totalfuel*self.fuel_price_kzt,2),
   'fuel_cost_kzt_per_t':round(totalfuel*self.fuel_price_kzt/tons,2) if tons else None,
   'refuel_events':sum(x['start']<=self.duration for x in self.fuel_events),
   'refuel_busy_min':round(trefuel,1),'downtime_min':round(tdowntime,1),
   'maintenance_events':sum(tr.get('scheduled_maintenance_done',False) for tr in self.trucks.values()),
   'fuel_shortfall_l':round(shortfall,2),'fleet_mix':{k:sum(tr['type']==k for tr in self.trucks.values()) for k in ENERGY},
   'strategy':self.strategy,'scenario':self.scenario,'duration_min':self.duration,
   'seed':self.seed,'objective':self.dispatch_objective,
   'data_provenance':'real-derived OpenMines parameters; hypothetical fuel/grade/failures; simulated operations'}
 def production_curve(self):
  bins=[0.]*(self.duration+1)
  for d in self.deliveries:bins[min(self.duration,int(d['t']))]+=d['tonnes']
  acc=self.archived_tonnes;values=[]
  step=5 if self.duration<=480 else 15
  for i,v in enumerate(bins):
   acc+=v
   if i%step==0 or i==self.duration:values.append({'minute':i,'tonnes':round(acc,2)})
  return values
 def _truck_at(self,tr,t):
  segs=tr['segments']
  if not segs:return {'status':'idle','x':0.,'y':0.,'payload':0.,'route':'C','progress':0.,
                       'fuel_l':round(tr['initial_fuel_l'],1),'tank_l':tr['tank_l']}
  starts=[s['start'] for s in segs]
  idx=bisect.bisect_right(starts,t)-1
  if idx<0:return {'status':'idle','x':0.,'y':0.,'payload':0.,'route':'C','progress':0.,
                    'fuel_l':round(tr['initial_fuel_l'],1),'tank_l':tr['tank_l']}
  s=segs[idx]
  if t>=s['end']:
   at=self.nodes[s['to']];xy=at['x'],at['y'];status='idle';progress=1.
   payload=0 if s['state']=='unloading' else s['payload'];fuel=s['fuel_after_l']
  else:
   progress=max(0,min(1,(t-s['start'])/max(1e-9,s['end']-s['start'])))
   a=self.nodes[s['from']];b=self.nodes[s['to']]
   xy=a['x']+(b['x']-a['x'])*progress,a['y']+(b['y']-a['y'])*progress
   status=s['state'];payload=s['payload']
   fuel=s['fuel_before_l']+(s['fuel_after_l']-s['fuel_before_l'])*progress
  return {'status':status,'x':round(xy[0],4),'y':round(xy[1],4),
    'payload':payload,'route':s['from']+' → '+s['to'],'progress':round(progress,3),
    'current_destination':s['to'],'fuel_l':round(fuel,2),'tank_l':tr['tank_l'],
    'fuel_pct':round(100*fuel/tr['tank_l'],1)}
 def frame(self,t):
  t=max(0.,min(float(self.duration),float(t)))
  snap=[{k:tr[k] for k in ('id','type','capacity','speed')}|self._truck_at(tr,t) for tr in self.trucks.values()]
  delivered=self.archived_tonnes+sum(d['tonnes'] for d in self.deliveries if d['t']<=t)
  finished=self.archived_trips+sum(d['t']<=t for d in self.deliveries)
  states={k:sum(tr['status']==k for tr in snap) for k in
     ('hauling','loading','queue_load','queue_dump','outbound','returning','unloading',
      'to_fuel','queue_fuel','refueling','maintenance','shift_change','idle')}
  fuel=sum(self._used_until(tr,t)[0] for tr in self.trucks.values())
  return {'minute':round(t,1),'trucks':snap,'tonnes':round(delivered,1),
   'fuel_used_l':round(fuel,1),'completed_trips':finished,'states':states,
   'run_seed':self.seed,'strategy':self.strategy,'scenario':self.scenario,
   'timestamp_kind':'simulated_elapsed_minutes'}
 def operations_report(self):
  """Auditable aggregates computed from this run's simulated events.

  Loads are recorded as loading service, not deliveries; fuel and activity spans
  are clipped to the chosen operating window. No fabricated ore-grade or shovel
  fuel quantities are reported.
  """
  hours=math.ceil(self.duration/60)
  hourly=[{'hour':h,'minute':h*60,'delivered_t':0.,'trips':0,'fuel_l':0.,'queue_min':0.,'loading_t':0.} for h in range(hours)]
  sites={f'L{i}':{'site':f'L{i}','loaded_t':0.,'cycles':0,'queue_min':0.,'loading_min':0.,'shovels':len(self.loads[i])} for i in range(5)}
  dumps={f'D{i}':{'site':f'D{i}','delivered_t':0.,'trips':0} for i in range(5)}
  shovels={v['id']:{'shovel':v['id'],'alias':v['alias'],'site':f'L{i}','loaded_t':0.,'cycles':0,'busy_min':0.} for i,unit in enumerate(self.loads) for v in unit}
  classes={k:{'type':k,'trucks':0,'fuel_l':0.,'delivered_t':0.,'trips':0,'refuels':0} for k in ENERGY}
  activities={name:0. for name in ('hauling','returning','outbound','loading','queue_load','queue_dump','unloading','to_fuel','queue_fuel','refueling','maintenance','shift_change','idle')}
  for d in self.deliveries:
   if d['t']>self.duration:continue
   hour=min(hours-1,int(d['t']//60))
   hourly[hour]['delivered_t']+=d['tonnes'];hourly[hour]['trips']+=1
   dumps[d['site']]['delivered_t']+=d['tonnes'];dumps[d['site']]['trips']+=1
   cls=classes[self.trucks[d['truck']]['type']];cls['delivered_t']+=d['tonnes'];cls['trips']+=1
  for ev in self.fuel_events:
   if ev['start']<=self.duration:classes[self.trucks[ev['truck']]['type']]['refuels']+=1
  for tr in self.trucks.values():
   cls=classes[tr['type']];cls['trucks']+=1
   covered=0.
   for s in tr['segments']:
    lo=max(0.,s['start']);hi=min(float(self.duration),s['end']);span=max(0.,hi-lo)
    if not span:continue
    covered+=span
    state=s['state'];activities[state]=activities.get(state,0.)+span
    ratio=span/max(1e-10,s['end']-s['start'])
    fuel=s['fuel_used_l']*ratio;cls['fuel_l']+=fuel
    if state=='loading':
     site=s['from'];vol=s['payload']*ratio
     sites[site]['loaded_t']+=vol;sites[site]['loading_min']+=span
     # A complete loading cycle is counted only when the service completes.
     if s['end']<=self.duration:
      sites[site]['cycles']+=1
      shovel=shovels.get(s.get('shovel'))
      if shovel:shovel['cycles']+=1
     shovel=shovels.get(s.get('shovel'))
     if shovel:shovel['loaded_t']+=vol;shovel['busy_min']+=span
    if state=='queue_load' and s['from'] in sites:sites[s['from']]['queue_min']+=span
    start_hour=max(0,int(lo//60));end_hour=min(hours-1,int((hi-1e-8)//60))
    for h in range(start_hour,end_hour+1):
     tmin=max(lo,h*60);tmax=min(hi,(h+1)*60)
     portion=max(0,tmax-tmin)
     hourly[h]['fuel_l']+=s['fuel_used_l']*portion/max(1e-10,s['end']-s['start'])
     if state in ('queue_load','queue_dump','queue_fuel'):hourly[h]['queue_min']+=portion
     if state=='loading':hourly[h]['loading_t']+=s['payload']*portion/max(1e-10,s['end']-s['start'])
   activities['idle']+=max(0,self.duration-covered)
  def rounded(x):return round(x,2)
  for row in hourly:
   for k in ('delivered_t','fuel_l','queue_min','loading_t'):row[k]=rounded(row[k])
  for row in sites.values():
   for k in ('loaded_t','queue_min','loading_min'):row[k]=rounded(row[k])
  for row in shovels.values():
   for k in ('loaded_t','busy_min'):row[k]=rounded(row[k])
   row['utilization_pct']=round(100*row['busy_min']/self.duration,1)
  for row in classes.values():
   for k in ('delivered_t','fuel_l'):row[k]=rounded(row[k])
  return {'source':'synthetic_simulation','scope':'completed full simulated run',
    'duration_min':self.duration,'strategy':self.strategy,'scenario':self.scenario,'seed':self.seed,
    'metrics':self.metrics(),'hourly':hourly,'loading_sites':list(sites.values()),
    'shovels':list(shovels.values()),'dump_sites':list(dumps.values()),
    'truck_classes':list(classes.values()),'activity_minutes':{k:rounded(v) for k,v in activities.items()},
    'notes':{'loading_t':'Full or partial loading service performed within the run; not identical to delivered tonnes',
      'shovel_fuel':'Not modeled; no fabricated litres are reported',
      'idle':'Unassigned time plus any unmodeled gaps; truck-minute accounting',
      'fuel':'Estimated from configured reference capacities and assumed rates, not field observations'}}

 def public_config(self):
  return {'mine':self.cfg['mine']['name'],'nodes':self.nodes,'fleet':self.all_trucks,
   'shovels':[{'site':f'L{i}','count':len(x),'names':[s['id'] for s in x],
               'aliases':[s['alias'] for s in x]} for i,x in enumerate(self.loads)],
   'dumpers':[{'site':f'D{i}','count':len(x)} for i,x in enumerate(self.dumps)],
   'road_matrix':self.road_l2d,'return_matrix':self.road_d2l,
   'fuel_stations':list(DEFAULT_PUMPS),'fuel_models':ENERGY,
   'duration':self.duration,'scenario':self.scenario,'active_fleet':self.fleet,
   'route_from':self.route_from,'route_to':self.route_to,
   'outage_start':self.outage_start,'outage_duration':self.outage_duration,'affected':self.affected,
   'data_kind':'OpenMines configuration plus modeled fuel, routes and simulated operating events',
   'config_source':'370025263/openmines, north_pit_mine.json (MIT)'}

def compare(strategy='smart',scenario='normal',seed=42,**kwargs):
 baseline=MineRun(strategy='nearest',scenario=scenario,seed=seed,**kwargs).simulate()
 candidate=MineRun(strategy=strategy,scenario=scenario,seed=seed,**kwargs).simulate()
 a=baseline.metrics();b=candidate.metrics()
 change=round(100*(b['tonnes']/a['tonnes']-1),2) if a['tonnes'] else None
 fuel_change=round(100*(b['fuel_used_l']/a['fuel_used_l']-1),2) if a['fuel_used_l'] else None
 return {'baseline':a,'candidate':b,'production_change_pct':change,'fuel_change_pct':fuel_change,
   'baseline_curve':baseline.production_curve(),'candidate_curve':candidate.production_curve()}

def scenario_impact(strategy='smart',scenario='normal',seed=42,**kwargs):
 normal_run=MineRun(strategy=strategy,scenario='normal',seed=seed,**kwargs).simulate()
 changed_run=MineRun(strategy=strategy,scenario=scenario,seed=seed,**kwargs).simulate()
 normal=normal_run.metrics();changed=changed_run.metrics()
 return {'normal':normal,'disrupted':changed,
   'normal_curve':normal_run.production_curve(),
   'disrupted_curve':changed_run.production_curve(),
   'lost_tonnes':round(normal['tonnes']-changed['tonnes'],2),
   'extra_fuel_l':round(changed['fuel_used_l']-normal['fuel_used_l'],2)}

def paired_benchmark(strategy='smart',scenario='normal',seeds=range(21,32),**kwargs):
 results=[]
 for seed in seeds:
  comp=compare(strategy=strategy,scenario=scenario,seed=seed,**kwargs)
  results.append({'seed':seed,'baseline_t':comp['baseline']['tonnes'],
    'candidate_t':comp['candidate']['tonnes'],'change_pct':comp['production_change_pct'],
    'baseline_queue':comp['baseline']['mean_queue_min'],
    'candidate_queue':comp['candidate']['mean_queue_min'],
    'baseline_fuel_l':comp['baseline']['fuel_used_l'],
    'candidate_fuel_l':comp['candidate']['fuel_used_l']})
 changes=[x['change_pct'] for x in results if x['change_pct'] is not None]
 return {'runs':results,'mean_change_pct':round(sum(changes)/len(changes),2) if changes else None,
   'all_seeds_better':bool(changes) and all(x>0 for x in changes),'n':len(results)}
