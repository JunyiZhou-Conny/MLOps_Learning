#!/usr/bin/env python3
# /// script
# requires-python = ">=3.9"
# dependencies = ["pyyaml"]
# ///
"""Clone or update every AC215 tutorial repository listed in course/lectures.yaml.

    uv run tools/sync_tutorials.py                # clone what's missing, fast-forward the rest
    uv run tools/sync_tutorials.py --only 5 6     # just the repos of lectures 5 and 6
    uv run tools/sync_tutorials.py --only llm-rag # or name repos directly
    uv run tools/sync_tutorials.py --pinned       # check out the commits the guides/videos were made from
    uv run tools/sync_tutorials.py --latest       # back to each repo's default branch, then pull
    uv run tools/sync_tutorials.py --status       # one line per repo: branch, commit, dirty, behind/ahead

Repos go to tutorials/<name> (gitignored), or to --dir / $AC215_TUTORIALS. A repo with
uncommitted changes is never touched (you get a warning instead), so your own edits are safe.
(`uv run` reads the header above and brings PyYAML along; plain `python3` works if PyYAML is installed.)
"""

from __future__ import annotations

import argparse
import os
import subprocess
import sys
from pathlib import Path

import yaml

ROOT = Path(__file__).resolve().parent.parent
SPEC = yaml.safe_load((ROOT / "course" / "lectures.yaml").read_text(encoding="utf-8"))


def git(repo: Path, *args: str, check: bool = True, capture: bool = True) -> str:
    r = subprocess.run(["git", "-C", str(repo), *args], text=True,
                       capture_output=capture, check=False)
    if check and r.returncode != 0:
        raise RuntimeError(f"git {' '.join(args)} failed in {repo.name}:\n{r.stderr.strip()}")
    return (r.stdout or "").strip()


def selected(only: list[str]) -> list[str]:
    names = list(SPEC["repos"])
    if not only:
        return names
    out: list[str] = []
    for item in only:
        if item.isdigit():
            lec = next((l for l in SPEC["lectures"] if l["n"] == int(item)), None)
            if lec is None:
                sys.exit(f"no lecture {item}")
            out += [t["repo"] for t in lec.get("tutorials", []) if t.get("repo")]
        elif item in SPEC["repos"]:
            out.append(item)
        else:
            sys.exit(f"unknown lecture or repo: {item}")
    return list(dict.fromkeys(out))


def dirty(repo: Path) -> bool:
    return bool(git(repo, "status", "--porcelain"))


def default_branch(repo: Path) -> str:
    ref = git(repo, "symbolic-ref", "--short", "refs/remotes/origin/HEAD", check=False)
    return ref.split("/", 1)[1] if "/" in ref else "main"


def sync(name: str, base: Path, mode: str) -> str:
    info = SPEC["repos"][name]
    repo = base / name
    if not repo.exists():
        subprocess.run(["git", "clone", "--quiet", info["url"], str(repo)], check=True)
        msg = "cloned"
    else:
        if dirty(repo):
            return f"SKIPPED (uncommitted changes; commit or stash them first)"
        git(repo, "fetch", "--quiet", "--all", "--prune")
        msg = "fetched"
    if mode == "pinned":
        git(repo, "checkout", "--quiet", "--detach", info["pinned"])
        return f"{msg}, at pinned {info['pinned']} (detached; `--latest` to go back)"
    branch = default_branch(repo)
    if git(repo, "rev-parse", "--abbrev-ref", "HEAD") != branch:
        git(repo, "checkout", "--quiet", branch)
    git(repo, "merge", "--quiet", "--ff-only", f"origin/{branch}", check=False)
    head = git(repo, "rev-parse", "--short", "HEAD")
    note = "" if head.startswith(info["pinned"][:7]) else f"  (guide/video made at {info['pinned']})"
    return f"{msg}, {branch} @ {head}{note}"


def status(name: str, base: Path) -> str:
    repo = base / name
    if not repo.exists():
        return "not cloned"
    head = git(repo, "rev-parse", "--short", "HEAD")
    branch = git(repo, "rev-parse", "--abbrev-ref", "HEAD")
    up = git(repo, "rev-list", "--left-right", "--count", "HEAD...@{upstream}", check=False)
    ab = ""
    if up:
        ahead, behind = up.split()
        ab = f"  ahead {ahead} / behind {behind}" if ahead != "0" or behind != "0" else "  up to date"
    pin = SPEC["repos"][name]["pinned"]
    return f"{branch} @ {head}{ab}{'  DIRTY' if dirty(repo) else ''}{'  = pinned' if head.startswith(pin[:7]) else ''}"


def main() -> None:
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--only", nargs="*", default=[], help="lecture numbers and/or repo names")
    ap.add_argument("--dir", default=os.environ.get("AC215_TUTORIALS", str(ROOT / "tutorials")))
    g = ap.add_mutually_exclusive_group()
    g.add_argument("--pinned", action="store_true", help="check out the commits the guides were made from")
    g.add_argument("--latest", action="store_true", help="default branch, fast-forwarded (the default)")
    g.add_argument("--status", action="store_true", help="report only, change nothing")
    args = ap.parse_args()

    base = Path(args.dir).expanduser().resolve()
    base.mkdir(parents=True, exist_ok=True)
    width = max(len(n) for n in SPEC["repos"])
    for name in selected(args.only):
        try:
            line = status(name, base) if args.status else sync(name, base, "pinned" if args.pinned else "latest")
        except (RuntimeError, subprocess.CalledProcessError) as e:
            line = f"ERROR: {e}"
        print(f"{name:<{width}}  {line}", flush=True)


if __name__ == "__main__":
    main()
