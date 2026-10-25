"""Continuously advancing, restartable simulation. All sensor values are modeled.

This component *does not* claim field telemetry, and intentionally does not
reset trucks at midnight. Scenarios branch from the identical saved mine state.
"""
from __future__ import annotations
import copy, datetime, json, os, pickle, threading, time, uuid, shutil
from pathlib import Path
from engine import MineRun

STATE_DIR=Path(os.getenv('OREFLOW_STATE_DIR','/app/state'))
ALLOWED_RATES=(0,1,5,15,60)
ALLOWED_INCIDENTS=('road_closure','shovel_outage','truck_failure','fuel_station_outage','crusher_outage','road_degradation')


def window_report(run,start,end):
    """Daily or recent-window aggregation from actual calculated events."""
    end=float(end);start=float(start)
    duration=max(1e-9,end-start)
    deliveries=[d for d in run.deliveries if start<d['t']<=end]
    fuels=0.;queue=0.;busy=0.;downtime=0.;load_sites={f'L{i}':{'site':f'L{i}','loaded_t':0.,'queue_min':0.,'cycles':0} for i in range(5)}
    active_shovels={s['id']:{'shovel':s['id'],'site':f'L{i}','tonnes':0.,'busy_min':0.} for i,l in enumerate(run.loads) for s in l}
    state_minutes={}
    hourly=[{'minute':int(t),'delivered_t':0.,'fuel_l':0.,'queue_min':0.} for t in range(int(start//60)*60,int(end//60)*60+60,60)]
    def add_hour(t0,t1,attribute,amount):
        for h in hourly:
            o=max(0.,min(t1,h['minute']+60)-max(t0,h['minute']))
            if o: h[attribute]+=amount*o/(t1-t0) if t1>t0 else 0
    for d in deliveries:
        for h in hourly:
            if h['minute']<d['t']<=h['minute']+60:
                h['delivered_t']+=d['tonnes'];break
    for tr in run.trucks.values():
        for seg in tr['segments']:
            lo=max(start,seg['start']);hi=min(end,seg['end'])
            if hi<=lo:continue
            fraction=(hi-lo)/max(1e-9,seg['end']-seg['start'])
            burn=seg['fuel_used_l']*fraction
            fuels+=burn;add_hour(lo,hi,'fuel_l',burn)
            state=seg['state'];state_minutes[state]=state_minutes.get(state,0.)+hi-lo
            if state in ('outbound','hauling','returning','loading','unloading','to_fuel'):busy+=hi-lo
            if state in ('queue_load','queue_dump','queue_fuel'):
                queue+=hi-lo;add_hour(lo,hi,'queue_min',hi-lo)
            if state in ('maintenance','shift_change'):downtime+=hi-lo
            if state=='queue_load' and seg['from'] in load_sites:
                load_sites[seg['from']]['queue_min']+=hi-lo
            if state=='loading' and seg['from'] in load_sites:
                vol=seg['payload']*fraction
                load_sites[seg['from']]['loaded_t']+=vol
                if start<seg['end']<=end:load_sites[seg['from']]['cycles']+=1
                shovel=active_shovels.get(seg.get('shovel'))
                if shovel:shovel['tonnes']+=vol;shovel['busy_min']+=hi-lo
    n=max(1,len(run.trucks))
    tonnes=sum(d['tonnes'] for d in deliveries)
    for d in (load_sites,active_shovels):
        for row in d.values():
            for k in ('loaded_t','queue_min','tonnes','busy_min'):
                if k in row:row[k]=round(row[k],1)
    for h in hourly:
        for key in ('delivered_t','fuel_l','queue_min'):h[key]=round(h[key],1)
    return {'start_min':round(start,2),'end_min':round(end,2),'tonnes':round(tonnes,1),'trips':len(deliveries),
            'fuel_l':round(fuels,1),'fuel_l_per_t':round(fuels/tonnes,4) if tonnes else None,
            'avg_fleet_utilization_pct':round(100*busy/(duration*n),1),
            'waiting_truck_hours':round(queue/60,2),'downtime_truck_hours':round(downtime/60,2),
            'hourly':hourly,'load_sites':list(load_sites.values()),
            'shovels':sorted(active_shovels.values(),key=lambda x:x['tonnes'],reverse=True),
            'fleet_state_hours':{k:round(v/60,2) for k,v in state_minutes.items()},
            'units':'Modeled tonnes, modeled litres, simulated minutes; not field measurements'}

class ContinuousMine:
    def __init__(self,state_dir=STATE_DIR):
        self.dir=Path(state_dir);self.dir.mkdir(parents=True,exist_ok=True)
        self.checkpoint=self.dir/'mine-state.pkl'
        self.lock=threading.RLock()
        self.run_id='continuous-'+uuid.uuid4().hex[:12]
        self.run=MineRun(strategy='smart',duration=1440,seed=42)
        self.minute=0.;self.rate=5.;self.playing=True
        self.events=[];self.days=[];self.next_day=1
        self.job={'status':'idle'}
        self.latest_advice=None;self.next_auto_check=60.;self.auto_running=False
        self._last_tick=time.monotonic();self._last_save=time.monotonic()
        self._load()

    def _load(self):
        if not self.checkpoint.exists():return
        try:
            # Trusted checkpoint created by this service in its private Docker volume.
            with self.checkpoint.open('rb') as f:doc=pickle.load(f)
            if doc.get('schema')!=2:raise ValueError('unsupported checkpoint schema')
            self.run=doc['run'];self.minute=float(doc['minute']);self.run_id=doc['run_id']
            self.run.restricted_load_site=getattr(self.run,'restricted_load_site',None)
            self.run.restricted_until=getattr(self.run,'restricted_until',0.)
            self.rate=float(doc['rate']);self.playing=bool(doc['playing'])
            self.events=doc['events'];self.days=doc['days'];self.next_day=int(doc['next_day'])
            self.latest_advice=doc.get('latest_advice');self.next_auto_check=float(doc.get('next_auto_check',self.minute+60))
            self.events.append({'minute':round(self.minute,2),'type':'system','text':'Mine resumed from saved checkpoint'})
        except Exception as e:
            # Fail closed rather than quietly wiping state or resetting production.
            raise RuntimeError(f'Cannot read mine checkpoint at {self.checkpoint}: {e}') from e
        finally:self._last_tick=time.monotonic()

    def save(self):
        with self.lock:
            doc={'schema':2,'run':self.run,'minute':self.minute,'run_id':self.run_id,
                 'rate':self.rate,'playing':self.playing,'events':self.events[-250:],
                 'days':self.days,'next_day':self.next_day,
                 'latest_advice':self.latest_advice,'next_auto_check':self.next_auto_check}
            tmp=self.checkpoint.with_suffix('.tmp')
            with tmp.open('wb') as f:
                pickle.dump(doc,f,protocol=5);f.flush();os.fsync(f.fileno())
            os.replace(tmp,self.checkpoint)
            self._last_save=time.monotonic()

    def tick(self):
        with self.lock:
            now=time.monotonic();dt=max(0,min(now-self._last_tick,5.))
            self._last_tick=now
            if self.playing:
                target=self.minute+dt*self.rate
                self.run.advance_to(target);self.minute=target
                while self.minute>=self.next_day*1440:
                    start=(self.next_day-1)*1440;stop=self.next_day*1440
                    rep=window_report(self.run,start,stop)
                    rep['day']=self.next_day
                    self.days.append(rep)
                    path=self.dir/f'day-{self.next_day:05}.json'
                    path.write_text(json.dumps(rep,ensure_ascii=False),encoding='utf-8')
                    self.events.append({'minute':stop,'type':'report','text':f'Day {self.next_day} operations report saved'})
                    self.next_day+=1
                    # Reports are durable before older raw events are compacted.
                    self.run.archive_before(max(0,stop-2880))
            if self.playing and self.minute>=self.next_auto_check and not self.auto_running and self.job.get('status')!='running':
                self.next_auto_check=self.minute+120 # throttled 2 simulated hours
                # Only evaluate automatically on meaningful modeled congestion.
                statuses=self.run.frame(self.minute)['states']
                if statuses.get('queue_load',0)>=12:
                    self.auto_running=True
                    threading.Thread(target=self._auto_advice,daemon=True).start()
            if now-self._last_save>=30:self.save()

    def _auto_advice(self):
        try:
            answer=self._evaluate('advice',{'horizon_hours':2})
            with self.lock:
                self.latest_advice=answer
                self.events.append({'minute':round(answer['at_min'],2),'type':'advice',
                                    'text':'Dispatch alternatives tested. Open Recommendations for the evidence.'})
        except Exception as exc:
            with self.lock:self.events.append({'minute':round(self.minute,2),'type':'advice_error','text':str(exc)})
        finally:
            with self.lock:self.auto_running=False

    def fresh_start(self):
        """Explicit user-requested new mine. Archive old checkpoint and daily files."""
        with self.lock:
            self.tick()
            self.save()
            archive=self.dir/'previous_runs'/datetime.datetime.now(datetime.timezone.utc).strftime('%Y%m%dT%H%M%SZ')
            if archive.exists():archive=archive.with_name(archive.name+'-'+uuid.uuid4().hex[:6])
            archive.mkdir(parents=True)
            if self.checkpoint.exists():shutil.move(str(self.checkpoint),str(archive/'mine-state.pkl'))
            for report in sorted(self.dir.glob('day-*.json')):
                shutil.move(str(report),str(archive/report.name))
            self.run=MineRun(strategy='smart',duration=1440,seed=42)
            self.run_id='continuous-'+uuid.uuid4().hex[:12]
            self.minute=0.;self.rate=5.;self.playing=True
            self.events=[{'minute':0.,'type':'system','text':'New mine started from original North Pit configuration'}]
            self.days=[];self.next_day=1;self.job={'status':'idle'}
            self.latest_advice=None;self.next_auto_check=60.;self.auto_running=False
            self._last_tick=time.monotonic()
            self.save()
            return {'started':True,'run_id':self.run_id,'minute':0.,'previous_run_archived':True,
                    'archive_folder':archive.name,'note':'Only simulated operating history reset; source mine parameters unchanged.'}

    def control(self,obj):
        with self.lock:
            self.tick()
            if 'playing' in obj:self.playing=bool(obj['playing'])
            if 'rate' in obj:
                v=float(obj['rate'])
                if v not in ALLOWED_RATES or v==0:raise ValueError('Choose one of the supported speeds')
                self.rate=v
            self.save()
            return self.snapshot()

    def snapshot(self):
        with self.lock:
            self.tick()
            f=self.run.frame(self.minute)
            bysite={f'L{i}':{'queue':0,'loading':0,'total':0} for i in range(5)}
            for truck in f['trucks']:
                node=truck.get('current_destination')
                if node in bysite:
                    bysite[node]['total']+=1
                    if truck['status']=='queue_load':bysite[node]['queue']+=1
                    if truck['status']=='loading':bysite[node]['loading']+=1
            alerts=[]
            for site,row in bysite.items():
                if row['queue']>=8:alerts.append({'severity':'attention','title':f'Queue at {site}','message':f'{row["queue"]} trucks waiting for loading','site':site,'action':'Review dispatch alternatives'})
            for site,row in bysite.items():
                if row['loading']==0 and row['total']>5:
                    alerts.append({'severity':'notice','title':f'Low loading activity at {site}','message':'Inspect queue and shovel availability before assuming failure','site':site})
            f.update({'run_id':self.run_id,'continuous':True,'playing':self.playing,'rate':self.rate,
                      'day':int(self.minute//1440)+1,'time_of_day_min':round(self.minute%1440,1),
                      'active_policy':self.run.strategy,'alerts':alerts[:8],
                      'sites':bysite,'recent_events':self.events[-12:],
                      'completed_days':len(self.days),'kind':'simulated_operation',
                      'suggestion':self.latest_advice if self.latest_advice and self.minute-self.latest_advice.get('at_min',0)<180 else None})
            return f

    def _clone(self,policy=None,incident=None,params=None,base_run=None,base_minute=None):
        run=copy.deepcopy(self.run if base_run is None else base_run)
        start_min=self.minute if base_minute is None else base_minute
        if policy:run.strategy=policy
        if incident:
            opts=params or {}
            if incident not in ALLOWED_INCIDENTS:raise ValueError('Unsupported scenario')
            run.scenario=incident
            run.outage_duration=float(opts.get('duration_min',120))
            if not 5<=run.outage_duration<=480:raise ValueError('Outage length must be 5–480 minutes')
            start=start_min+float(opts.get('delay_min',15))
            if not 0<=float(opts.get('delay_min',15))<=240:raise ValueError('Delay must be 0–240 minutes')
            run.outage_start=start;run.closure_start=start
            if incident in ('road_closure','road_degradation'):
                frm=opts.get('road_from','L2');to=opts.get('road_to','D4')
                run._road_length(frm,to) # validate true road
                run.route_from=frm;run.route_to=to
            elif incident=='shovel_outage':
                names=[s['alias'] for site in run.loads for s in site]
                affected=opts.get('affected','shovel-3-1')
                if affected not in names:raise ValueError('Invalid shovel')
                run.affected=affected
            elif incident=='truck_failure':
                affected=opts.get('affected','T001')
                if affected not in run.trucks:raise ValueError('Invalid truck')
                run.affected=affected
            elif incident=='fuel_station_outage':
                affected=opts.get('affected','L3')
                if affected not in run.pumps:raise ValueError('Invalid fuel station')
                run.affected=affected
            elif incident=='crusher_outage':
                affected=opts.get('affected','D0')
                if affected not in {f'D{i}' for i in range(5)}:raise ValueError('Invalid dump')
                run.affected=affected
        return run

    def _evaluate(self,kind,payload):
        # Snapshot the current state once under the lock. CPU-heavy forecast
        # branches run outside it, so the operating mine remains responsive.
        with self.lock:
            self.tick()
            now=self.minute
            baseline=copy.deepcopy(self.run)
        hours=int(payload.get('horizon_hours',4))
        if hours not in (2,4,8):raise ValueError('Choose a 2, 4 or 8 hour forecast')
        until=now+hours*60
        current=window_report(baseline,max(0,now-60),now)
        if kind=='advice':
            policies=('nearest','balanced','smart')
            results=[]
            for policy in policies:
                run=copy.deepcopy(baseline)
                run.strategy=policy
                run.advance_to(until)
                a=window_report(run,now,until)
                results.append({'policy':policy,'tonnes':a['tonnes'],'fuel_l':a['fuel_l'],
                                'fuel_l_per_t':a['fuel_l_per_t'],'queue_truck_hours':a['waiting_truck_hours']})
            best=max(x['tonnes'] for x in results)
            eligible=[x for x in results if x['tonnes']>=.99*best]
            recommendation=min(eligible,key=lambda x:(x['fuel_l_per_t'] if x['fuel_l_per_t'] is not None else 1e12))
            current_policy=baseline.strategy
            current_row=next(x for x in results if x['policy']==current_policy)
            same=abs(recommendation['tonnes']-current_row['tonnes'])<=.005*max(1,current_row['tonnes']) and abs(recommendation['fuel_l']-current_row['fuel_l'])<=.01*max(1,current_row['fuel_l'])
            if same:recommendation=current_row
            # Test a concrete, limited congestion intervention from exactly
            # the same saved machine state. This affects FUTURE dispatch only;
            # it cannot invalidate pre-booked loading slots or teleport trucks.
            snapshot=baseline.frame(now)
            sites={f'L{i}':0 for i in range(5)}
            for truck in snapshot['trucks']:
                if truck['status']=='queue_load' and truck.get('current_destination') in sites:
                    sites[truck['current_destination']]+=1
            worst=max(sites,key=lambda site:sites[site])
            relief=None
            if sites[worst]>=8:
                branch=copy.deepcopy(baseline)
                branch.restricted_load_site=worst
                branch.restricted_until=now+min(60.,hours*60.)
                branch.advance_to(until)
                measured=window_report(branch,now,until)
                current_report=next(x for x in results if x['policy']==current_policy)
                delta_t=measured['tonnes']-current_report['tonnes']
                delta_wait=measured['waiting_truck_hours']-current_report['queue_truck_hours']
                justified=(delta_t>max(50.,current_report['tonnes']*.005) or
                  (delta_t>=-max(50.,current_report['tonnes']*.005) and delta_wait<-1.))
                relief={'site':worst,'queued_now':sites[worst],
                    'action':'Temporarily exclude this loading site from new dispatch assignments',
                    'duration_min':min(60.,hours*60.),'forecast_t':measured['tonnes'],
                    'forecast_wait_truck_hours':measured['waiting_truck_hours'],
                    'change_t':round(delta_t,1),'change_wait_truck_hours':round(delta_wait,2),
                    'recommended':justified,
                    'reason':('Simulated alternative improves output or cuts waiting without a material output penalty.'
                        if justified else 'No reliable benefit found from excluding this site for new assignments.'),
                    'limitation':'Existing queue reservations are not forcibly reassigned.'}
            return {'kind':'advice','at_min':round(now,2),'horizon_hours':hours,'options':results,
                    'recommended_policy':recommendation['policy'],
                    'current_policy':current_policy,
                    'reason':('Current policy is competitive; no change recommended.' if recommendation['policy']==current_policy else f'{recommendation["policy"].title()} maintains at least 99% of the best forecast output and uses fewer modeled litres per tonne among eligible alternatives.'),
                    'method':'Branch from identical in-progress mine state; deterministic event simulation; one-seed scenario evaluation, not a field-validated prediction',
                    'recent_hour':current,'site_relief':relief}
        if kind=='scenario':
            incident=payload.get('scenario','road_closure')
            normal=copy.deepcopy(baseline)
            changed=self._clone(incident=incident,params=payload,base_run=baseline,base_minute=now)
            normal.advance_to(until);changed.advance_to(until)
            a=window_report(normal,now,until);b=window_report(changed,now,until)
            # Test whether rerouting under another policy helps during this
            # disruption. A different strategy is recommended only when an
            # actual branch produces a defensible improvement.
            recovery=[]
            for policy in ('nearest','balanced','smart'):
                if policy==baseline.strategy:
                    sample=b
                else:
                    candidate=self._clone(incident=incident,params=payload,base_run=baseline,base_minute=now)
                    candidate.strategy=policy
                    candidate.advance_to(until)
                    sample=window_report(candidate,now,until)
                recovery.append({'policy':policy,'tonnes':sample['tonnes'],'fuel_l':sample['fuel_l'],
                                 'fuel_l_per_t':sample['fuel_l_per_t']})
            # The third branch is independently simulated and supports charts
            # and affected-equipment visual overlays. Never touch live C.run.
            recovery_runs={}
            for r in recovery:
                run=(changed if r['policy']==baseline.strategy else
                    self._clone(incident=incident,params=payload,base_run=baseline,base_minute=now))
                if run is not changed:
                    run.strategy=r['policy'];run.advance_to(until)
                recovery_runs[r['policy']]=run
            best=max(x['tonnes'] for x in recovery)
            eligible=[x for x in recovery if x['tonnes']>=best*.99]
            choice=min(eligible,key=lambda x:x['fuel_l_per_t'] if x['fuel_l_per_t'] is not None else 1e12)
            improves=choice['policy']!=baseline.strategy and (choice['tonnes']>b['tonnes']*1.005 or
                      (choice['tonnes']>=b['tonnes']*.995 and choice['fuel_l']<b['fuel_l']*.99))
            mitigation={'recommended_policy':choice['policy'] if improves else baseline.strategy,
                        'improvement_t':round(choice['tonnes']-b['tonnes'],1) if improves else 0,
                        'fuel_change_l':round(choice['fuel_l']-b['fuel_l'],1) if improves else 0,
                        'alternatives':recovery,
                        'reason':('Alternative dispatch reduces the modeled impact.' if improves else
                                  'No tested dispatch change was materially better; keep the current policy.')}
            winning_run=recovery_runs[mitigation['recommended_policy']]
            winning_report=window_report(winning_run,now,until)
            # Compare all trucks' states and assignments at a common moment
            # during the event; absence of differences is reported honestly.
            event_at=min(until,now+float(payload.get('delay_min',15))+min(30.,float(payload.get('duration_min',120))/2))
            before=normal.frame(event_at);after=changed.frame(event_at)
            by_id={t['id']:t for t in before['trucks']}
            changed_ids=[t['id'] for t in after['trucks'] if
                 (t['status'],t.get('route'),t.get('current_destination'))!=
                 (by_id[t['id']]['status'],by_id[t['id']].get('route'),by_id[t['id']].get('current_destination'))]
            preview={'at_min':round(event_at,1),'normal_trucks':before['trucks'],
                     'disrupted_trucks':after['trucks'],'affected_truck_ids':changed_ids,
                     'normal_assets':normal.asset_states(event_at),
                     'disrupted_assets':changed.asset_states(event_at)}
            return {'kind':'scenario','scenario':incident,'at_min':round(now,2),'horizon_hours':hours,
                    'normal':a,'changed':b,'recovered':winning_report,'scenario_preview':preview,'tonnes_delta':round(b['tonnes']-a['tonnes'],1),
                    'fuel_delta_l':round(b['fuel_l']-a['fuel_l'],1),'mitigation':mitigation,
                    'interpretation':('No meaningful production effect in this model window.' if abs(b['tonnes']-a['tonnes'])<=.01*max(1,a['tonnes']) else ('Delivery decreases under this modeled disruption.' if b['tonnes']<a['tonnes'] else 'Delivery increases under this modeled disruption; investigate rerouting and congestion rather than assuming a benefit.')),
                    'method':'Both branches begin with the same equipment states, tank levels, queues and random seed. Forecast only; no live change applied.'}
        raise ValueError('Unknown evaluation')

    def evaluate(self,kind,obj):
        with self.lock:
            if self.job.get('status')=='running':raise ValueError('An evaluation is already running')
            self.job={'status':'running','type':kind,'detail':'Testing branches from current mine state'}
        def run():
            try:
                answer=self._evaluate(kind,obj)
                with self.lock:self.job={'status':'done','type':kind,'result':answer}
            except Exception as e:
                with self.lock:self.job={'status':'error','type':kind,'detail':str(e)}
        threading.Thread(target=run,daemon=True).start()
        return {'status':'running'}

    def apply_policy(self,obj):
        policy=obj.get('policy')
        if policy not in ('nearest','balanced','smart'):raise ValueError('Invalid policy')
        with self.lock:
            self.tick()
            self.run.strategy=policy
            self.latest_advice=None
            self.events.append({'minute':round(self.minute,2),'type':'dispatch','text':f'Dispatch policy set to {policy}. Current trips finish before reassignment.'})
            self.save()
            return {'policy':policy,'applies':'future dispatch events only'}

    def apply_site_relief(self,obj):
        # No failure is ever introduced by this endpoint. Only a recently
        # evaluated, beneficial site restriction may be applied.
        with self.lock:
            self.tick()
            result=self.job.get('result') if self.job.get('status')=='done' else None
            relief=result.get('site_relief') if result and result.get('kind')=='advice' else None
            if not relief or not relief.get('recommended'):
                raise ValueError('No tested beneficial queue-relief plan available')
            if relief['site']!=obj.get('site'):
                raise ValueError('Requested site does not match tested plan')
            if self.minute-float(result['at_min'])>5:
                raise ValueError('Evaluation is stale; re-evaluate first')
            self.run.restricted_load_site=relief['site']
            self.run.restricted_until=self.minute+relief['duration_min']
            self.latest_advice=None
            self.events.append({'minute':round(self.minute,2),'type':'dispatch',
               'text':f'Queue-relief trial active: future assignments avoid {relief["site"]} for {relief["duration_min"]:.0f} minutes'})
            self.save()
            return {'applied':True,'action':'site_restriction','site':relief['site'],
                    'effective_until_min':self.run.restricted_until,
                    'existing_queued_trucks':'unchanged'}

    def apply_scenario(self,obj):
        with self.lock:
            self.tick()
            self._clone(incident=obj.get('scenario'),params=obj) # validate first
            incident=obj['scenario'];self.run.scenario=incident
            self.latest_advice=None
            self.run.outage_duration=float(obj.get('duration_min',120))
            self.run.outage_start=self.minute+float(obj.get('delay_min',15))
            self.run.closure_start=self.run.outage_start
            if incident in ('road_closure','road_degradation'):
                self.run.route_from=obj.get('road_from','L2');self.run.route_to=obj.get('road_to','D4')
            else:self.run.affected=obj.get('affected',{'shovel_outage':'shovel-3-1','truck_failure':'T001','fuel_station_outage':'L3','crusher_outage':'D0'}.get(incident,''))
            self.events.append({'minute':round(self.minute,2),'type':'incident','text':f'{incident.replace("_"," ").title()} scheduled for minute {self.run.outage_start:.0f}'})
            self.save()
            return {'applied':True,'starts_min':self.run.outage_start,'ends_min':self.run.outage_start+self.run.outage_duration}

    def daily(self):
        with self.lock:
            self.tick()
            start=max(0,self.minute-1440)
            return {'current':window_report(self.run,start,self.minute),
                    'completed_days':[{'day':d['day'],'tonnes':d['tonnes'],'fuel_l':d['fuel_l'],'trips':d['trips']} for d in self.days[-30:]],
                    'operating_min':round(self.minute,2),'report_window':'rolling 24 simulated hours'}

    def loop(self):
        while True:
            try:self.tick()
            except Exception as e:
                with self.lock:
                    self.playing=False;self.events.append({'minute':round(self.minute,1),'type':'error','text':str(e)})
            time.sleep(.5)
