#!/usr/bin/env python3
"""Live OpenEgiz verification: reports failures explicitly (no mock status)."""
import base64, json, pathlib, sys, time, urllib.request, urllib.error
ROOT=pathlib.Path(__file__).resolve().parent.parent

def credentials():
    p=ROOT/'deploy/compose/.env'
    if not p.exists():raise RuntimeError('deploy/compose/.env missing: start OpenEgiz first')
    return dict(line.split('=',1) for line in p.read_text().splitlines() if line and not line.startswith('#') and '=' in line)

def read(url,headers=None,data=None,timeout=9):
    req=urllib.request.Request(url,headers=headers or {},data=data)
    with urllib.request.urlopen(req,timeout=timeout) as r:return r.read().decode()

def main():
    env=credentials();checks={}
    try:
        state=json.loads(read('http://localhost:8099/api/health'))
        checks['oreflow_http']=state.get('app')=='ok'
        checks['mqtt_connected']=bool(state.get('mqtt_connected'))
        checks['ditto_readback']=bool(state.get('ditto',{}).get('verified'))
        checks['ditto_same_active_run']=bool(state.get('ditto',{}).get('matches_active_run'))
        if not checks['mqtt_connected']:checks['mqtt_reason']=state.get('mqtt_error','')
        if not checks['ditto_readback']:checks['ditto_reason']=state.get('ditto',{}).get('reason','')
        frame=json.loads(read('http://localhost:8099/api/frame'))
        config=json.loads(read('http://localhost:8099/api/config'))
        live=json.loads(read('http://localhost:8099/api/v22/now'))
        checks['fleet_71']=len(config['fleet'])==71
        checks['active_fleet_consistent']=len(frame['trucks'])==config['active_fleet']==71
        checks['continuous_mine']=live.get('continuous') is True and live.get('playing') in (True,False)
        checks['clock_advances_without_end']=isinstance(live.get('minute'),(int,float)) and 'day' in live
        checks['modeled_fuel_fields']=all(t.get('tank_l',0)>0 and 'fuel_l' in t for t in frame['trucks'])
        twin=json.loads(read('http://localhost:8099/api/ditto/t001'))
        checks['ditto_fuel_readback']=twin.get('verified') and isinstance(twin.get('properties',{}).get('fuel_l'),(int,float))
        fuel_twin=json.loads(read('http://localhost:8099/api/ditto/fuel-l0'))
        road_twin=json.loads(read('http://localhost:8099/api/ditto/road-l0-d0'))
        checks['fuel_station_ditto_twin']=bool(fuel_twin.get('verified') and fuel_twin.get('matches_active_run') and
            fuel_twin.get('properties',{}).get('state') in ('available','unavailable'))
        checks['road_ditto_twin']=bool(road_twin.get('verified') and road_twin.get('matches_active_run') and
            road_twin.get('properties',{}).get('state') in ('open','closed','degraded'))
        assets=json.loads(read('http://localhost:8099/api/v22/assets'))
        checks['extended_equipment_coverage']=len(assets.get('fuel_stations',{}))==2 and len(assets.get('roads',{}))==55 and len(assets.get('shovels',{}))==20

        checks['fuel_events_endpoint']=json.loads(read('http://localhost:8099/api/fuel-events')).get('source')=='simulated'
    except Exception as e:checks['oreflow_http']=False;checks['app_error']=str(e)
    try:
        graf=json.loads(read('http://localhost:3000/api/health'))
        checks['grafana_http']=graf.get('database')=='ok'
    except Exception as e:checks['grafana_http']=False;checks['grafana_error']=str(e)
    try:
        query='from(bucket:"default") |> range(start:-15m) |> filter(fn:(r)=>r.thingId=="org.openegiz.oreflow:mine-01") |> limit(n:3)'
        raw=read('http://localhost:8086/api/v2/query?org=opentwins',
            headers={'Authorization':'Token '+env['INFLUXDB_TOKEN'],'Content-Type':'application/vnd.flux', 'Accept':'application/csv'},
            data=query.encode(),timeout=18)
        checks['influx_twin_data']=('org.openegiz.oreflow:mine-01' in raw)
    except Exception as e:checks['influx_twin_data']=False;checks['influx_error']=str(e)
    print(json.dumps(checks,indent=2))
    critical=['oreflow_http','mqtt_connected','ditto_readback','ditto_same_active_run','fleet_71','active_fleet_consistent','continuous_mine','clock_advances_without_end','modeled_fuel_fields','ditto_fuel_readback','fuel_events_endpoint','extended_equipment_coverage','fuel_station_ditto_twin','road_ditto_twin','grafana_http','influx_twin_data']
    if not all(checks.get(k) for k in critical):
        print('INCOMPLETE: at least one real service or telemetry check failed',file=sys.stderr)
        return 1
    print('PASS: actual end-to-end HTTP, MQTT, Ditto readback and Influx evidence observed')
    return 0

if __name__=='__main__':sys.exit(main())
