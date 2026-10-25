"""v2.1: verify that new charts and PDF/CSV summaries have an event-based source."""
import sys
from pathlib import Path
sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
import unittest
from engine import MineRun

class ReportTests(unittest.TestCase):
 @classmethod
 def setUpClass(cls): cls.mine_run=MineRun(duration=1440,seed=42).simulate();cls.report=cls.mine_run.operations_report()
 def test_complete_hourly(self):
  self.assertEqual(len(self.report['hourly']),24)
  self.assertAlmostEqual(sum(x['delivered_t'] for x in self.report['hourly']),self.mine_run.metrics()['tonnes'],places=1)
 def test_fuel_hourly_conservation(self):
  self.assertAlmostEqual(sum(x['fuel_l'] for x in self.report['hourly']),self.mine_run.metrics()['fuel_used_l'],delta=0.1)
 def test_per_class_attribution(self):
  self.assertEqual(sum(x['trucks'] for x in self.report['truck_classes']),71)
  self.assertEqual(sum(x['trips'] for x in self.report['truck_classes']),len(self.mine_run.deliveries))
  self.assertAlmostEqual(sum(x['delivered_t'] for x in self.report['truck_classes']),self.mine_run.metrics()['tonnes'],places=1)
 def test_all_20_shovels_and_loading_conservation(self):
  self.assertEqual(len(self.report['shovels']),20)
  self.assertAlmostEqual(sum(x['loaded_t'] for x in self.report['shovels']),sum(x['loaded_t'] for x in self.report['loading_sites']),delta=.1)
  self.assertGreater(max(x['loaded_t'] for x in self.report['shovels']),0)
  self.assertGreater(sum(x['cycles'] for x in self.report['shovels']),100)
 def test_activity_time_conservation(self):
  self.assertAlmostEqual(sum(self.report['activity_minutes'].values()),71*1440,delta=.2)
 def test_no_invented_shovel_diesel_or_grade(self):
  for x in self.report['shovels']:
   self.assertNotIn('fuel_l',x)
   self.assertNotIn('ore_grade',x)
  self.assertEqual(self.report['source'],'synthetic_simulation')
 def test_two_seeds_genuinely_different(self):
  other=MineRun(duration=240,seed=43).simulate().operations_report()
  base=MineRun(duration=240,seed=42).simulate().operations_report()
  self.assertNotEqual(other['metrics']['tonnes'],base['metrics']['tonnes'])

if __name__=='__main__':unittest.main()
