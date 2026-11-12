#!/usr/bin/env python3
"""Sync one vendored plugin from its upstream repository.

Usage:
    python3 scripts/sync_upstream.py plugins/<name> [--body-file PATH]

Each plugin folder copied from someone else has an `upstream.json`:

    {
      "repo": "owner/name",          # GitHub repository it comes from
      "branch": "main",              # branch to follow
      "path": "",                    # plugin folder inside that repo ("" = repo root)
      "include": ["skills", ...],    # files/folders to copy, relative to `path`
      "commit": "<sha>"              # upstream commit the local copy matches
    }

The script shallow-clones the upstream branch, compares only the `include`
paths with the local copy, and if anything differs it replaces them and
records the new commit. Files not listed in `include` (our own plugin.json,
upstream.json) are never touched. It never runs anything from upstream.

When run in GitHub Actions it writes `changed`, `short` and `commit` to
$GITHUB_OUTPUT, and with --body-file it writes a pull request description.
"""

import argparse
import datetime
import filecmp
import json
import os
import shutil
import subprocess
import sys
import tempfile
from pathlib import Path

# Files that execute or configure execution. Changes to these are flagged
# in the pull request so they get a closer look.
RISKY_SUFFIXES = {".sh", ".bash", ".js", ".cjs", ".mjs", ".ts", ".py", ".cmd", ".ps1", ".rb", ".go"}
RISKY_NAMES = {"hooks.json", ".mcp.json", "plugin.json", "package.json", "settings.json"}


def files_under(root: Path) -> dict[str, Path]:
    """Map relative path -> absolute path for every file under root (or root itself)."""
    if not root.exists():
        return {}
    if root.is_symlink():
        sys.exit(f"refusing to copy symlink: {root}")
    if root.is_file():
        return {"": root}
    out = {}
    for p in sorted(root.rglob("*")):
        if p.is_symlink():
            sys.exit(f"refusing to copy symlink: {p}")
        if p.is_file():
            out[p.relative_to(root).as_posix()] = p
    return out


def diff_paths(src: Path, dst: Path, label: str):
    a, b = files_under(src), files_under(dst)
    join = lambda rel: f"{label}/{rel}" if rel else label
    added = [join(r) for r in a if r not in b]
    removed = [join(r) for r in b if r not in a]
    modified = [join(r) for r in a if r in b and not filecmp.cmp(a[r], b[r], shallow=False)]
    return added, removed, modified


def is_risky(path: str) -> bool:
    p = Path(path)
    return p.suffix in RISKY_SUFFIXES or p.name in RISKY_NAMES or "hooks" in p.parts


def set_output(**kv):
    target = os.environ.get("GITHUB_OUTPUT")
    if target:
        with open(target, "a") as f:
            for k, v in kv.items():
                f.write(f"{k}={v}\n")


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("plugin_dir")
    ap.add_argument("--body-file")
    args = ap.parse_args()

    plugin = Path(args.plugin_dir).resolve()
    cfg_path = plugin / "upstream.json"
    cfg = json.loads(cfg_path.read_text())
    repo, branch = cfg["repo"], cfg.get("branch", "main")
    sub = cfg.get("path", "")

    with tempfile.TemporaryDirectory() as tmp:
        clone = Path(tmp) / "upstream"
        subprocess.run(
            ["git", "clone", "--quiet", "--depth", "1", "--branch", branch,
             f"https://github.com/{repo}.git", str(clone)],
            check=True, env={**os.environ, "GIT_LFS_SKIP_SMUDGE": "1", "GIT_TERMINAL_PROMPT": "0"},
        )
        new_commit = subprocess.run(["git", "-C", str(clone), "rev-parse", "HEAD"],
                                    check=True, capture_output=True, text=True).stdout.strip()
        root = clone / sub if sub else clone

        added, removed, modified = [], [], []
        for inc in cfg["include"]:
            src = root / inc
            if not src.exists():
                sys.exit(f"{repo}: '{inc}' no longer exists upstream; update {cfg_path.name} by hand")
            a, r, m = diff_paths(src, plugin / inc, inc)
            added += a; removed += r; modified += m

        changed = bool(added or removed or modified)
        name = plugin.name
        if not changed:
            print(f"{name}: up to date with {repo}@{new_commit[:7]}")
            set_output(changed="false", short=new_commit[:7], commit=new_commit)
            return

        for inc in cfg["include"]:
            src, dst = root / inc, plugin / inc
            if dst.is_dir():
                shutil.rmtree(dst)
            elif dst.exists():
                dst.unlink()
            dst.parent.mkdir(parents=True, exist_ok=True)
            if src.is_dir():
                shutil.copytree(src, dst)
            else:
                shutil.copy2(src, dst)

        old_commit = cfg.get("commit", "")
        cfg["commit"] = new_commit
        cfg_path.write_text(json.dumps(cfg, indent=2) + "\n")

        # When plugin.json is our own (upstream has none), bump its version so
        # installed copies see the update. Date-based versions are valid semver.
        if ".claude-plugin/plugin.json" not in cfg["include"]:
            manifest_path = plugin / ".claude-plugin" / "plugin.json"
            if manifest_path.exists():
                manifest = json.loads(manifest_path.read_text())
                today = datetime.date.today()
                manifest["version"] = f"{today.year}.{today.month}.{today.day}"
                manifest_path.write_text(json.dumps(manifest, indent=2) + "\n")

        print(f"{name}: updated to {repo}@{new_commit[:7]} "
              f"(+{len(added)} -{len(removed)} ~{len(modified)})")
        set_output(changed="true", short=new_commit[:7], commit=new_commit)

        if args.body_file:
            Path(args.body_file).write_text(pr_body(name, repo, old_commit, new_commit,
                                                    added, removed, modified))


def pr_body(name, repo, old, new, added, removed, modified):
    lines = [f"Upstream `{repo}` changed the files this repo copies for **{name}**.", ""]
    if old:
        lines.append(f"Full upstream diff: https://github.com/{repo}/compare/{old}...{new}")
    else:
        lines.append(f"Upstream commit: https://github.com/{repo}/commit/{new}")
    lines.append("")
    risky = [p for p in added + modified if is_risky(p)]
    if risky:
        lines += ["### ⚠️ Look closely: these files run code or change what runs", ""]
        lines += [f"- `{p}`" for p in risky] + [""]
    for title, items in (("Added", added), ("Changed", modified), ("Removed", removed)):
        if items:
            lines += [f"### {title}", ""] + [f"- `{p}`" for p in items] + [""]
    lines += [
        "### Before merging",
        "",
        "- [ ] Read the diff of every `SKILL.md`: does it still do what it did, with no new instructions to fetch, send or run things?",
        "- [ ] Read any flagged script or hook change line by line.",
        "- [ ] Nothing asks for credentials, tokens or network hosts it didn't need before.",
        "",
        "Opened automatically by the weekly upstream check. If you close it without merging, next week's check opens it again. "
        "To stop following upstream for this skill, delete its `upstream.json`.",
    ]
    return "\n".join(lines) + "\n"


if __name__ == "__main__":
    main()
