#!/usr/bin/env python3
"""No Docker: start a temporary HTTP server and test real handlers / payload validation."""
import json
import sys
import threading
import urllib.error
import urllib.request
from pathlib import Path
ROOT=Path(__file__).resolve().parents[1]
sys.path.insert(0,str(ROOT/'team/oreflow'))
from server import Handler
from http.server import ThreadingHTTPServer

server=ThreadingHTTPServer(('127.0.0.1',0),Handler)
thread=threading.Thread(target=server.serve_forever,daemon=True);thread.start()
base=f'http://127.0.0.1:{server.server_port}'
def request(path,obj=None):
 data=json.dumps(obj).encode() if obj is not None else None
 req=urllib.request.Request(base+path,data=data,headers={'Content-Type':'application/json'} if data else {})
 with urllib.request.urlopen(req,timeout=30) as res:return res.status,json.loads(res.read())
try:
 for path in ('/api/config','/api/frame','/api/overview','/api/health','/api/trips','/api/fuel-events'):
  code,data=request(path);assert code==200,(path,code)
  print('GET',path,'PASS')
 cfg=request('/api/config')[1]
 assert len(cfg['fleet'])==71 and cfg['duration']==1440 and len(cfg['shovels'])==5
 frame=request('/api/frame')[1]
 assert len(frame['trucks'])==71 and all('fuel_l' in t and 'tank_l' in t for t in frame['trucks'])
 assert request('/api/overview')[1]['metrics']['fuel_used_l']>0
 assert request('/api/fuel-events')[1]['events']
 # custom road, time, refinery scenario and true class-level fleet subsets
 payload={'scenario':'road_closure','strategy':'smart','route_from':'L3','route_to':'D1',
          'outage_start':360,'closure_start':360,'outage_duration':240,'seed':45,'duration':1440}
 _,active=request('/api/activate',payload)
 assert active['metrics']['duration_min']==1440 and 'scenario_impact' in active
 assert active['scenario_impact']['normal']['tonnes']!=active['scenario_impact']['disrupted']['tonnes']
 print('POST custom road closure PASS')
 _,active=request('/api/activate',{'scenario':'fleet_reduction','fleet_mix':{'OfficalTruck':4,'CLTruck':10,'XHTruck':12},'duration':240})
 assert active['metrics']['fleet']==26
 assert len(request('/api/frame')[1]['trucks'])==26
 print('POST fleet mix PASS')
 _,f=request('/api/control',{'seek':150,'play':False})
 assert 149<=f['minute']<=151
 print('POST playback and seek PASS')
 try:request('/api/activate',{'strategy':'nonexistent'})
 except urllib.error.HTTPError as e:assert e.code==400;print('Invalid policy HTTP 400 PASS')
 else:raise AssertionError('Invalid policy incorrectly accepted')
 print('API SMOKE PASS')
finally:
 server.shutdown();server.server_close()
