#!/usr/bin/env python3
# SPDX-License-Identifier: MIT
"""Three-way stable upgrade preserving board changes; never accept conflict markers."""
import argparse
import importlib.util
import json
import pathlib
import subprocess
import tempfile


def upgrade(gitdir, tree, proof):
    def git(*args):
        return subprocess.check_output(['git', '--git-dir=' + str(gitdir), *args])
    def blob(ref, name):
        p = subprocess.run(['git', '--git-dir=' + str(gitdir), 'show', ref + ':' + name],
                           stdout=subprocess.PIPE, stderr=subprocess.PIPE)
        return p.stdout if p.returncode == 0 else None
    changes = git('diff', '--no-renames', '--name-status', '-z', 'v6.18.44', 'v6.18.63').split(b'\0')
    conflicts = []
    reviewed = []
    resolver = None
    resolver_path = pathlib.Path(__file__).with_name('resolve-stable-conflicts.py')
    if resolver_path.is_file():
        spec = importlib.util.spec_from_file_location('reviewed_stable_resolutions', resolver_path)
        resolver = importlib.util.module_from_spec(spec)
        spec.loader.exec_module(resolver)
    merged = []
    for i in range(0, len(changes) - 1, 2):
        status, name = changes[i].decode(), changes[i+1].decode()
        rel = pathlib.PurePosixPath(name)
        if rel.is_absolute() or '..' in rel.parts:
            raise ValueError('unsafe stable source path')
        path = tree / name
        if path.is_symlink():
            raise ValueError('symlink in changed stable source: ' + name)
        base = blob('v6.18.44', name)
        newer = blob('v6.18.63', name)
        ours = path.read_bytes() if path.is_file() else None
        conflict = False
        if ours == base or ours == newer:
            result = newer
        elif base is not None and ours is not None and newer is not None:
            with tempfile.TemporaryDirectory() as tmp:
                files = [pathlib.Path(tmp) / n for n in ('board', 'base-6.18.44', 'stable-6.18.63')]
                for dest, data in zip(files, (ours, base, newer)):
                    dest.write_bytes(data)
                p = subprocess.run(['git', 'merge-file', '--diff3', '-p', *map(str, files)],
                                   stdout=subprocess.PIPE, stderr=subprocess.PIPE)
                result = p.stdout
                conflict = p.returncode != 0
        else:
            result = ours
            conflict = True
        if conflict and resolver is not None:
            accepted, resolution = resolver.resolve(name, base, ours, newer, result)
            if accepted:
                result = resolution
                conflict = False
                reviewed.append(name)
        if conflict:
            conflicts.append(name)
            for suffix, data in (('.board', ours), ('.base', base), ('.stable', newer), ('.merge', result)):
                out = proof / 'conflicts' / (name + suffix)
                out.parent.mkdir(parents=True, exist_ok=True)
                if data is not None:
                    out.write_bytes(data)
            continue
        if result is None:
            path.unlink(missing_ok=True)
        else:
            path.parent.mkdir(parents=True, exist_ok=True)
            path.write_bytes(result)
            mode = git('ls-tree', 'v6.18.63', '--', name).split(b' ', 1)[0]
            path.chmod(0o755 if mode == b'100755' else 0o644)
        merged.append(name)
    report = {'base': '6.18.44', 'target': '6.18.63', 'merged': merged, 'conflicts': conflicts, 'reviewed_resolutions': reviewed}
    (proof / 'stable-merge.json').write_text(json.dumps(report, indent=2) + '\n')
    print('STABLE_THREE_WAY_MERGED', len(merged), 'CONFLICTS', conflicts)
    if conflicts:
        raise SystemExit(3)

if __name__ == '__main__':
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument('gitdir', type=pathlib.Path)
    p.add_argument('tree', type=pathlib.Path)
    p.add_argument('proof', type=pathlib.Path)
    a = p.parse_args()
    upgrade(a.gitdir, a.tree, a.proof)
