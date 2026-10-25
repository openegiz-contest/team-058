"""OreFlow API, playback clock and MQTT gateway; standard-library HTTP server."""
import base64
import csv
import io
import hashlib
import json
import os
import re
import sys
import threading
import time
import urllib.error
import urllib.request
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from urllib.parse import quote
from pathlib import Path
from engine import MineRun, compare, scenario_impact, paired_benchmark, NAMESPACE
from continuous import ContinuousMine, window_report

HERE=Path(__file__).parent
PORT=int(os.environ.get('OREFLOW_PORT','8099'))
DITTO_URL=os.environ.get('DITTO_URL','http://localhost:8080').rstrip('/')
DITTO_USER=os.environ.get('DITTO_USER','ditto')
DITTO_PASSWORD=os.environ.get('DITTO_PASSWORD','')
MQTT_HOST=os.environ.get('MQTT_HOST','')
MQTT_PORT=int(os.environ.get('MQTT_PORT','1883'))


def dump(obj):return json.dumps(obj,ensure_ascii=False,separators=(',',':')).encode()


class State:
    def __init__(self):
        self.lock=threading.RLock()
        self.run=MineRun().simulate()
        self.run_id='northpit-default-42'
        # Legacy full-run comparisons are computed only if the legacy endpoint
        # is requested; do not block V2.3 continuous server startup.
        self.comparison=None
        self.impact=None
        self.minute=0.
        self.playing=True
        self.speed=self.run.duration/90.0 # 90 real seconds per complete simulated run
        self.last=time.monotonic()
        self.mqtt_ok=False
        self.mqtt_error='MQTT not started'
        self.last_publish=0.
        self._road_state_cache={}
        self.last_published_run=''
        self.benchmark=None
        self._report=None
        self._last_activation_key=None
        self.job={'status':'idle','detail':'No calculation running'}
        self._client=None

    def tick(self):
        now=time.monotonic()
        dt=max(0,min(30,now-self.last))
        if self.playing:self.minute=min(float(self.run.duration),self.minute+dt*self.speed)
        if self.minute>=self.run.duration:self.playing=False
        self.last=now

    def activate(self,payload):
        allowed={'strategy','scenario','seed','fleet','fleet_mix','duration',
                 'affected','route_from','route_to','closure_start','outage_start',
                 'outage_duration','dispatch_objective','fuel_price_kzt'}
        unknown=set(payload)-allowed
        if unknown:raise ValueError('Unsupported configuration keys: '+', '.join(sorted(unknown)))
        duration=int(payload.get('duration',1440))
        if duration not in (240,720,1440,2880):
            raise ValueError('Choose 240, 720, 1440 or 2880 simulation minutes')
        kwargs={k:payload[k] for k in allowed if k in payload and payload[k] is not None}
        kwargs.setdefault('strategy','smart')
        kwargs.setdefault('scenario','normal')
        kwargs.setdefault('seed',42)
        kwargs.setdefault('duration',1440)
        kwargs.setdefault('fleet',71)
        # Bounded exact replay: one previous complete scenario, with no growing
        # model cache. A matching request returns the actual existing run.
        exact_key=json.dumps(kwargs,sort_keys=True,separators=(',',':'))
        with self.lock:
            if self._last_activation_key==exact_key:
                self.minute=0.;self.playing=False;self.last=time.monotonic()
                return {'run_id':self.run_id,'metrics':self.run.metrics(),
                    'comparison':self.comparison,'scenario_impact':self.impact,
                    'cache_hit':True},200
        # Make default schedule sensible for shorter experiments.
        kwargs.setdefault('closure_start',min(480,duration//3))
        kwargs.setdefault('outage_start',min(480,duration//3))
        kwargs.setdefault('outage_duration',min(120,duration//4))
        # Compute each required scenario once rather than repeating the same
        # simulation in compare() and scenario_impact(). Same paired seed & config.
        run=MineRun(**kwargs).simulate()
        baseline_kwargs={**kwargs,'strategy':'nearest'}
        base=run if run.strategy=='nearest' else MineRun(**baseline_kwargs).simulate()
        a=base.metrics();b=run.metrics()
        paired={'baseline':a,'candidate':b,
            'production_change_pct':round(100*(b['tonnes']/a['tonnes']-1),2) if a['tonnes'] else None,
            'fuel_change_pct':round(100*(b['fuel_used_l']/a['fuel_used_l']-1),2) if a['fuel_used_l'] else None,
            'baseline_curve':base.production_curve(),'candidate_curve':run.production_curve()}
        normal=run if run.scenario=='normal' else MineRun(**{**kwargs,'scenario':'normal'}).simulate()
        c=normal.metrics()
        impact={'normal':c,'disrupted':b,
            'normal_curve':normal.production_curve(),'disrupted_curve':run.production_curve(),
            'lost_tonnes':round(c['tonnes']-b['tonnes'],2),
            'extra_fuel_l':round(b['fuel_used_l']-c['fuel_used_l'],2)}
        rid='np21-'+hashlib.sha256(dump(kwargs)).hexdigest()[:12]
        report=run.operations_report()
        with self.lock:
            self.run=run;self.comparison=paired;self.impact=impact
            self.minute=0.;self.playing=False
            self.speed=run.duration/90.0
            self.run_id=rid;self.last=time.monotonic();self.benchmark=None
            self._report=report
            self._last_activation_key=exact_key
            self.last_published_run=''
        return {'run_id':rid,'metrics':run.metrics(),'comparison':paired,
                'scenario_impact':impact},200

    def start_job(self,payload):
        with self.lock:
            if self.job['status']=='running':
                raise ValueError('A simulation experiment is already running')
            self.job={'status':'running','detail':'Recalculating real simulation events'}
        def worker():
            try:
                result,_=self.activate(payload)
                with self.lock:self.job={'status':'done','detail':'Completed','result':result}
            except Exception as exc:
                with self.lock:self.job={'status':'error','detail':str(exc)}
        threading.Thread(target=worker,daemon=True).start()
        return {'status':'running','detail':'Recalculating simulation; current run remains visible'}

    def snapshot(self,minute=None):
        with self.lock:
            self.tick()
            t=self.minute if minute is None else max(0,min(self.run.duration,float(minute)))
            frame=self.run.frame(t)
            frame['run_id']=self.run_id
            frame['source']='OpenMines North Pit config; OreFlow simulated events'
            frame['clock']={'playing':self.playing,'speed':self.speed,'global_minute':round(self.minute,2)}
            return frame

    def control(self,obj):
        with self.lock:
            self.tick()
            if 'seek' in obj:self.minute=max(0,min(self.run.duration,float(obj['seek'])))
            if 'play' in obj:self.playing=bool(obj['play'])
            if 'speed' in obj:
                v=float(obj['speed'])
                if not (0.05<=v<=100):raise ValueError('unsupported playback rate')
                self.speed=v
            if obj.get('reset'):self.minute=0.;self.playing=False
            self.last=time.monotonic()
            return self.snapshot()

    def mqtt_init(self):
        if not MQTT_HOST:return
        try:
            import paho.mqtt.client as mqtt
        except ImportError:
            self.mqtt_error='paho-mqtt is not installed';return
        client=mqtt.Client(mqtt.CallbackAPIVersion.VERSION2,client_id=f'oreflow-twin-{os.getpid()}')
        def connected(client,userdata,flags,reason_code,properties):
            self.mqtt_ok=not reason_code.is_failure
            self.mqtt_error='' if self.mqtt_ok else f'MQTT connection refused: {reason_code}'
        def disconnected(client,userdata,flags,reason_code,properties):
            self.mqtt_ok=False;self.mqtt_error=f'MQTT disconnected: {reason_code}'
        client.on_connect=connected;client.on_disconnect=disconnected
        try:
            client.connect_async(MQTT_HOST,MQTT_PORT,keepalive=45);client.loop_start()
            self._client=client
        except Exception as e:self.mqtt_error=str(e)

    def send_twin(self,id_,props):
        if not self.mqtt_ok or not self._client:return
        msg={'topic':f'{NAMESPACE}/{id_}/things/twin/commands/modify','path':'/features',
             'value':{k:{'properties':{'value':v}} for k,v in props.items()}}
        info=self._client.publish(f'telemetry/{id_}',json.dumps(msg),qos=0)
        if info.rc!=0:self.mqtt_error=f'MQTT publish rc={info.rc}';self.mqtt_ok=False

    def publish(self):
        snap=self.snapshot()
        rid=snap['run_id'];minute=snap['minute']
        self.send_twin('mine-01',{'delivered_t':snap['tonnes'],'trips':snap['completed_trips'],
                                  'sim_minute':minute,'run_id':rid,'fleet':len(snap['trucks']),
                                  'status':'SIMULATION_NOT_PHYSICAL','fuel_used_l':snap['fuel_used_l'],
                                  'refuelling_trucks':snap['states'].get('refueling',0)})
        for t in snap['trucks']:
            self.send_twin(t['id'].lower(),{'state':t['status'],'payload_t':t['payload'],
                 'x_schematic':t['x'],'y_schematic':t['y'],'destination':t['current_destination'] if 'current_destination' in t else 'C',
                 'sim_minute':minute,'run_id':rid,'model_type':t['type'],
                 'fuel_l':t['fuel_l'],'fuel_pct':t.get('fuel_pct',0),'tank_l':t['tank_l']})
        for i in range(5):
            q=sum(t['current_destination']==f'L{i}' and t['status']=='queue_load' for t in snap['trucks'] if 'current_destination' in t)
            self.send_twin(f'load-{i+1}',{'queue_trucks':q,'sim_minute':minute,'run_id':rid})
        for i in range(5):
            q=sum(t['current_destination']==f'D{i}' and t['status']=='queue_dump' for t in snap['trucks'] if 'current_destination' in t)
            self.send_twin(f'dump-{i+1}',{'queue_trucks':q,'sim_minute':minute,'run_id':rid})
        assets=self.run.asset_states(minute)
        for site,st in assets['fuel_stations'].items():
            self.send_twin(f'fuel-{site.lower()}',{**st,'sim_minute':minute,'run_id':rid})
        for route,st in assets['roads'].items():
            signature=(rid,st['state'])
            if self._road_state_cache.get(route)==signature:continue
            self._road_state_cache[route]=signature
            self.send_twin(f'road-{st["from"].lower()}-{st["to"].lower()}',
                {'state':st['state'],'closure_active':st['state']=='closed',
                 'sim_minute':minute,'run_id':rid})
        for shovel,st in assets['shovels'].items():
            self.send_twin(shovel,{'state':st['state'],'site':st['site'],
               'sim_minute':minute,'run_id':rid})
        self.last_publish=time.time();self.last_published_run=rid

    def publisher(self):
        self.mqtt_init()
        while True:
            try:
                if self.mqtt_ok:self.publish()
            except Exception as e:
                self.mqtt_error=str(e)
            time.sleep(3)

    def ditto_readback(self,thing='mine-01'):
        if not DITTO_PASSWORD:return {'verified':False,'reason':'No Ditto credentials in this process'}
        auth=base64.b64encode(f'{DITTO_USER}:{DITTO_PASSWORD}'.encode()).decode()
        req=urllib.request.Request(f'{DITTO_URL}/api/2/things/{NAMESPACE}:{thing}',headers={'Authorization':f'Basic {auth}'})
        try:
            with urllib.request.urlopen(req,timeout=4) as resp:record=json.load(resp)
            fields=record.get('features',{})
            props={k:v.get('properties',{}).get('value') for k,v in fields.items()}
            return {'verified':True,'thingId':record.get('thingId'),'readback_run_id':props.get('run_id'),
                    'matches_active_run':props.get('run_id')==self.run_id,'sim_minute':props.get('sim_minute'),
                    'properties':props}
        except Exception as e:return {'verified':False,'reason':str(e)}

# CSV exports are deliberately classified: original configuration versus simulated results.
EXPORT_SCHEMAS={
 'source-trucks': ('truck_id','source_truck_type','payload_capacity_t','configured_speed_kmh','record_origin'),
 'source-shovels': ('shovel_id','loading_site','bucket_capacity_t','loading_cycle_min','record_origin'),
 'source-roads': ('from_node','to_node','distance_km','directional','record_origin'),
 'hourly': ('run_id','sim_hour_start_min','sim_day','hour_of_day','delivered_t','modeled_fuel_l','queue_truck_min','record_origin'),
 'trips': ('run_id','truck_id','load_site','dump_site','delivery_min','delivery_day','payload_t','record_origin'),
 'fuel': ('run_id','truck_id','fuel_station','refuel_start_min','refuel_end_min','litres_added','record_origin'),
 'truck-events': ('run_id','truck_id','state','start_min','end_min','from_node','to_node','payload_t','modeled_fuel_used_l','modeled_fuel_added_l','record_origin'),
 'shovels': ('run_id','shovel_id','loading_site','loaded_t','busy_min','record_origin'),
}

def export_rows(kind,mine):
    if kind not in EXPORT_SCHEMAS:raise ValueError('Unknown CSV export type')
    with mine.lock:
        mine.tick()
        run=mine.run;rid=mine.run_id
        if kind=='source-trucks':
            return [{'truck_id':t['id'],'source_truck_type':t['type'],'payload_capacity_t':t['capacity'],
               'configured_speed_kmh':t['speed'],'record_origin':'OpenMines configuration'} for t in run.all_trucks]
        if kind=='source-shovels':
            return [{'shovel_id':s['name'],'loading_site':f'L{i}','bucket_capacity_t':s['tons'],
               'loading_cycle_min':s['cycle_time'],'record_origin':'OpenMines configuration'}
               for i,site in enumerate(run.cfg['load_sites']) for s in site['shovels']]
        if kind=='source-roads':
            return [{'from_node':a,'to_node':b,'distance_km':run._road_length(a,b),'directional':'yes',
                     'record_origin':'OpenMines configuration'} for a,b in sorted(run._road_pairs())]
        start=max(0.,mine.minute-1440.)
        if kind=='hourly':
            rows=window_report(run,start,mine.minute)['hourly']
            return [{'run_id':rid,'sim_hour_start_min':r['minute'],'sim_day':int(r['minute']//1440)+1,
              'hour_of_day':f'{int(r["minute"]%1440//60):02}:00','delivered_t':r['delivered_t'],
              'modeled_fuel_l':r['fuel_l'],'queue_truck_min':r['queue_min'],
              'record_origin':'OreFlow simulated events'} for r in rows]
        if kind=='trips':
            return [{'run_id':rid,'truck_id':r['truck'],'load_site':r['load_site'],'dump_site':r['dump_site'],
             'delivery_min':r['end_min'],'delivery_day':int(r['end_min']//1440)+1,
             'payload_t':r['tonnes'],'record_origin':'OreFlow simulated events'}
             for r in run.trips if start<r['end_min']<=mine.minute]
        if kind=='fuel':
            return [{'run_id':rid,'truck_id':r['truck'],'fuel_station':r['station'],
                'refuel_start_min':r['start'],'refuel_end_min':r['end'],
                'litres_added':r['litres'],'record_origin':'OreFlow simulated events'}
                for r in run.fuel_events if start<r['end']<=mine.minute]
        if kind=='truck-events':
            return [{'run_id':rid,'truck_id':t['id'],'state':s['state'],'start_min':round(max(start,s['start']),5),
                'end_min':round(min(mine.minute,s['end']),5),'from_node':s['from'],'to_node':s['to'],
                'payload_t':s['payload'],'modeled_fuel_used_l':round(s['fuel_used_l']*max(0,min(mine.minute,s['end'])-max(start,s['start']))/max(1e-9,s['end']-s['start']),5),
                'modeled_fuel_added_l':s['fuel_added_l'],'record_origin':'OreFlow simulated events'}
                for t in run.trucks.values() for s in t['segments'] if s['end']>start and s['start']<mine.minute]
        if kind=='shovels':
            report=window_report(run,start,mine.minute)
            return [{'run_id':rid,'shovel_id':r['shovel'],'loading_site':r['site'],
              'loaded_t':r['tonnes'],'busy_min':round(r['busy_min'],1),
              'record_origin':'OreFlow simulated events'} for r in report['shovels']]
        raise ValueError('Unknown export')

def format_csv(kind,rows):
    output=io.StringIO(newline='')
    writer=csv.DictWriter(output,fieldnames=EXPORT_SCHEMAS[kind],extrasaction='ignore',lineterminator='\n')
    writer.writeheader();writer.writerows(rows)
    return ('\ufeff'+output.getvalue()).encode('utf-8')

S=State()
C=ContinuousMine()

def publish_live():
    # Reuse the battle-tested MQTT -> Ditto event writer with continuous state.
    S.mqtt_init()
    while True:
        try:
            with C.lock:
                C.tick()
                with S.lock:
                    S.run=C.run;S.run_id=C.run_id;S.minute=C.minute
                    S.playing=False;S.last=time.monotonic()
                    if S.mqtt_ok:S.publish()
        except Exception as exc:
            S.mqtt_error=str(exc)
        time.sleep(3)


class Handler(BaseHTTPRequestHandler):
    def log_message(self,fmt,*args):pass
    def respond(self,code,obj):
        body=dump(obj)
        self.send_response(code)
        self.send_header('Content-Type','application/json; charset=utf-8')
        self.send_header('Content-Length',str(len(body)))
        self.send_header('Cache-Control','no-store')
        self.end_headers();self.wfile.write(body)
    def read_json(self):
        ln=int(self.headers.get('Content-Length','0'))
        if ln>8192:raise ValueError('request too large')
        return json.loads(self.rfile.read(ln) or b'{}')
    def do_GET(self):
        from urllib.parse import urlsplit,parse_qs
        url=urlsplit(self.path);path=url.path
        qs=parse_qs(url.query)
        try:
            if path in ('/','/index.html'):
                self.file('static/index.html','text/html; charset=utf-8');return
            if path.startswith('/static/') and re.fullmatch(r'/static/[a-z0-9_.-]+',path):
                fn=HERE/path.lstrip('/')
                if fn.exists():
                    mime='text/css' if path.endswith('.css') else 'application/javascript'
                    self.file(path.lstrip('/'),mime);return
            if path=='/api/prototype-info':self.respond(200,{'recorded':False,'version':'2.3-competition'});return
            if path=='/api/source-config':self.respond(200,C.run.cfg);return
            if path=='/api/v23/export':
                kind=qs.get('kind',['hourly'])[0]
                if kind not in EXPORT_SCHEMAS:raise ValueError('Invalid export type')
                body=format_csv(kind,export_rows(kind,C))
                self.send_response(200)
                self.send_header('Content-Type','text/csv; charset=utf-8')
                self.send_header('Content-Disposition',f'attachment; filename="oreflow_{kind}.csv"')
                self.send_header('Content-Length',str(len(body)))
                self.send_header('Cache-Control','no-store')
                self.end_headers();self.wfile.write(body);return
            if path=='/api/v22/assets':self.respond(200,C.run.asset_states(C.minute));return
            if path=='/api/v22/now':self.respond(200,C.snapshot());return
            if path=='/api/v22/config':
                self.respond(200,{'mine':C.run.public_config(),'rates':[1,5,15,60],
                                  'shovels':[{'id':x['alias'],'name':x['id'],'site':f'L{i}'} for i,ss in enumerate(C.run.loads) for x in ss]});return
            if path=='/api/v22/reports':self.respond(200,C.daily());return
            if path=='/api/v22/day':
                num=int(qs.get('day',['0'])[0])
                if num<1 or num>len(C.days):raise ValueError('day not yet completed')
                self.respond(200,C.days[num-1]);return
            if path=='/api/v22/job':
                with C.lock:self.respond(200,C.job);return
            if path=='/api/v22/status':
                with C.lock:
                    S.run_id=C.run_id
                    active=C.run_id
                read=S.ditto_readback()
                sim_age=(C.minute-float(read.get('sim_minute') or 0)) if read.get('verified') else None
                fresh=sim_age is not None and 0<=sim_age<=max(15,C.rate*10)
                self.respond(200,{'oreflow':True,'mqtt':S.mqtt_ok,'ditto':read.get('verified',False),
                    'run_matches':read.get('readback_run_id')==active,'twin_fresh':fresh,
                    'simulated_lag_minutes':round(sim_age,1) if sim_age is not None else None,
                    'influx':'not independently checked here',
                    'message':read.get('reason','') if not read.get('verified') else ''});return
            if path=='/api/health':
                with C.lock:S.run_id=C.run_id
                read=S.ditto_readback()
                self.respond(200,{'app':'ok','simulation_duration':C.minute,'mqtt_connected':S.mqtt_ok,'mqtt_error':S.mqtt_error,
                                   'ditto':read,'last_published_epoch':S.last_publish,'simulated_not_physical':True});return
            if path=='/api/config':self.respond(200,C.run.public_config());return
            if path=='/api/frame':
                t=float(qs['t'][0]) if 't' in qs else None
                self.respond(200,C.snapshot());return
            if path=='/api/overview':
                with S.lock:
                    if S.comparison is None:S.comparison=compare(duration=1440)
                    if S.impact is None:S.impact=scenario_impact(duration=1440)
                    self.respond(200,{'metrics':S.run.metrics(),'comparison':S.comparison,
                                      'run_id':S.run_id,'curve':S.run.production_curve(),
                                      'scenario_impact':S.impact,
                                      'actions':S.run.actions[-50:],'simulated_not_physical':True});return
            if path=='/api/benchmark':
                with S.lock:
                    if S.benchmark is None:
                        r=S.run
                        S.benchmark=paired_benchmark(strategy=r.strategy,scenario=r.scenario,
                            seeds=range(21,32),duration=r.duration,fleet=r.fleet,
                            fleet_mix=r.fleet_mix,affected=r.affected,
                            route_from=r.route_from,route_to=r.route_to,
                            closure_start=r.closure_start,outage_start=r.outage_start,
                            outage_duration=r.outage_duration,
                            dispatch_objective=r.dispatch_objective,
                            fuel_price_kzt=r.fuel_price_kzt)
                    self.respond(200,S.benchmark);return
            if path.startswith('/api/ditto/'):
                thing=path[len('/api/ditto/'):]
                if not re.fullmatch(r'(mine-01|t\d{3}|load-[1-5]|dump-[1-5]|shovel-[1-5]-[1-5]|fuel-l[03]|road-(?:c|l[0-4]|d[0-4])-(?:l[0-4]|d[0-4]))',thing):
                    self.respond(400,{'error':'invalid twin'});return
                with C.lock:S.run_id=C.run_id
                self.respond(200,S.ditto_readback(thing));return
            if path=='/api/job':
                with S.lock:self.respond(200,S.job);return
            if path=='/api/report':
                with S.lock:
                    if S._report is None:S._report=S.run.operations_report()
                    self.respond(200,{'run_id':S.run_id,**S._report});return
            if path=='/api/trips':
                with S.lock:self.respond(200,{'source':'simulated','trips':S.run.trips});return
            if path=='/api/fuel-events':
                with S.lock:self.respond(200,{'source':'simulated','events':S.run.fuel_events});return
            self.respond(404,{'error':'not found'})
        except (ValueError,KeyError) as e:self.respond(400,{'error':str(e)})
    def do_POST(self):
        try:
            obj=self.read_json()
            if self.path=='/api/v23/fresh-start':
                if obj.get('confirm')!='START_FRESH':raise ValueError('Explicit confirmation required')
                self.respond(200,C.fresh_start());return
            if self.path=='/api/v22/control':self.respond(200,C.control(obj));return
            if self.path=='/api/v22/evaluate':self.respond(202,C.evaluate(obj.get('kind','advice'),obj));return
            if self.path=='/api/v22/policy':self.respond(200,C.apply_policy(obj));return
            if self.path=='/api/v23/queue-relief':self.respond(200,C.apply_site_relief(obj));return
            if self.path=='/api/v22/incident':self.respond(200,C.apply_scenario(obj));return
            if self.path=='/api/activate/start':self.respond(202,S.start_job(obj));return
            if self.path=='/api/activate':
                output,code=S.activate(obj);self.respond(code,output);return
            if self.path=='/api/control':self.respond(200,S.control(obj));return
            self.respond(404,{'error':'not found'})
        except (ValueError,KeyError,TypeError) as e:self.respond(400,{'error':str(e)})
    def file(self,path,mime):
        blob=(HERE/path).read_bytes()
        self.send_response(200);self.send_header('Content-Type',mime)
        self.send_header('Content-Length',str(len(blob)))
        self.end_headers();self.wfile.write(blob)


def main():
    threading.Thread(target=C.loop,daemon=True).start()
    if MQTT_HOST:threading.Thread(target=publish_live,daemon=True).start()
    server=ThreadingHTTPServer(('0.0.0.0',PORT),Handler)
    print(f'OreFlow on http://127.0.0.1:{PORT} (simulation; MQTT={MQTT_HOST or "disabled"})',flush=True)
    try:server.serve_forever()
    finally:server.server_close()

if __name__=='__main__':main()
