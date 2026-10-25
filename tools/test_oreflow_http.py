#!/usr/bin/env python3
"""Local HTTP API smoke test. Can run without Docker or external dependencies."""
import json,os,subprocess,sys,time,urllib.request,urllib.error,pathlib,signal
ROOT=pathlib.Path(__file__).resolve().parents[1]
HOST='http://127.0.0.1:18099'

def req(path,body=None):
    r=urllib.request.Request(HOST+path,data=json.dumps(body).encode() if body is not None else None,
                             headers={'Content-Type':'application/json'} if body is not None else {})
    with urllib.request.urlopen(r,timeout=8) as a:
        data=a.read()
        return json.loads(data) if path.startswith('/api/') else data

def main():
    p=subprocess.Popen([sys.executable,'server.py'],cwd=ROOT/'team/oreflow',
          env={**os.environ,'OREFLOW_PORT':'18099','MQTT_HOST':'','DITTO_PASSWORD':''},stdout=subprocess.DEVNULL,stderr=subprocess.PIPE)
    try:
        for i in range(60):
            try:req('/api/frame');break
            except Exception:time.sleep(.1)
        else:raise RuntimeError('HTTP did not start')
        assert b'OREFLOW' in req('/')
        assert b'map-stage' in req('/static/app.css')
        assert b'drawTrucks' in req('/static/app.js')
        config=req('/api/config');assert len(config['fleet'])==71
        a=req('/api/frame?t=60');assert len(a['trucks'])==71 and a['minute']==60
        o=req('/api/overview');assert o['metrics']['duration_min']==1440 and o['metrics']['tonnes']>1000
        b=req('/api/benchmark');assert b['n']==11
        report=req('/api/report');assert len(report['hourly'])==24 and len(report['shovels'])==20
        s=req('/api/activate',{'strategy':'smart','scenario':'shovel_outage','seed':42,'fleet':71})
        assert s['metrics']['scenario']=='shovel_outage'
        control=req('/api/control',{'play':False,'seek':99});assert control['minute']==99
        t=req('/api/trips');assert t['source']=='simulated' and len(t['trips'])>150
        health=req('/api/health');assert health['app']=='ok' and not health['ditto']['verified']
        s=req('/api/activate',{'strategy':'nearest','scenario':'fleet_reduction','seed':42,'fleet':25})
        assert s['metrics']['fleet']==25
        try:req('/api/activate',{'strategy':'broken'})
        except urllib.error.HTTPError as e:assert e.code==400
        else:raise AssertionError('invalid policy was accepted')
        print('PASS: 13 local HTTP checks including active scenario, benchmark, playback, static assets, and platform honesty')
    finally:
        p.terminate()
        try:p.wait(timeout=4)
        except subprocess.TimeoutExpired:p.kill()
if __name__=='__main__':main()
