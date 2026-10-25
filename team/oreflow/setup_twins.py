"""Idempotent initialization of OpenEgiz equipment and road twins."""
import base64,json,os,time,urllib.error,urllib.request
from engine import MineRun,NAMESPACE,DEFAULT_PUMPS


def definitions():
    run=MineRun()
    root=f'{NAMESPACE}:mine-01'
    twins={}
    def add(id_,kind,name,extra=None,features=None):
        attrib={'name':name,'kind':kind,'_isType':False}
        if id_!='mine-01':attrib['_parents']=root
        attrib.update(extra or {})
        twins[f'{NAMESPACE}:{id_}']={'policyId':'default:basic_policy','attributes':attrib,
            'features':{k:{'properties':{'value':v}} for k,v in (features or {}).items()}}
    add('mine-01','mine','North Pit — OreFlow simulation',{'source':'OpenMines MIT, anonymized source parameters'},
        {'sim_minute':0,'delivered_t':0,'trips':0,'run_id':'not_started','status':'SIMULATION_NOT_PHYSICAL'})
    for tr in run.all_trucks:
        add(tr['id'].lower(),'haul_truck',tr['id'],{'type':tr['type'],'capacity_t':tr['capacity'],'speed_kmh':tr['speed']},
            {'state':'idle','payload_t':0,'run_id':'not_started','sim_minute':0})
    for i,site in enumerate(run.cfg['load_sites']):
        add(f'load-{i+1}','loading_site',site['name'],{'pos_schematic':site['position']},{'queue_trucks':0,'sim_minute':0})
        for j,s in enumerate(site['shovels']):
            add(f'shovel-{i+1}-{j+1}','shovel',s['name'],{'bucket_t':s['tons'],'cycle_min':s['cycle_time']},{'site_loading_active':False,'sim_minute':0})
    for i,site in enumerate(run.cfg['dump_sites']):
        add(f'dump-{i+1}','dump_site',site['name'],{'pos_schematic':site['position']},{'queue_trucks':0,'sim_minute':0})
    # Equipment previously represented only in the local simulator. Every fuel
    # point and directed connection has its own platform-backed thing.
    for station in DEFAULT_PUMPS:
        add(f'fuel-{station.lower()}','fuel_station',f'Fuel station {station}',
            {'site':station,'pump_count':len(run.pumps[station]),'modeled':True},
            {'state':'available','waiting_trucks':0,'refueling_trucks':0,'incoming_trucks':0,
             'fuel_dispensed_l':0,'sim_minute':0,'run_id':'not_started'})
    for frm,to in sorted(run._road_pairs()):
        add(f'road-{frm.lower()}-{to.lower()}','directed_haul_road',f'{frm} → {to}',
            {'from':frm,'to':to,'length_km':run._road_length(frm,to),'modeled':True},
            {'state':'open','closure_active':False,'sim_minute':0,'run_id':'not_started'})
    return twins


def main():
    if os.getenv('OREFLOW_DRY_RUN')=='1':
        print(json.dumps({'twins':len(definitions()),'ids':list(definitions())[:5]}));return
    url=os.getenv('DITTO_URL','http://ditto-nginx:80').rstrip('/')
    pwd=os.environ['DITTO_PASSWORD']
    auth=base64.b64encode(f'ditto:{pwd}'.encode()).decode()
    twins=definitions()
    for i,(thing,payload) in enumerate(twins.items()):
        request=urllib.request.Request(f'{url}/api/2/things/{thing}',data=json.dumps(payload).encode(),method='PUT',
                                       headers={'Authorization':f'Basic {auth}','Content-Type':'application/json'})
        for retry in range(50):
            try:
                with urllib.request.urlopen(request,timeout=20) as resp:
                    if resp.status not in (200,201,204):raise RuntimeError(f'HTTP {resp.status}')
                break
            except (urllib.error.URLError,TimeoutError) as e:
                if retry==49:raise RuntimeError(f'Ditto twin setup failed: {thing}: {e}') from e
                time.sleep(2)
        if i%20==0:print(f'Ditto twins registered: {i+1}/{len(twins)}',flush=True)
    print(f'{len(twins)} OreFlow twins registered through Ditto HTTP API',flush=True)

if __name__=='__main__':main()
