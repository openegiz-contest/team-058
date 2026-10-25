import sys,unittest,pathlib,json
sys.path.insert(0,str(pathlib.Path(__file__).resolve().parents[1]))
from engine import MineRun, compare, scenario_impact, paired_benchmark,source,validate_config,ENERGY
from setup_twins import definitions

class MineTests(unittest.TestCase):
 @classmethod
 def setUpClass(cls):
  cls.sim=MineRun(seed=42).simulate()
 def test_real_source_shovel_count(self):
  self.assertTrue(validate_config(source()))
  self.assertEqual(sum(len(x['shovels']) for x in source()['load_sites']),20)
 def test_all_trucks_present(self):self.assertEqual(len(self.sim.trucks),71)
 def test_three_types_and_tonnage(self):
  types={}
  for t in self.sim.all_trucks:types.setdefault((t['type'],t['capacity']),0);types[(t['type'],t['capacity'])]+=1
  self.assertEqual(sorted(types.values()),[9,29,33])
  self.assertEqual({t['capacity'] for t in self.sim.all_trucks},{35,55,77})
 def test_distances_are_directed(self):
  self.assertNotEqual(self.sim._road_length('L0','D4'),self.sim._road_length('D4','L0'))
 def test_every_truck_unique(self):self.assertEqual(len(self.sim.trucks),len(set(self.sim.trucks)))
 def test_no_state_overlap(self):
  for t in self.sim.trucks.values():
   seg=t['segments']
   self.assertTrue(all(seg[i]['end']<=seg[i+1]['start']+1e-5 for i in range(len(seg)-1)),t['id'])
 def test_payload_never_exceeds_capacity(self):
  for t in self.sim.trucks.values():
   self.assertTrue(all(0<=s['payload']<=t['capacity'] for s in t['segments']))
 def test_trip_tonnage_conservation(self):
  self.assertEqual(round(sum(d['tonnes'] for d in self.sim.deliveries)),self.sim.metrics()['tonnes'])
  self.assertEqual(len(self.sim.deliveries),self.sim.metrics()['trips'])
 def test_completed_trips_have_valid_sites(self):
  for d in self.sim.deliveries:
   self.assertIn(d['load_site'],self.sim.nodes)
   self.assertIn(d['site'],self.sim.nodes)
   self.assertLessEqual(d['t'],self.sim.duration+1e-6)
 def test_frames_consistent(self):
  for minute in (0,2,40,77,120,180,240):
   f=self.sim.frame(minute)
   self.assertEqual(sum(f['states'].values()),71)
   self.assertEqual(len(f['trucks']),71)
   self.assertEqual(f['tonnes'],sum(x['tonnes'] for x in self.sim.deliveries if x['t']<=minute))
 def test_deterministic(self):
  a=MineRun(seed=19).simulate();b=MineRun(seed=19).simulate()
  self.assertEqual(a.production_curve(),b.production_curve())
  self.assertEqual(a.metrics(),b.metrics())
 def test_strategies_differ(self):
  c=compare(seed=42)
  self.assertGreater(c['candidate']['tonnes'],c['baseline']['tonnes'])
 def test_road_closure_is_reversible(self):
  a=MineRun(strategy='smart',scenario='road_closure').simulate()
  self.assertFalse(any(x['from']=='L2' and x['to']=='D4' and 480<=x['start']<600 for t in a.trucks.values() for x in t['segments'] if x['state']=='hauling'))
  b=MineRun(strategy='smart',scenario='normal').simulate()
  c=MineRun(strategy='smart',scenario='normal').simulate()
  self.assertEqual(b.metrics(),c.metrics())
 def test_shovel_failure_affects_simulation(self):
  fail=MineRun(scenario='shovel_outage').simulate()
  base=MineRun(scenario='normal').simulate()
  self.assertNotEqual(fail.metrics()['tonnes'],base.metrics()['tonnes'])
 def test_reduced_fleet_affects_output(self):
  few=MineRun(scenario='fleet_reduction',fleet=20).simulate()
  self.assertEqual(len(few.trucks),20)
  self.assertLess(few.metrics()['tonnes'],self.sim.metrics()['tonnes'])
 def test_definitions_complete(self):
  twins=definitions()
  self.assertEqual(len(twins),159)
  self.assertIn('org.openegiz.oreflow:t071',twins)
  self.assertEqual(sum(v['attributes']['kind']=='shovel' for v in twins.values()),20)
 def test_benchmark(self):
  r=paired_benchmark(seeds=(21,22,23))
  self.assertEqual(r['n'],3)
  self.assertTrue(all(v['candidate_t']>v['baseline_t'] for v in r['runs']))
 def test_invalid_inputs(self):
  for kwargs in ({'strategy':'magic'},{'scenario':'unknown'},{'scenario':'fleet_reduction','fleet':0}):
   with self.assertRaises(ValueError):MineRun(**kwargs)


class FuelAndScenarioTests(unittest.TestCase):
 @classmethod
 def setUpClass(cls):cls.day=MineRun(duration=1440,seed=42).simulate()
 def test_24h_and_real_source_params(self):
  self.assertEqual(self.day.duration,1440)
  self.assertEqual(len(self.day.trucks),71)
  self.assertEqual(sum(len(x) for x in self.day.loads),20)
  self.assertEqual(sorted(x['capacity'] for x in self.day.all_trucks),sorted([77]*9+[35]*29+[55]*33))
 def test_all_tanks_in_range(self):
  for t in self.day.trucks.values():
   self.assertLessEqual(t['initial_fuel_l'],t['tank_l'])
   self.assertGreater(t['initial_fuel_l'],0)
   for seg in t['segments']:
    self.assertGreaterEqual(seg['fuel_before_l'],-.001)
    self.assertGreaterEqual(seg['fuel_after_l'],-.001)
    self.assertLessEqual(seg['fuel_after_l'],t['tank_l']+.001)
  self.assertEqual(self.day.metrics()['fuel_shortfall_l'],0)
 def test_fuel_bookkeeping_conserves_litres(self):
  for t in self.day.trucks.values():
   final=t['initial_fuel_l']+t['fuel_added_l']-t['fuel_used_l']
   self.assertAlmostEqual(t['fuel_l'],final,delta=.01)
  self.assertGreater(self.day.metrics()['fuel_used_l'],0)
 def test_refueling_real_events_in_run(self):
  self.assertGreater(len(self.day.fuel_events),10)
  self.assertTrue(any(s['state']=='refueling' for t in self.day.trucks.values() for s in t['segments']))
  for ev in self.day.fuel_events:
   self.assertIn(ev['station'],('L0','L3'))
   self.assertGreaterEqual(ev['litres'],0)
   self.assertLessEqual(ev['start'],ev['end'])
 def test_frame_fuel_changes_over_time(self):
  a=self.day.frame(0);b=self.day.frame(900)
  self.assertEqual(sum(b['states'].values()),71)
  self.assertNotEqual(a['fuel_used_l'],b['fuel_used_l'])
  self.assertTrue(all(0<=t['fuel_l']<=t['tank_l'] for t in b['trucks']))
 def test_route_closure_any_loaded_direction(self):
  r=MineRun(scenario='road_closure',route_from='L3',route_to='D1',duration=1440,closure_start=300,outage_duration=450).simulate()
  self.assertFalse(any(s['state']=='hauling' and s['from']=='L3' and s['to']=='D1' and 300<=s['start']<750 for t in r.trucks.values() for s in t['segments']))
 def test_route_closure_any_return_direction(self):
  r=MineRun(scenario='road_closure',route_from='D4',route_to='L2',duration=1440,closure_start=300,outage_duration=450).simulate()
  self.assertFalse(any(s['state']=='returning' and s['from']=='D4' and s['to']=='L2' and 300<=s['start']<750 for t in r.trucks.values() for s in t['segments']))
 def test_shovel_selector(self):
  r=MineRun(scenario='shovel_outage',affected='shovel-4-1',outage_start=300,outage_duration=600).simulate()
  shovel='NorthPitMine-LoadSite4-Shovel-1'
  self.assertFalse(any(s['state']=='loading' and s.get('shovel')==shovel and s['start']<900 and s['end']>300 for t in r.trucks.values() for s in t['segments']))
 def test_fleet_mix(self):
  mix={'OfficalTruck':3,'CLTruck':10,'XHTruck':12}
  r=MineRun(scenario='fleet_reduction',fleet_mix=mix).simulate()
  self.assertEqual(r.metrics()['fleet'],25)
  self.assertEqual(r.metrics()['fleet_mix'],mix)
 def test_truck_breakdown_event(self):
  r=MineRun(scenario='truck_failure',affected='T014',outage_start=300,outage_duration=300).simulate()
  self.assertTrue(any(s['state']=='maintenance' and s['end']>300 for s in r.trucks['T014']['segments']))
 def test_fuel_station_unavailable(self):
  r=MineRun(scenario='fuel_station_outage',affected='L3',outage_start=600,outage_duration=800).simulate()
  # Only new fill jobs are excluded during outage; previously started filling may finish.
  self.assertFalse(any(600<=e['start']<1400 and e['station']=='L3' for e in r.fuel_events))
 def test_output_paired_and_impact(self):
  r=scenario_impact(scenario='road_closure',route_from='L2',route_to='D4',duration=720)
  self.assertIn('normal',r);self.assertIn('extra_fuel_l',r)
  c=compare(duration=720)
  self.assertIn('fuel_change_pct',c)
 def test_seed_repeatability_24h(self):
  a=MineRun(seed=7).simulate().metrics();b=MineRun(seed=7).simulate().metrics()
  self.assertEqual(a,b)
 def test_invalid_parameters_rejected(self):
  bad=({'duration':5000},{'dispatch_objective':'magic'},
       {'scenario':'shovel_outage','affected':'shovel-88'},
       {'scenario':'fuel_station_outage','affected':'L2'},
       {'scenario':'road_closure','route_from':'L0','route_to':'L1'},
       {'scenario':'fleet_reduction','fleet_mix':{'OfficalTruck':10,'CLTruck':29,'XHTruck':33}})
  for kw in bad:
   with self.subTest(kw=kw),self.assertRaises(ValueError):MineRun(**kw)
 def test_source_unchanged(self):
  cfg=source();self.assertNotIn('tank_l',cfg['charging_site']['trucks'][0]);self.assertIn('l2d_road_matrix',cfg['road'])

if __name__=='__main__':unittest.main()
