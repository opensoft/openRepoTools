# SPDX-License-Identifier: Apache-2.0
"""The sandbox every Amendment 23 module shares (`tests/test_a23_*.py`).

A bare origin seeded with a register, W cloned from it, and the
`workspace.yaml` naming W, with the real `lanes-edit.sh` run in a scrubbed
environment: a `$HOME` of its own, `gh` and `tmux` that refuse, and no
inherited `LANES_*`, `TMUX*`, `GIT_*` or `CLAUDE_*`. W is a clone of its own,
never a view of the seed or of a lane's checkout, so W can be seen to lag.

Amendment 23's routing is opt-in until its slice 1b (the review of
opensoft/openRepoTools#282, MUST 2), so the box exports
`LANES_ROUTE_WRITES=1` unless a case asks for the default with `route=False`.
Nothing reaches a real remote.
"""

from __future__ import annotations

import os
import subprocess
from pathlib import Path

from conftest import REPO

REGISTER = "lanes/LANES.md"
HEADER = ("# LANES.md -- the sandbox register\n\n"
          "| lane | session id | workstation / env / user | started (UTC) "
          "| objects owned | handoff path | state |\n"
          "|---|---|---|---|---|---|---|\n")
#: `LANES_CONTAINER` and `LANES_HOST` as the box pins them: "this container".
ME = "bench-a hosta"

SCRUBBED_PREFIXES = ("LANES_", "LANE_START_", "CLAUDE_", "OPENREPOTOOLS_",
                     "FAKE_", "GIT_", "TMUX")
SCRUBBED = {"AGENT_PROTOCOL_ROOT", "PROJECTS_ROOT", "XDG_CONFIG_HOME",
            "XDG_CACHE_HOME"}

REFUSE = """#!/usr/bin/env bash
printf 'FAKE %s REFUSED: %s -- this suite reaches no real surface\\n' "${0##*/}" "$*" >&2
exit 90
"""

#: `LANES_GIT`: every NETWORK call the helper makes, logged one per line, then
#: an optional hook (`FAKE_NET_HOOK`, run as `<hook> <op> <git args…>`), then the
#: real git. The hook decides: exit 0 runs the real git; exit 97 means the hook
#: ran git itself and the call succeeded; any other exit is the call's own
#: (a failure). `<op>` is the git subcommand: fetch, push, ls-remote or clone.
NET_GIT = """#!/usr/bin/env bash
op=""
for a in "$@"; do case "$a" in fetch|push|pull|ls-remote|clone) op="$a"; break ;; esac; done
printf '%s %s\\n' "$op" "$*" >> "$FAKE_NET_LOG"
if [ -n "${FAKE_NET_HOOK:-}" ]; then
  rc=0; "$FAKE_NET_HOOK" "$op" "$@" || rc=$?
  case "$rc" in 0) : ;; 97) exit 0 ;; *) exit "$rc" ;; esac
fi
exec git "$@"
"""


def register_text(rows) -> str:
    return HEADER + "".join(f"{r}\n" for r in rows)


class RegisterBox:
    """A bare origin, W cloned from it, and the workspace.yaml naming W.

    `files` seeds origin's first commit; `seed_dir` names the clone that made
    it, which stays as a peer able to push; `second_branch` adds `side` on
    origin; `w_reference` clones W with `--reference`."""

    def __init__(self, root: Path, files: dict, *, seed_dir: str = "seed",
                 second_branch: bool = False, w_reference: Path | None = None,
                 route: bool = True, env: dict | None = None) -> None:
        # REAL PATHS, because the helper prints W and its lane checkouts as
        # `pwd -P` spells them (a temp root under a symlink would not match).
        root = Path(os.path.realpath(root))
        root.mkdir(parents=True, exist_ok=True)
        self.root = root
        self.home = root / "home"
        self.origin = root / "origin.git"
        self.w = self.home / "projects" / "brett-wip"
        self.lanes_root = self.home / "projects" / "brett-wip-lanes"
        self.fakebin = root / "fakebin"
        for d in (self.home / ".agents", self.home / "projects", root / "tmp", self.fakebin):
            d.mkdir(parents=True, exist_ok=True)
        for name in ("gh", "tmux"):
            (self.fakebin / name).write_text(REFUSE, encoding="utf-8")
            (self.fakebin / name).chmod(0o755)
        base = {k: v for k, v in os.environ.items()
                if k not in SCRUBBED and not k.startswith(SCRUBBED_PREFIXES)}
        base.update({
            "HOME": str(self.home),
            "TMPDIR": str(root / "tmp"),
            "XDG_CONFIG_HOME": str(self.home / ".config"),
            "XDG_CACHE_HOME": str(self.home / ".cache"),
            "PATH": f"{self.fakebin}{os.pathsep}{base.get('PATH', '')}",
            "AGENT_PROTOCOL_ROOT": str(self.home / ".agents"),
            "LANES_WORKSTATION": "Eagle",
            "LANES_HOST": "hosta",
            "LANES_CONTAINER": "bench-a",
            "LANES_NO_GITHUB": "1",
            "LANES_INDEX": "off",
            "LANE_WORKTREES_REPORT": "off",
            "GIT_AUTHOR_NAME": "a23 tests",
            "GIT_AUTHOR_EMAIL": "test@example.invalid",
            "GIT_COMMITTER_NAME": "a23 tests",
            "GIT_COMMITTER_EMAIL": "test@example.invalid",
        })
        if route:
            base["LANES_ROUTE_WRITES"] = "1"
        base.update(env or {})
        self.env = base
        self.git("init", "-q", "--bare", "-b", "main", str(self.origin))
        self.quiet(self.origin, bare=True)
        self.seed = root / seed_dir
        self.git("clone", "-q", str(self.origin), str(self.seed))
        self.quiet(self.seed)
        for rel, text in files.items():
            self.write(self.seed, rel, text)
        self.commit(self.seed, "seed", *files)
        self.git("-C", str(self.seed), "push", "-q", "origin", "main")
        if second_branch:
            # A SECOND BRANCH ON ORIGIN, so a clone that took every branch shows.
            self.git("-C", str(self.seed), "push", "-q", "origin", "main:refs/heads/side")
        clone = ["clone", "-q"]
        if w_reference is not None:
            clone += ["--reference", str(w_reference)]
        self.git(*clone, str(self.origin), str(self.w))
        self.quiet(self.w)
        (self.home / ".agents" / "workspace.yaml").write_text(
            f"repository: {self.origin}\npath: {self.w}\n", encoding="utf-8")

    # ------------------------------------------------------------- git
    def quiet(self, repo: Path, *, bare: bool = False) -> None:
        """gc.auto=0 and maintenance.auto=false: W is what lane checkouts borrow."""
        where = ["--git-dir", str(repo)] if bare else ["-C", str(repo)]
        self.git(*where, "config", "gc.auto", "0")
        self.git(*where, "config", "maintenance.auto", "false")

    def git(self, *args: str, check: bool = True) -> str:
        return subprocess.run(["git", *args], env=self.env, check=check,
                              capture_output=True, text=True).stdout

    @staticmethod
    def write(checkout: Path, rel: str, text: str) -> Path:
        path = checkout / rel
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(text, encoding="utf-8")
        return path

    def commit(self, checkout: Path, message: str, *paths: str) -> None:
        self.git("-C", str(checkout), "add", "--", *paths)
        self.git("-C", str(checkout), "commit", "-q", "-m", message)

    def clone(self, dest: Path, *, origin: Path | None = None,
              reference: Path | None = None) -> Path:
        args = ["clone", "-q"]
        if reference is not None:
            args += ["--reference", str(reference)]
        self.git(*args, str(origin or self.origin), str(dest))
        self.quiet(dest)
        return dest

    def peer_pushes(self, rel: str, text: str) -> None:
        """The seed clone, as a peer, publishes one more file."""
        self.write(self.seed, rel, text)
        self.commit(self.seed, f"a peer writes {rel}", rel)
        self.git("-C", str(self.seed), "push", "-q", "origin", "main")

    def peer_edits(self, rel: str, old: str, new: str, message: str = "") -> None:
        """The seed clone, brought up to date, replaces `old` with `new` in one
        file and publishes it: another writer's commit landing first."""
        self.git("-C", str(self.seed), "pull", "-q", "--ff-only", "origin", "main")
        path = self.seed / rel
        text = path.read_text(encoding="utf-8")
        assert text.count(old) == 1, (rel, old)
        path.write_text(text.replace(old, new), encoding="utf-8")
        self.commit(self.seed, message or f"a peer edits {rel}", rel)
        self.git("-C", str(self.seed), "push", "-q", "origin", "main")

    # ------------------------------------------------------------- the seam
    def seam(self, name: str = "c") -> Path:
        """A clone of origin named by the explicit `LANES_REPO` (S2.1, the
        test seam): every write of this box then goes through it, in place."""
        checkout = self.clone(self.root / name)
        self.env["LANES_REPO"] = str(checkout)
        return checkout

    def use_net(self, hook: str = "") -> Path:
        """Route the helper's network calls through `NET_GIT`, logged to
        `self.net_log`; `hook` is the body of `FAKE_NET_HOOK`, if any."""
        shim = self.fakebin / "net-git"
        shim.write_text(NET_GIT, encoding="utf-8")
        shim.chmod(0o755)
        self.net_log = self.root / "net.log"
        self.net_log.write_text("", encoding="utf-8")
        self.env["LANES_GIT"] = str(shim)
        self.env["FAKE_NET_LOG"] = str(self.net_log)
        if hook:
            body = self.fakebin / "net-hook"
            body.write_text("#!/usr/bin/env bash\n" + hook, encoding="utf-8")
            body.chmod(0o755)
            self.env["FAKE_NET_HOOK"] = str(body)
        return shim

    def net_ops(self) -> list:
        """The network operations the helper made, in order."""
        return [line.split(" ", 1)[0] for line in
                self.net_log.read_text(encoding="utf-8").splitlines()]

    def snapshot(self, checkout: Path) -> tuple:
        """Everything a refusal must leave as it was: HEAD and the branch it
        is on, the index, the working tree, and origin's tip."""
        c = ["-C", str(checkout)]
        return (self.git(*c, "rev-parse", "HEAD").strip(),
                self.git(*c, "symbolic-ref", "-q", "HEAD", check=False).strip(),
                self.git(*c, "status", "--porcelain", "--untracked-files=all"),
                self.git(*c, "diff"),
                self.git(*c, "diff", "--cached"),
                self.origin_head())

    @staticmethod
    def lock_of(checkout: Path) -> Path:
        return checkout / "lanes" / ".lanes-edit.lock"

    def unpublished(self, checkout: Path) -> list:
        """`git cherry -v origin/main HEAD`'s `+` lines: what origin lacks."""
        self.git("-C", str(checkout), "fetch", "-q", "origin")
        return [line for line in self.git("-C", str(checkout), "cherry", "-v",
                                          "refs/remotes/origin/main", "HEAD").splitlines()
                if line.startswith("+")]

    # ------------------------------------------------------------- the helper
    def cmd(self, *args: str) -> list:
        return ["bash", str(REPO / "lanes-edit.sh"), *args]

    def helper(self, *args: str, timeout: int = 180, **extra: str) -> subprocess.CompletedProcess:
        return subprocess.run(self.cmd(*args), env=dict(self.env, **extra), cwd=str(self.root),
                              capture_output=True, text=True, timeout=timeout, check=False)

    def popen(self, *args: str, **extra: str) -> subprocess.Popen:
        return subprocess.Popen(self.cmd(*args), env=dict(self.env, **extra), cwd=str(self.root),
                                stdout=subprocess.PIPE, stderr=subprocess.PIPE, text=True)

    # ------------------------------------------------------------- reading
    def checkout(self, lane: str) -> Path:
        return self.lanes_root / lane

    def origin_head(self) -> str:
        return self.git("--git-dir", str(self.origin), "rev-parse", "main").strip()

    def origin_file(self, rel: str) -> str:
        return self.git("--git-dir", str(self.origin), "show", f"main:{rel}")

    def origin_register(self) -> str:
        return self.origin_file(REGISTER)

    def w_origin_main(self) -> str:
        """W's own `origin/main`, as an offline read of W sees it."""
        return self.git("-C", str(self.w), "rev-parse", "refs/remotes/origin/main").strip()

    def w_state(self) -> tuple:
        return (self.git("-C", str(self.w), "rev-parse", "HEAD").strip(),
                self.git("-C", str(self.w), "status", "--porcelain", "--untracked-files=all"))
