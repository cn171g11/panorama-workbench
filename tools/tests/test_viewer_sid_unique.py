import contextlib
import importlib.util
import io
import json
from pathlib import Path
import subprocess
import sys
import tempfile
import unittest

MODULE_PATH = Path(__file__).resolve().parents[1] / 'check_viewer_sid_unique.py'
spec = importlib.util.spec_from_file_location('sid_checker', MODULE_PATH)
module = importlib.util.module_from_spec(spec)
spec.loader.exec_module(module)
GAMES = json.loads((MODULE_PATH.parent / 'data/tencent-game-exceptions.json').read_text(encoding='utf-8'))['panoramaIds']

class SidInventoryTests(unittest.TestCase):
    def make_fixture(self, directory, *, duplicate=False, omit_game=False, legacy=False):
        root=Path(directory)
        row=['test123456',106.12345678901234,29.12345678901234,'路','','',0,0,'腾讯常规']
        if legacy: row=row[:-1]
        if duplicate: row[0]=GAMES[0]
        counts={'500000':1}
        game_rows=[[sid,111.6,10.3,'剑灵','','',0,0,'腾讯隐藏'] for sid in GAMES]
        if not omit_game: counts['hidden_game']=len(game_rows)
        (root/'data_meta.js').write_text('window.PANO_COUNT='+json.dumps(counts)+';',encoding='utf-8')
        (root/'data_500000.js').write_text('window.PANO_CITY["500000"]='+json.dumps([row])+';',encoding='utf-8')
        if omit_game:
            hidden='window.PANO_CITY["hidden"]=[];'
            counts['hidden']=0
            (root/'data_meta.js').write_text('window.PANO_COUNT='+json.dumps(counts)+';',encoding='utf-8')
        else: hidden='window.PANO_CITY["hidden_game"]='+json.dumps(game_rows)+';'
        (root/'hidden_pano.js').write_text(hidden,encoding='utf-8')
        return root
    def test_exact_inventory_and_legacy_sids_preserved(self):
        with tempfile.TemporaryDirectory() as d:
            root=self.make_fixture(d,legacy=True)
            originals={p.name:p.read_bytes() for p in root.iterdir()}
            with contextlib.redirect_stdout(io.StringIO()): r=module.check(root)
            self.assertEqual(r['records'],16); self.assertEqual(r['gamePoints'],15)
            self.assertEqual(r['duplicateExtra'],0)
            self.assertEqual(originals,{p.name:p.read_bytes() for p in root.iterdir()})
    def test_cli_fast_exit_only_after_successful_validation(self):
        with tempfile.TemporaryDirectory() as d:
            root=self.make_fixture(d)
            r=subprocess.run([sys.executable,str(MODULE_PATH),'--viewer',str(root)],capture_output=True,text=True)
            self.assertEqual(r.returncode,0,r.stderr)
            self.assertEqual(json.loads(r.stdout)['uniqueSid'],16)
    def test_duplicates_fail_api_and_cli(self):
        with tempfile.TemporaryDirectory() as d:
            root=self.make_fixture(d,duplicate=True)
            with contextlib.redirect_stdout(io.StringIO()),self.assertRaisesRegex(ValueError,'Duplicate SIDs'): module.check(root)
            r=subprocess.run([sys.executable,str(MODULE_PATH),'--viewer',str(root)],capture_output=True,text=True)
            self.assertNotEqual(r.returncode,0)
            self.assertIn('Duplicate SIDs',r.stderr)
    def test_registered_game_collection_cannot_silently_disappear(self):
        with tempfile.TemporaryDirectory() as d:
            root=self.make_fixture(d,omit_game=True)
            with self.assertRaisesRegex(ValueError,'game SID inventory'): module.check(root)

if __name__=='__main__': unittest.main()
