import importlib.util
import json
from pathlib import Path
import subprocess
import tempfile
import unittest

spec = importlib.util.spec_from_file_location('upgrade', Path(__file__).resolve().parents[1]/'scripts/upgrade-retained-source.py')
upgrade = importlib.util.module_from_spec(spec)
spec.loader.exec_module(upgrade)

class StableMergeTests(unittest.TestCase):
    def execute(self, base, board, stable):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            repo, tree, proof = [root/n for n in ('repo', 'board', 'proof')]
            for p in (repo, tree, proof): p.mkdir()
            def git(*args):
                subprocess.run(['git', '-C', str(repo), '-c', 'user.name=Test', '-c', 'user.email=test@example.invalid', *args], check=True, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
            git('init')
            (repo/'driver.c').write_text(base)
            git('add', '.')
            git('commit', '-m', 'base')
            git('tag', 'v6.18.44')
            (repo/'driver.c').write_text(stable)
            git('commit', '-am', 'stable')
            git('tag', 'v6.18.63')
            (tree/'driver.c').write_text(board)
            failed = False
            try: upgrade.upgrade(repo/'.git', tree, proof)
            except SystemExit: failed = True
            return failed, (tree/'driver.c').read_text(), json.loads((proof/'stable-merge.json').read_text())

    def test_preserves_disjoint_board_change_and_stable_fix(self):
        base = 'old\n' + 'unchanged\n'*12 + 'board-old\n'
        failed, result, _ = self.execute(base, base.replace('board-old', 'board-driver'), base.replace('old\n', 'stable-fix\n', 1))
        self.assertFalse(failed)
        self.assertIn('stable-fix', result)
        self.assertIn('board-driver', result)

    def test_overlap_stops_without_writing_conflict_markers_to_source(self):
        failed, result, report = self.execute('base\n', 'board\n', 'stable\n')
        self.assertTrue(failed)
        self.assertEqual(result, 'board\n')
        self.assertEqual(report['conflicts'], ['driver.c'])

    def test_already_applied_fix_is_not_reversed(self):
        failed, result, _ = self.execute('base\n', 'stable\n', 'stable\n')
        self.assertFalse(failed)
        self.assertEqual(result, 'stable\n')
