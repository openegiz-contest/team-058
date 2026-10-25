"""Regression tests for user-reported V2.3 failures."""
import sys, tempfile, copy, pickle, unittest
from pathlib import Path
sys.path.insert(0,str(Path(__file__).resolve().parents[1]))
from engine import MineRun
from continuous import ContinuousMine
from server import export_rows, EXPORT_SCHEMAS, format_csv

class HotfixTests(unittest.TestCase):
 def test_old_checkpoint_migrates_dispatch_properties_and_scenario(self):
  with tempfile.TemporaryDirectory() as tmp:
   c=ContinuousMine(tmp);c.playing=False;c.run.advance_to(140);c.minute=140
   del c.run.restricted_load_site;del c.run.restricted_until
   c.save()
   restored=ContinuousMine(tmp);restored.playing=False
   self.assertIsNone(restored.run.restricted_load_site)
   self.assertEqual(restored.run.restricted_until,0.)
   answer=restored._evaluate('scenario',{'scenario':'shovel_outage','affected':'shovel-3-1','delay_min':0,'duration_min':90,'horizon_hours':2})
   self.assertIn('recovered',answer)
   self.assertEqual(answer['kind'],'scenario')
   self.assertEqual(restored.run.scenario,'normal')
 def test_pause_resume_and_reset_to_new_mine(self):
  with tempfile.TemporaryDirectory() as tmp:
   c=ContinuousMine(tmp);c.playing=False;c.run.advance_to(160);c.minute=160;c.save()
   old=c.run_id
   c.control({'playing':True});self.assertTrue(c.playing)
   c.control({'playing':False});self.assertFalse(c.playing)
   result=c.fresh_start()
   self.assertTrue(result['started']);self.assertNotEqual(old,c.run_id)
   self.assertLess(c.minute,0.1);self.assertTrue(c.playing)
   self.assertEqual(c.run.metrics()['trips'],0)
   self.assertEqual(len(list((Path(tmp)/'previous_runs').glob('*/mine-state.pkl'))),1)
   restart=ContinuousMine(tmp)
   self.assertEqual(restart.run_id,c.run_id)
   self.assertLess(restart.minute,0.1)
 def test_exports_tag_source_vs_simulated_and_correct_columns(self):
  with tempfile.TemporaryDirectory() as tmp:
   c=ContinuousMine(tmp);c.playing=False;c.run.advance_to(180);c.minute=180
   self.assertEqual(len(export_rows('source-trucks',c)),71)
   self.assertEqual(len(export_rows('source-shovels',c)),20)
   self.assertEqual(len(export_rows('source-roads',c)),55)
   for k in EXPORT_SCHEMAS:
    rows=export_rows(k,c)
    content=format_csv(k,rows).decode('utf-8-sig')
    self.assertTrue(content.startswith(','.join(EXPORT_SCHEMAS[k])))
    if rows:
     self.assertIn('record_origin',rows[0])
     self.assertTrue(all(r['record_origin'].startswith('OpenMines') if k.startswith('source') else r['record_origin'].startswith('OreFlow simulated') for r in rows))
   self.assertGreater(len(export_rows('trips',c)),0)
