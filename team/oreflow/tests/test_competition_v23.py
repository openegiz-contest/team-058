"""Competition Edition regression checks: grounded asset twins and decisions."""
import sys
from pathlib import Path
sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
import copy, tempfile, unittest
from engine import MineRun, DEFAULT_PUMPS, NAMESPACE
from setup_twins import definitions
from continuous import ContinuousMine

class CompetitionTests(unittest.TestCase):
    def test_original_and_extended_twin_coverage(self):
        twins=definitions();self.assertEqual(len(twins),159)
        for name in ('mine-01','t001','load-1','shovel-1-1','dump-1','fuel-l0','fuel-l3','road-l0-d0','road-d0-l0','road-c-l0'):
            self.assertIn(f'{NAMESPACE}:{name}',twins)
        roads=[x for x in twins if x.startswith(f'{NAMESPACE}:road-')]
        self.assertEqual(len(roads),55)
        self.assertEqual({twins[x]['attributes']['kind'] for x in roads},{'directed_haul_road'})
    def test_asset_statuses_from_real_scenario_events(self):
        mine=MineRun().advance_to(120)
        a=mine.asset_states(110)
        self.assertEqual(set(a['fuel_stations']),set(DEFAULT_PUMPS))
        self.assertEqual(len(a['shovels']),20)
        self.assertEqual(len(a['roads']),55)
        for row in a['fuel_stations'].values():
            self.assertLessEqual(row['pumps_busy'],row['pump_capacity'])
            self.assertGreaterEqual(row['fuel_dispensed_l'],0)
        road=MineRun(scenario='road_closure',route_from='L2',route_to='D4',closure_start=80,outage_start=80,outage_duration=60)
        self.assertEqual(road.asset_states(100)['roads']['L2->D4']['state'],'closed')
        self.assertEqual(road.asset_states(200)['roads']['L2->D4']['state'],'open')
        shovel=MineRun(scenario='shovel_outage',affected='shovel-3-1',outage_start=80,outage_duration=60)
        self.assertEqual(shovel.asset_states(100)['shovels']['shovel-3-1']['state'],'failed')
    def test_site_restriction_real_dispatch_and_time_limit(self):
        baseline=MineRun(seed=42).advance_to(120)
        restricted=copy.deepcopy(baseline)
        restricted.restricted_load_site='L2';restricted.restricted_until=240
        # Already planned loading reservations are unaffected. Only future
        # dispatches see the temporary loading-site exclusion.
        self.assertNotEqual(restricted._choose_load(restricted.trucks['T005'],150,'C'),2)
        self.assertEqual(restricted.restricted_load_site,'L2')
        restricted.advance_to(240)
        self.assertEqual(baseline.frame(120)['tonnes'],restricted.frame(120)['tonnes'])
    def test_scenario_is_isolated_and_includes_recovery_evidence(self):
        with tempfile.TemporaryDirectory() as temp:
            c=ContinuousMine(state_dir=temp);c.playing=False;c.run.advance_to(140);c.minute=140
            old=c.run.metrics()['tonnes'];old_scenario=c.run.scenario
            a=c._evaluate('scenario',{'scenario':'road_closure','road_from':'L2','road_to':'D4','delay_min':0,'duration_min':80,'horizon_hours':2})
            self.assertIn('recovered',a);self.assertIn('scenario_preview',a)
            self.assertEqual(a['normal']['tonnes'],sum(x['delivered_t'] for x in a['normal']['hourly']))
            self.assertEqual(c.run.metrics()['tonnes'],old)
            self.assertEqual(c.run.scenario,old_scenario)
            self.assertEqual(len(a['scenario_preview']['normal_trucks']),71)
