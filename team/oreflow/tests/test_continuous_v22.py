"""V2.2 continuous mine invariants and decision integrity."""
import sys
from pathlib import Path
sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
import tempfile,unittest,copy
from pathlib import Path
from engine import MineRun
from continuous import ContinuousMine,window_report

class IncrementalSimulation(unittest.TestCase):
 def test_horizon_does_not_stop_mine(self):
  r=MineRun(seed=42).advance_to(3000)
  self.assertGreater(len(r.deliveries),0)
  self.assertGreater(max(d['t'] for d in r.deliveries),2880)
  self.assertGreater(len(r.queue),0)
 def test_chunked_equals_direct_seven_days(self):
  direct=MineRun(seed=43).advance_to(10080)
  chunk=MineRun(seed=43)
  for t in range(30,10081,30):chunk.advance_to(t)
  self.assertEqual(direct.frame(10080)['tonnes'],chunk.frame(10080)['tonnes'])
  self.assertEqual(direct.frame(10080)['fuel_used_l'],chunk.frame(10080)['fuel_used_l'])
  self.assertEqual(len(direct.deliveries),len(chunk.deliveries))
 def test_fuel_never_negative_on_seven_days(self):
  r=MineRun(seed=47).advance_to(10080)
  self.assertEqual(sum(t.get('fuel_shortfall_l',0) for t in r.trucks.values()),0)
  for t in r.trucks.values():self.assertGreaterEqual(t['fuel_l'],0)
 def test_archive_preserves_totals(self):
  r=MineRun(seed=45).advance_to(10080)
  a=r.frame(10080);b=window_report(r,8640,10080)
  r.archive_before(7200)
  self.assertEqual(a['tonnes'],r.frame(10080)['tonnes'])
  self.assertEqual(a['fuel_used_l'],r.frame(10080)['fuel_used_l'])
  self.assertEqual(b,window_report(r,8640,10080))
  self.assertLess(len(r.trips),10000)
 def test_daily_report_conservation(self):
  r=MineRun().advance_to(1440)
  report=window_report(r,0,1440)
  self.assertAlmostEqual(report['tonnes'],r.metrics()['tonnes'])
  self.assertAlmostEqual(report['fuel_l'],r.metrics()['fuel_used_l'],delta=1)
  self.assertEqual(report['trips'],r.metrics()['trips'])
 def test_current_frame_has_71_trucks(self):
  r=MineRun().advance_to(180)
  f=r.frame(180)
  self.assertEqual(len(f['trucks']),71)
  self.assertEqual(sum(f['states'].values()),71)

class ContinuousController(unittest.TestCase):
 def setUp(self):
  self.temp=tempfile.TemporaryDirectory();self.addCleanup(self.temp.cleanup)
  self.c=ContinuousMine(self.temp.name);self.c.playing=False
  self.c.run.advance_to(240);self.c.minute=240
 def test_checkpoint_restore(self):
  self.c.save();c2=ContinuousMine(self.temp.name)
  self.assertEqual(c2.run_id,self.c.run_id)
  self.assertEqual(c2.minute,self.c.minute)
  self.assertEqual(c2.run.frame(240)['tonnes'],self.c.run.frame(240)['tonnes'])
  self.assertEqual(len(c2.run.queue),len(self.c.run.queue))
 def test_no_rebuild_of_equipment_on_continue(self):
  before=self.c.run.trucks['T001']['fuel_l']
  self.c.run.advance_to(360)
  self.assertLess(self.c.run.trucks['T001']['fuel_l'],before)
  self.assertEqual(len(self.c.run.trucks),71)
 def test_pause_and_rate(self):
  self.c.control({'rate':15,'playing':False})
  self.assertEqual(self.c.rate,15)
  self.assertFalse(self.c.playing)
  with self.assertRaises(ValueError):self.c.control({'rate':100000})
 def test_advice_branches_do_not_modify_live_mine(self):
  initial=copy.deepcopy(self.c.run)
  result=self.c._evaluate('advice',{'horizon_hours':2})
  self.assertEqual({x['policy'] for x in result['options']},{'nearest','balanced','smart'})
  self.assertEqual(self.c.run.frame(240)['tonnes'],initial.frame(240)['tonnes'])
  self.assertEqual(self.c.run.strategy,initial.strategy)
  self.assertEqual(result['recommended_policy'],next(x for x in result['options'] if x['policy']==result['recommended_policy'])['policy'])
 def test_scenario_branches_do_not_modify_live_mine(self):
  orig=self.c.run.scenario
  result=self.c._evaluate('scenario',{'scenario':'shovel_outage','affected':'shovel-3-1','duration_min':120,'horizon_hours':2})
  self.assertEqual(orig,self.c.run.scenario)
  self.assertEqual(result['kind'],'scenario')
  self.assertIn('mitigation',result)
 def test_invalid_scenario_rejected(self):
  with self.assertRaises(ValueError):self.c.apply_scenario({'scenario':'shovel_outage','affected':'shovel-not-found'})
 def test_apply_policy_changes_future_assignments_only(self):
  old_deliveries=len(self.c.run.deliveries)
  self.c.apply_policy({'policy':'balanced'})
  self.assertEqual(self.c.run.strategy,'balanced')
  self.assertEqual(len(self.c.run.deliveries),old_deliveries)
 def test_reports_accumulate_without_stopping(self):
  self.c.run.advance_to(2880);self.c.minute=2880
  self.c.playing=True
  self.c.tick()
  self.assertGreaterEqual(len(self.c.days),2)
  self.assertTrue((Path(self.temp.name)/'day-00001.json').exists())
  self.assertGreater(len(self.c.run.queue),0)
 def test_daily_shovel_count(self):
  report=window_report(self.c.run,0,240)
  self.assertEqual(len(report['shovels']),20)
  self.assertEqual(len(report['load_sites']),5)

if __name__=='__main__':unittest.main()
