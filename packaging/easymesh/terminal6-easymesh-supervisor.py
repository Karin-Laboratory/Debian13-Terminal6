#!/usr/bin/env python3
"""Start only the prplMesh control plane; never reconfigure Linux networking."""
from __future__ import annotations

import argparse
import configparser
import os
from pathlib import Path
import signal
import shutil
import stat
import subprocess
import sys
import time


CHILDREN: list[subprocess.Popen] = []
STOP = False


def stop_children(signum: int, _frame: object) -> None:
    global STOP
    STOP = True
    for child in reversed(CHILDREN):
        if child.poll() is None:
            try:
                os.killpg(child.pid, signal.SIGTERM)
            except ProcessLookupError:
                pass


def read_role(path: Path) -> str:
    parser = configparser.ConfigParser(interpolation=None, strict=True)
    with path.open(encoding="utf-8") as stream:
        parser.read_file(stream)
    role = parser.get("node", "role", fallback="")
    if role not in {"controller", "agent", "controller-agent"}:
        raise ValueError("invalid node role")
    return role


def process_names(role: str) -> list[str]:
    if role not in {"controller", "agent", "controller-agent"}:
        raise ValueError("invalid node role")
    names = ["ieee1905_transport"]
    if role in {"controller", "controller-agent"}:
        names.append("beerocks_controller")
    names.extend(["beerocks_agent", "beerocks_vendor_message"])
    return names


def safe_file(path: Path, max_mode: int) -> None:
    st = path.stat()
    if st.st_uid != 0 or st.st_mode & max_mode:
        raise ValueError(f"unsafe owner or mode: {path.name}")
    if not path.is_file() or path.is_symlink():
        raise ValueError(f"not a regular file: {path.name}")


def copy_runtime_db(source: Path, destination: Path) -> None:
    parent = destination.parent
    parent.mkdir(mode=0o700, parents=True, exist_ok=True)
    parent_info = parent.lstat()
    if not stat.S_ISDIR(parent_info.st_mode) or parent_info.st_uid != os.geteuid():
        raise ValueError("unsafe runtime configuration directory")
    os.chmod(parent, 0o700)
    try:
        existing = destination.lstat()
    except FileNotFoundError:
        existing = None
    if existing and (not stat.S_ISREG(existing.st_mode) or existing.st_uid != os.geteuid()):
        raise ValueError("unsafe existing runtime platform database")

    temporary = parent / f".{destination.name}.{os.getpid()}.tmp"
    flags = os.O_WRONLY | os.O_CREAT | os.O_EXCL
    if hasattr(os, "O_NOFOLLOW"):
        flags |= os.O_NOFOLLOW
    fd = os.open(temporary, flags, 0o600)
    try:
        with os.fdopen(fd, "wb") as stream:
            stream.write(source.read_bytes())
            stream.flush()
            os.fsync(stream.fileno())
        os.replace(temporary, destination)
        os.chmod(destination, 0o600)
        dir_fd = os.open(parent, os.O_RDONLY | getattr(os, "O_DIRECTORY", 0))
        try:
            os.fsync(dir_fd)
        finally:
            os.close(dir_fd)
    except BaseException:
        try:
            temporary.unlink()
        except FileNotFoundError:
            pass
        raise


def add_ebtables_rule() -> bool:
    """Return whether this process added the upstream control-frame rule."""
    if shutil.which("ebtables") is None:
        raise RuntimeError("ebtables is required for the upstream IEEE 1905 rule")
    rule = ["ebtables", "-C", "FORWARD", "-d", "01:80:c2:00:00:13", "-j", "DROP"]
    probe = subprocess.run(rule, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL, check=False)
    if probe.returncode == 0:
        return False
    add = subprocess.run(["ebtables", "-I", "FORWARD", "-d", "01:80:c2:00:00:13", "-j", "DROP"],
                         stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL, check=False)
    if add.returncode:
        raise RuntimeError("could not install required IEEE 1905 forwarding rule")
    return True


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("--config", type=Path, default=Path("/etc/terminal6-easymesh/node.conf"))
    ap.add_argument("--platform-db", type=Path, default=Path("/etc/terminal6-easymesh/prplmesh_platform_db"))
    ap.add_argument("--prefix", type=Path, default=Path("/opt/terminal6-easymesh"))
    args = ap.parse_args()
    if os.geteuid() != 0:
        print("EASYMESH_SUPERVISOR=FAIL reason=root_required", file=sys.stderr)
        return 1

    rule_owned = False
    try:
        safe_file(args.config, 0o022)
        safe_file(args.platform_db, 0o077)
        role = read_role(args.config)
        db_runtime = Path("/tmp/beerocks/prplmesh_platform_db")
        copy_runtime_db(args.platform_db, db_runtime)

        bindir = args.prefix / "bin"
        names = process_names(role)
        for name in names:
            path = bindir / name
            if not path.is_file() or not os.access(path, os.X_OK):
                raise ValueError(f"required executable missing: {name}")

        # Upstream's Linux init adds this rule. Do it explicitly here, without its
        # interface creation, address flushing, or NetworkManager operations.
        signal.signal(signal.SIGTERM, stop_children)
        signal.signal(signal.SIGINT, stop_children)
        rule_owned = add_ebtables_rule()
        if STOP:
            raise RuntimeError("startup cancelled before process launch")
        for name in names:
            CHILDREN.append(subprocess.Popen([str(bindir / name)], start_new_session=True))
            time.sleep(0.2)
            if CHILDREN[-1].poll() is not None:
                raise RuntimeError(f"process exited during startup: {name}")

        while not STOP:
            for child, name in zip(CHILDREN, names):
                code = child.poll()
                if code is not None:
                    raise RuntimeError(f"process exited: {name} status={code}")
            time.sleep(1)
    except (OSError, ValueError, RuntimeError, configparser.Error) as exc:
        print(f"EASYMESH_SUPERVISOR=FAIL reason={exc}", file=sys.stderr)
        return 1
    finally:
        stop_children(signal.SIGTERM, None)
        for child in reversed(CHILDREN):
            try:
                child.wait(timeout=5)
            except subprocess.TimeoutExpired:
                try:
                    os.killpg(child.pid, signal.SIGKILL)
                except ProcessLookupError:
                    pass
                child.wait()
        if rule_owned:
            subprocess.run(["ebtables", "-D", "FORWARD", "-d", "01:80:c2:00:00:13", "-j", "DROP"],
                           stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL, check=False)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
