# SPDX-License-Identifier: Apache-2.0
"""WHERE `--install` TAKES ITS BYTES FROM: the compatibility matrix of the triad
migration (opensoft/openRepoTools#186, T007/T008 of
`specs/004-migrate-to-triad/tasks.md`; the matrix is
`specs/004-migrate-to-triad/installer-design.md`'s "Compatibility acceptance").

Every test here builds its own GitHub out of BARE REPOSITORIES IN A TEMPORARY
DIRECTORY: a fake `gh` and a fake `curl` (one Python program, `FAKE_GITHUB`
below) answer the calls the installer makes from those repositories with
`git` itself — `commits/<ref>` is `git rev-parse`, `git/trees/<sha>` is
`git ls-tree`, `contents/<path>?ref=` and the raw URL are `git show` — so a
branch that MOVES, a tag, a commit and a ref with a slash in it behave as they
do on GitHub, and every request is written to a log a test can read back. No
real `gh` or `curl` is reachable: the `$PATH` a run gets is a farm of the real
one's executables with both names left out, and the fakes put back only where a
test asks for them. Every `$HOME` is a temporary directory.

THE TWO LAYOUTS:

* LEGACY — one repository whose root carries every payload file (today's
  `opensoft/openRepoTools`). It installs EXACTLY as before: a complete checkout
  offline, byte for byte; a remote install fetching every payload file at the
  ref it was given, by `gh` and then the raw URL, with no other host and no
  `jq`. The only new request is the one that tells the layouts apart —
  `contracts/code-pin.yaml`, answered 404 — asked by those same two
  transports.
* ADOPTED — an ASSEMBLY root whose `contracts/code-pin.yaml` pins the CODE
  leg by repository and commit, with the gitlink at the pinned path agreeing.
  The payload comes from the code repository at the pinned commit and from
  nowhere else, and the ref is resolved ONCE, so a moving branch cannot mix
  two versions. That needs api.github.com (and `jq` on the `curl` path), which
  is why it is the adopted layout's and not the legacy one's.

A test whose name carries `composed` needs THIS checkout mounted as an
assembly's code leg with the assembly's root entry point beside it; standalone
code skips it, naming why, and T015 runs it at the real assembled head.
"""

from __future__ import annotations

import hashlib
import json
import os
import re
import shutil
import signal
import stat
import subprocess
import sys
import textwrap
import time
from pathlib import Path

import pytest

from conftest import REPO, WINDOWS_SKIP

COMMAND = REPO / "openRepoTools"

pytestmark = [pytest.mark.skipif(shutil.which("bash") is None,
                                 reason="openRepoTools is a bash script"),
              WINDOWS_SKIP]

#: `--install` merges two hook entries with jq and refuses without it, and the
#: fake `gh`'s `--jq` is answered by the real jq: every test that installs
#: needs one, as `tests/test_openrepotools_command.py`'s own NEEDS_JQ says.
NEEDS_JQ = pytest.mark.skipif(shutil.which("jq") is None,
                              reason="`--install` merges two hook entries with jq")

#: THE PINNED STANDARD'S TEMPLATE BYTES — what `wip init` seeds a workspace
#: from. Without the submodule these tests SKIP with conftest's own words, which
#: is the documented skip row 14 of the matrix keeps.
UPSTREAM = REPO / "upstream" / "openRepoShape"
NEEDS_TEMPLATES = pytest.mark.skipif(
    not (UPSTREAM / "templates" / "workspace-root").is_dir(),
    reason="the pinned openRepoShape is not checked out; "
           "run `git submodule update --init upstream/openRepoShape`")

#: THE COMPOSED CONTEXT: this checkout mounted as an assembly's code leg, the
#: assembly's root entry point beside it. Read from disk, never assumed.
ASSEMBLY = REPO.parent


def composed_context() -> tuple[bool, str]:
    pin = ASSEMBLY / "contracts" / "code-pin.yaml"
    if not pin.is_file() or not (ASSEMBLY / "openRepoTools").is_file():
        return False, ("composed acceptance: needs this checkout mounted as an "
                       "assembly's code leg with the assembly's root "
                       "`openRepoTools` beside it; standalone code skips it and "
                       "T015 runs it at the real assembled head")
    path = re.search(r"^submodule_path:\s*\"?([^\"\s]+)", pin.read_text(
        encoding="utf-8"), re.MULTILINE)
    if not path or path.group(1) != REPO.name:
        return False, f"{ASSEMBLY} pins a code leg that is not this checkout"
    return True, ""


COMPOSED, COMPOSED_WHY = composed_context()
#: `OPENREPOTOOLS_COMPOSED=1` is the assembly's exact-pin job saying the run IS
#: composed acceptance (T009's convention): there, an absent context FAILS and
#: nothing skips its way in. Anywhere else, standalone code skips these.
STRICT_COMPOSED = os.environ.get("OPENREPOTOOLS_COMPOSED") == "1"
NEEDS_COMPOSED = pytest.mark.skipif(not COMPOSED and not STRICT_COMPOSED,
                                    reason=COMPOSED_WHY)


def require_composed() -> None:
    if not COMPOSED:
        pytest.fail(f"OPENREPOTOOLS_COMPOSED=1, and {COMPOSED_WHY}")


# --- the payload, read the way a consumer reads it -------------------------

def one_line_array(text: str, name: str) -> list[str]:
    """`NAME=(a b c)` on ONE line, the way workBenches' `estate-commands-start`
    `sed`-reads it out of the vendored `openRepoTools` (consumer-reads row W4):
    a list that wrapped would read as nothing there, so it is asserted here."""
    lines = [line for line in text.splitlines() if line.startswith(f"{name}=(")]
    assert len(lines) == 1, f"{name}=( is not one line: {lines}"
    line = lines[0]
    assert line.endswith(")") and line.count("(") == 1 and line.count(")") == 1, line
    return line[len(name) + 2:-1].split()


SOURCE_TEXT = COMMAND.read_text(encoding="utf-8")
INSTALLABLES = one_line_array(SOURCE_TEXT, "INSTALLABLES")
SKILLS = one_line_array(SOURCE_TEXT, "SKILLS")
COMMANDS = one_line_array(SOURCE_TEXT, "COMMANDS")
SKILL_PATHS = [f"skills/{n}/SKILL.md" for n in SKILLS]
COMMAND_PATHS = [f"commands/{n}.md" for n in COMMANDS]
#: EVERY FILE `--install` READS, derived from the three lists and nothing else.
PAYLOAD = INSTALLABLES + SKILL_PATHS + COMMAND_PATHS


def destinations(home: Path, *, bin_dir: Path | None = None,
                 profiles: Path | None = None,
                 claude: Path | None = None) -> dict[str, str]:
    """Every placed file's destination → the payload path it carries."""
    bin_dir = bin_dir or home / ".local" / "bin"
    profiles = profiles or home / ".claude-profiles"
    claude = claude or home / ".claude"
    out = {str(bin_dir / n): n for n in INSTALLABLES}
    for n, p in zip(SKILLS, SKILL_PATHS):
        out[str(profiles / "shared" / "skills" / n / "SKILL.md")] = p
        out[str(claude / "skills" / n / "SKILL.md")] = p
    for n, p in zip(COMMANDS, COMMAND_PATHS):
        out[str(profiles / "shared" / "commands" / f"{n}.md")] = p
        out[str(claude / "commands" / f"{n}.md")] = p
    return out


def variant(path: str, tag: str | None) -> bytes:
    """This checkout's bytes for `path`, MARKED with `tag` so a test can tell
    which commit an installed file came from. A comment line at the end, which
    every payload file — bash, Python, Markdown and the alias table — reads
    past."""
    data = (REPO / path).read_bytes()
    if tag is None:
        return data
    return data + f"\n# payload variant {tag}\n".encode()


def payload_files(tag: str | None, *, without: tuple[str, ...] = ()) -> dict[str, bytes]:
    return {p: variant(p, tag) for p in PAYLOAD if p not in without}


# --- repositories, built with git plumbing ---------------------------------

def git(*args: str, cwd: Path | None = None, input: bytes | None = None,
        env: dict | None = None) -> str:
    proc = subprocess.run(["git", *args], cwd=str(cwd) if cwd else None,
                          input=input, capture_output=True, check=False,
                          env={**os.environ, **(env or {})})
    if proc.returncode != 0:
        raise AssertionError(f"git {' '.join(args)} failed:\n"
                             f"{proc.stderr.decode(errors='replace')}")
    return proc.stdout.decode()


IDENTITY = {"GIT_AUTHOR_NAME": "payload tests", "GIT_AUTHOR_EMAIL": "t@example.invalid",
            "GIT_COMMITTER_NAME": "payload tests",
            "GIT_COMMITTER_EMAIL": "t@example.invalid",
            "GIT_AUTHOR_DATE": "2026-10-07T00:00:00Z",
            "GIT_COMMITTER_DATE": "2026-10-07T00:00:00Z"}


def bare(server: Path, slug: str) -> Path:
    path = server / f"{slug}.git"
    if not path.exists():
        path.parent.mkdir(parents=True, exist_ok=True)
        git("init", "-q", "--bare", "-b", "main", str(path))
    return path


def commit(repo: Path, files: dict[str, bytes], *, gitlinks: dict[str, str] | None = None,
           branch: str | None = "main", message: str = "payload tests") -> str:
    """One commit of exactly `files` (and `gitlinks`) in the bare `repo`.

    Executable bits follow this checkout: a payload command is 100755 because
    its source is. Built from the object store up, so the tests pay for no
    working tree."""
    index = repo / f"index-{os.getpid()}-{time.monotonic_ns()}"
    env = {"GIT_INDEX_FILE": str(index), **IDENTITY}
    lines = []
    for path, data in sorted(files.items()):
        oid = git("--git-dir", str(repo), "hash-object", "-w", "--stdin",
                  input=data).strip()
        source = REPO / path
        mode = "100755" if (source.is_file() and os.access(source, os.X_OK)) else "100644"
        lines.append(f"{mode} {oid}\t{path}")
    for path, oid in sorted((gitlinks or {}).items()):
        lines.append(f"160000 {oid}\t{path}")
    git("--git-dir", str(repo), "update-index", "--index-info",
        input=("\n".join(lines) + "\n").encode(), env=env)
    tree = git("--git-dir", str(repo), "write-tree", env=env).strip()
    index.unlink()
    sha = git("--git-dir", str(repo), "commit-tree", tree, "-m", message,
              env=env).strip()
    if branch:
        git("--git-dir", str(repo), "update-ref", f"refs/heads/{branch}", sha)
    return sha


def tree_digest(repo: Path, sha: str) -> str:
    """`sorted-ls-tree-r-v1`, as `contracts/code-pin.yaml` defines it."""
    out = subprocess.run(["git", "--git-dir", str(repo), "ls-tree", "-r", "-z", sha],
                         capture_output=True, check=True).stdout
    records = sorted(r for r in out.split(b"\0") if r)
    return hashlib.sha256(b"".join(r + b"\n" for r in records)).hexdigest()


#: THE PIN, in the grammar the rehearsed assembly carries (2726d3a's
#: `contracts/code-pin.yaml`), comments and quoting included.
PIN_TEXT = """\
schema_version: 1
kind: pinned_contract_manifest

# ===========================================================================
# code-pin.yaml — the CODE leg, pinned by commit and digest.
# ===========================================================================

leg_role: code
source_repository: {source}
submodule_path: {path}

commit: "{commit}"
revision_kind: commit

digest_algorithm: sha256

# WHAT IS DIGESTED, exactly. `sorted-ls-tree-r-v1`.
digest_definition: sorted-ls-tree-r-v1
digests:
  tree_sha256: "{digest}"

verify_pin: scripts/validate-pins.py
resync_runbook: "README.md#the-lockstep-invariant"
"""

PROJECT_YAML = """\
schema_version: 1
kind: project-manifest
id: openrepotools
legs:
  - role: assembly
    repository: opensoft/openRepoTools
    path: "."
  - role: code
    repository: opensoft/openRepoTools-code
    path: code
"""

#: WHAT SITS AT THE ASSEMBLY ROOT IN THESE FIXTURES where the real assembly has
#: its entry point. It is never a payload: an install that placed it would put
#: a command that exits 97 on somebody's PATH, which these tests assert never
#: happens.
ROOT_PLACEHOLDER = (b"#!/usr/bin/env bash\n"
                    b"echo 'the assembly entry point placeholder ran' >&2\nexit 97\n")


def shape_pin(sha: str) -> bytes:
    return (f"schema_version: 1\nkind: pinned_contract_manifest\n"
            f"pin_role: upstream-standard\nsource_repository: opensoft/openRepoShape\n"
            f"submodule_path: upstream/openRepoShape\n"
            f'commit: "{sha}"\nrevision_kind: commit\n').encode()


class World:
    """One fake GitHub, its repositories and its request log."""

    def __init__(self, root: Path):
        self.root = root
        self.server = root / "github"
        self.server.mkdir(parents=True, exist_ok=True)
        self.log = root / "requests.log"
        self.conf = root / "fake-github.json"
        self.state = root / "fake-github.state"
        self.faults: list[dict] = []
        self.moves: list[dict] = []
        self.write_conf()

    def write_conf(self) -> None:
        self.conf.write_text(json.dumps({
            "server": str(self.server), "log": str(self.log),
            "state": str(self.state), "faults": self.faults,
            "moves": self.moves}), encoding="utf-8")
        if self.state.exists():
            self.state.unlink()

    def repo(self, slug: str) -> Path:
        return bare(self.server, slug)

    # -- the code leg, the assembly and the single repository --------------
    def code(self, slug: str = "opensoft/openRepoTools-code", tag: str | None = "pinned",
             *, without: tuple[str, ...] = (), shape: str | None = None,
             branch: str | None = "main") -> str:
        files = payload_files(tag, without=without)
        files["contracts/openreposhape-pin.yaml"] = (
            shape_pin(shape) if shape else
            (REPO / "contracts" / "openreposhape-pin.yaml").read_bytes())
        return commit(self.repo(slug), files, branch=branch,
                      message=f"code {tag}")

    def assembly(self, code_commit: str, *, slug: str = "opensoft/openRepoTools",
                 code_slug: str = "opensoft/openRepoTools-code",
                 pin: str | None = None, gitlink: str | None = None,
                 manifest: bool = True, with_pin: bool = True,
                 extra: dict[str, bytes] | None = None,
                 root_entry: bytes = ROOT_PLACEHOLDER,
                 branch: str | None = "main") -> str:
        code_repo = self.repo(code_slug)
        if pin is None:
            pin = PIN_TEXT.format(source=code_slug, path="code", commit=code_commit,
                                  digest=tree_digest(code_repo, code_commit))
        files = {"README.md": b"# openRepoTools\n", "openRepoTools": root_entry}
        if manifest:
            files["project.yaml"] = PROJECT_YAML.encode()
        if with_pin:
            files["contracts/code-pin.yaml"] = pin.encode()
        files["contracts/shape-pin.yaml"] = b"schema_version: 1\n"
        files.update(extra or {})
        return commit(self.repo(slug), files,
                      gitlinks={"code": gitlink or code_commit}, branch=branch,
                      message="assembly")

    def single(self, slug: str = "opensoft/openRepoTools", tag: str | None = "legacy",
               *, branch: str | None = "main", without: tuple[str, ...] = (),
               shape: str | None = None) -> str:
        """Today's layout: every payload file at the root, the dependency pin
        in `contracts/`, and no adoption manifest."""
        files = payload_files(tag, without=without)
        files["contracts/openreposhape-pin.yaml"] = (
            shape_pin(shape) if shape else
            (REPO / "contracts" / "openreposhape-pin.yaml").read_bytes())
        files["README.md"] = b"# openRepoTools\n"
        files["AGENTS.md"] = b"# Working in openRepoTools\n"
        return commit(self.repo(slug), files, branch=branch,
                      message=f"single {tag}")

    def ref(self, slug: str, ref: str, sha: str) -> None:
        git("--git-dir", str(self.repo(slug)), "update-ref", ref, sha)

    def tree_of(self, slug: str, sha: str, path: str) -> str:
        return git("--git-dir", str(self.repo(slug)), "rev-parse",
                   f"{sha}:{path}").strip()

    # -- the request log ---------------------------------------------------
    def requests(self) -> list[dict]:
        if not self.log.exists():
            return []
        return [json.loads(line) for line in
                self.log.read_text(encoding="utf-8").splitlines() if line]

    def payload_requests(self) -> list[dict]:
        """Every request for a payload FILE (not a listing, not a commit)."""
        out = []
        for r in self.requests():
            target = r["target"]
            for path in PAYLOAD:
                if (f"/contents/{path}?" in target
                        or target.endswith(f"/{path}") and "raw.githubusercontent" in target):
                    out.append({**r, "path": path})
        return out


#: A fake GitHub in one program: `gh api`, `gh repo …` and `curl`, answered from
#: bare repositories with git. Faults and branch moves come from its JSON
#: configuration, and every request is logged before it is answered.
FAKE_GITHUB = r'''
import json, os, re, subprocess, sys, urllib.parse

conf_path, tool, args = sys.argv[1], sys.argv[2], sys.argv[3:]
with open(conf_path) as fh:
    conf = json.load(fh)
server = conf["server"]


def repo_dir(slug):
    return os.path.join(server, slug + ".git")


def git(repo, *a, data=None):
    return subprocess.run(["git", "--git-dir", repo, *a], capture_output=True,
                          input=data)


def resolve(repo, ref):
    p = git(repo, "rev-parse", "--verify", "--quiet", ref + "^{commit}")
    return p.stdout.decode().strip() if p.returncode == 0 else ""


def log(entry):
    with open(conf["log"], "a") as fh:
        fh.write(json.dumps(entry) + "\n")


def tick():
    try:
        with open(conf["state"]) as fh:
            state = json.load(fh)
    except (OSError, ValueError):
        state = {"count": 0, "applied": []}
    for i, move in enumerate(conf.get("moves", [])):
        if i not in state["applied"] and state["count"] >= move["after"]:
            git(repo_dir(move["repo"]), "update-ref", move["ref"], move["to"])
            state["applied"].append(i)
    state["count"] += 1
    with open(conf["state"], "w") as fh:
        json.dump(state, fh)


def api(path, query, accept):
    m = re.match(r"repos/([^/]+)/([^/]+)/(.*)$", path)
    if not m:
        return 404, json.dumps({"message": "Not Found"}).encode()
    owner, name, rest = m.groups()
    repo = repo_dir(owner + "/" + name)
    if not os.path.isdir(repo):
        return 404, json.dumps({"message": "Not Found"}).encode()
    if rest.startswith("commits/"):
        ref = urllib.parse.unquote(rest[len("commits/"):])
        sha = resolve(repo, ref)
        if not sha:
            return 422, json.dumps({"message": "No commit found for SHA: " + ref,
                                    "status": "422"}).encode()
        if accept == "application/vnd.github.sha":
            return 200, sha.encode()
        return 200, json.dumps({"sha": sha}).encode()
    if rest.startswith("git/trees/"):
        ref = rest[len("git/trees/"):]
        kind = git(repo, "cat-file", "-t", ref).stdout.decode().strip()
        if kind == "commit":
            ref = git(repo, "rev-parse", ref + "^{tree}").stdout.decode().strip()
        elif kind != "tree":
            return 404, json.dumps({"message": "Not Found"}).encode()
        listing = git(repo, "ls-tree", "-z", ref).stdout.decode()
        tree = []
        for record in filter(None, listing.split("\0")):
            meta, path_ = record.split("\t", 1)
            mode, typ, sha = meta.split()
            tree.append({"path": path_, "mode": mode, "type": typ, "sha": sha})
        return 200, json.dumps({"sha": ref, "tree": tree, "truncated": False}).encode()
    if rest.startswith("contents/"):
        path_ = urllib.parse.unquote(rest[len("contents/"):])
        ref = query.get("ref", ["main"])[0]
        return blob(repo, ref, path_)
    return 404, json.dumps({"message": "Not Found"}).encode()


def blob(repo, ref, path_):
    sha = resolve(repo, ref)
    if not sha:
        return 404, json.dumps({"message": "No commit found for the ref " + ref}).encode()
    obj = sha + ":" + path_
    if git(repo, "cat-file", "-t", obj).stdout.decode().strip() != "blob":
        return 404, json.dumps({"message": "Not Found"}).encode()
    return 200, git(repo, "cat-file", "blob", obj).stdout


def raw(url_path):
    parts = url_path.split("/")
    if len(parts) < 4:
        return 404, b"404: Not Found"
    repo = repo_dir(parts[0] + "/" + parts[1])
    if not os.path.isdir(repo):
        return 404, b"404: Not Found"
    rest = parts[2:]
    for k in range(1, len(rest)):
        ref, path_ = "/".join(rest[:k]), "/".join(rest[k:])
        if resolve(repo, ref):
            status, body = blob(repo, ref, path_)
            return (status, body) if status == 200 else (404, b"404: Not Found")
    return 404, b"404: Not Found"


def fault_for(target):
    for f in conf.get("faults", []):
        if f.get("tool", "any") in ("any", tool) and re.search(f["match"], target):
            return f
    return None


MESSAGES = {401: "Bad credentials", 403: "API rate limit exceeded for 203.0.113.7.",
            404: "Not Found", 500: "Server Error"}


def gh_main():
    if args[:1] == ["repo"]:
        return gh_repo(args[1:])
    if args[:1] != ["api"]:
        sys.stderr.write("fake gh: unexpected call: %s\n" % " ".join(args))
        return 1
    endpoint, accept, jq, method = None, "", None, "GET"
    i = 1
    while i < len(args):
        a = args[i]
        if a in ("-H", "--header"):
            h = args[i + 1]
            if h.lower().startswith("accept:"):
                accept = h.split(":", 1)[1].strip()
            i += 2
        elif a in ("--jq", "-q"):
            jq = args[i + 1]
            i += 2
        elif a in ("--method", "-X"):
            method = args[i + 1]
            i += 2
        elif a in ("--paginate", "--silent"):
            i += 1
        elif a.startswith("-"):
            i += 2
        elif endpoint is None:
            endpoint = a
            i += 1
        else:
            i += 1
    endpoint = (endpoint or "").lstrip("/")
    log({"tool": "gh", "target": endpoint, "accept": accept})
    tick()
    if method == "PUT":
        return 0
    if endpoint == "user":
        sys.stdout.write("brettheap\n")
        return 0
    f = fault_for(endpoint)
    if f and f["kind"] == "transport":
        sys.stderr.write("error connecting to api.github.com\n"
                         "check your internet connection or https://githubstatus.com\n")
        return 1
    if f and f["kind"] == "status":
        status = f["status"]
        msg = MESSAGES.get(status, "Error")
        sys.stdout.write(json.dumps({"message": msg}))
        sys.stderr.write("gh: %s (HTTP %d)\n" % (msg, status))
        return 1
    path, _, q = endpoint.partition("?")
    status, body = api(path, urllib.parse.parse_qs(q), accept)
    if f and f["kind"] == "garbage":
        status, body = 200, b"<html>a captive portal answered this</html>"
    if status >= 400:
        sys.stdout.write(body.decode(errors="replace"))
        msg = json.loads(body).get("message", "Error")
        sys.stderr.write("gh: %s (HTTP %d)\n" % (msg, status))
        return 1
    if jq is not None:
        p = subprocess.run(["jq", "-r", jq], input=body, capture_output=True)
        if p.returncode != 0:
            sys.stderr.write("failed to parse jq expression or JSON: "
                             + p.stderr.decode(errors="replace"))
            return 1
        sys.stdout.buffer.write(p.stdout)
        return 0
    sys.stdout.buffer.write(body)
    return 0


def gh_repo(rest):
    log({"tool": "gh", "target": "repo " + " ".join(rest), "accept": ""})
    verb, slug = rest[0], rest[1]
    repo = repo_dir(slug)
    if verb == "view":
        return 0 if os.path.isdir(repo) else 1
    if verb == "create":
        os.makedirs(os.path.dirname(repo), exist_ok=True)
        subprocess.run(["git", "init", "-q", "--bare", "-b", "main", repo], check=True)
        return 0
    if verb == "clone":
        p = subprocess.run(["git", "clone", "-q", repo, rest[2]])
        return p.returncode
    return 1


def curl_main():
    url, accept, out, fmt, fail = None, "", None, None, False
    i = 0
    while i < len(args):
        a = args[i]
        if a in ("-H", "--header"):
            h = args[i + 1]
            if h.lower().startswith("accept:"):
                accept = h.split(":", 1)[1].strip()
            i += 2
        elif a in ("-o", "--output"):
            out = args[i + 1]
            i += 2
        elif a in ("-w", "--write-out"):
            fmt = args[i + 1]
            i += 2
        elif a == "--fail" or (a.startswith("-") and not a.startswith("--") and "f" in a):
            fail = True
            i += 1
        elif a.startswith("-"):
            i += 1
        else:
            url = a
            i += 1
    log({"tool": "curl", "target": url or "", "accept": accept})
    tick()
    f = fault_for(url or "")
    if f and f["kind"] == "transport":
        sys.stderr.write("curl: (6) Could not resolve host: %s\n"
                         % urllib.parse.urlsplit(url).netloc)
        return 6
    parts = urllib.parse.urlsplit(url or "")
    if f and f["kind"] == "status":
        status, body = f["status"], json.dumps({"message": MESSAGES.get(f["status"], "Error")}).encode()
    elif parts.netloc == "api.github.com":
        status, body = api(urllib.parse.unquote(parts.path.lstrip("/")),
                           urllib.parse.parse_qs(parts.query), accept)
    elif parts.netloc == "raw.githubusercontent.com":
        status, body = raw(parts.path.lstrip("/"))
    else:
        sys.stderr.write("curl: (6) Could not resolve host: %s\n" % parts.netloc)
        return 6
    if f and f["kind"] == "garbage":
        status, body = 200, b"<html>a captive portal answered this</html>"
    if status >= 400 and fail:
        sys.stderr.write("curl: (22) The requested URL returned error: %d\n" % status)
        return 22
    if out:
        with open(out, "wb") as fh:
            fh.write(body)
    else:
        sys.stdout.buffer.write(body)
    if fmt:
        sys.stdout.write(fmt.replace("%{http_code}", str(status)))
    return 0


sys.exit(gh_main() if tool == "gh" else curl_main())
'''


def path_farm(root: Path, leave_out: tuple[str, ...]) -> Path:
    """A directory of links to every executable on the real `$PATH` except
    `leave_out`: a machine on which those names do not EXIST."""
    farm = root / "path-farm"
    if farm.exists():
        return farm
    farm.mkdir()
    for directory in os.environ.get("PATH", "").split(os.pathsep):
        try:
            entries = sorted(os.listdir(directory))
        except OSError:
            continue
        for entry in entries:
            source = os.path.join(directory, entry)
            link = farm / entry
            if entry in leave_out or link.is_symlink() or not (
                    os.path.isfile(source) and os.access(source, os.X_OK)):
                continue
            link.symlink_to(source)
    return farm


def network(world: World, *, gh: bool = True, curl: bool = True,
            extra_shims: dict[str, str] | None = None) -> str:
    """The `$PATH` a run gets: the fakes that are switched on, first, then a
    farm with no real `gh` and no real `curl` in it at all."""
    fake = world.root / ("fake-" + ("g" if gh else "") + ("c" if curl else "")
                         + ("x" if extra_shims else ""))
    fake.mkdir(exist_ok=True)
    program = world.root / "fake_github.py"
    program.write_text(FAKE_GITHUB, encoding="utf-8")
    for name, wanted in (("gh", gh), ("curl", curl)):
        if wanted:
            shim = fake / name
            shim.write_text(f"#!/bin/sh\nexec '{sys.executable}' -I '{program}' "
                            f"'{world.conf}' {name} \"$@\"\n", encoding="utf-8")
            shim.chmod(0o755)
    for name, body in (extra_shims or {}).items():
        (fake / name).write_text(body, encoding="utf-8")
        (fake / name).chmod(0o755)
    farm = path_farm(world.root, ("gh", "curl"))
    return f"{fake}{os.pathsep}{farm}"


def env_for(home: Path, path: str, **extra: str) -> dict:
    environ = dict(os.environ)
    for name in list(environ):
        if name.startswith("OPENREPOTOOLS_") or name in (
                "XDG_DATA_HOME", "CLAUDE_PROFILES_HOME", "CLAUDE_USER_DIR",
                "AGENT_PROTOCOL_ROOT", "PROJECTS_DIR", "GH_TOKEN", "GITHUB_TOKEN"):
            environ.pop(name)
    environ.update({"HOME": str(home), "PATH": path,
                    "CLAUDE_PROFILES_HOME": str(home / ".claude-profiles"),
                    "CLAUDE_USER_DIR": str(home / ".claude"),
                    "AGENT_PROTOCOL_ROOT": str(home / ".agents"),
                    "XDG_CACHE_HOME": str(home / ".cache"), **IDENTITY})
    environ.update(extra)
    return environ


def run_stdin(world: World, home: Path, path: str, *args: str,
              script: Path = COMMAND, **extra: str) -> subprocess.CompletedProcess:
    """The documented one-liner's shape: the implementation on stdin, from a
    directory holding nothing named `bash`, so it runs as no file at all."""
    cwd = world.root / "cwd"
    cwd.mkdir(exist_ok=True)
    return subprocess.run(["bash", "-s", "--", *args], input=script.read_text(encoding="utf-8"),
                          capture_output=True, text=True, check=False, cwd=str(cwd),
                          env=env_for(home, path, **extra))


def run_file(script: Path, home: Path, path: str, *args: str,
             **extra: str) -> subprocess.CompletedProcess:
    return subprocess.run(["bash", str(script), *args], input="", capture_output=True,
                          text=True, check=False, cwd=str(home.parent),
                          env=env_for(home, path, **extra))


def snapshot(root: Path) -> dict[str, bytes]:
    if not root.exists():
        return {}
    return {str(p.relative_to(root)): (p.read_bytes() if p.is_file() else b"<dir>")
            for p in sorted(root.rglob("*"))}


def assert_installed(home: Path, tag: str | None, result, **dirs) -> None:
    for dest, path in destinations(home, **dirs).items():
        target = Path(dest)
        assert target.is_file(), f"{dest} not placed\n{result.stdout}\n{result.stderr}"
        assert target.read_bytes() == variant(path, tag), (
            f"{dest} does not hold the {tag!r} bytes of {path}\n{result.stdout}")


def assert_nothing_placed(home: Path, result) -> None:
    assert result.returncode == 2, result.stdout + result.stderr
    assert "REFUSED" in result.stderr, result.stderr
    for dest in destinations(home):
        assert not Path(dest).exists(), f"{dest} was placed by a refused run"


def local_tree(root: Path, tag: str | None) -> Path:
    """A complete directory of payload files, the way a checkout or a vendored
    tree holds them, with the executable bits the repository gives them."""
    root.mkdir(parents=True, exist_ok=True)
    for path, data in payload_files(tag).items():
        target = root / path
        target.parent.mkdir(parents=True, exist_ok=True)
        target.write_bytes(data)
        if os.access(REPO / path, os.X_OK):
            target.chmod(0o755)
    return root


def install_prior(world: World, home: Path, tag: str = "prior") -> None:
    """An earlier, complete install, from a local tree, offline."""
    tree = local_tree(world.root / f"tree-{tag}", tag)
    result = run_file(tree / "openRepoTools", home, network(world), "--install")
    assert result.returncode == 0, result.stdout + result.stderr


# --- a local assembly checkout ----------------------------------------------

def local_assembly(world: World, *, tag: str = "local") -> tuple[Path, Path, str]:
    """An assembly CHECKOUT with its code leg mounted at `code/`: the pin, the
    manifest, and the gitlink in the assembly's index, all naming the code
    checkout's own HEAD."""
    assembly = world.root / "checkout"
    code = assembly / "code"
    local_tree(code, tag)
    (code / "contracts").mkdir(exist_ok=True)
    shutil.copy2(REPO / "contracts" / "openreposhape-pin.yaml",
                 code / "contracts" / "openreposhape-pin.yaml")
    git("init", "-q", "-b", "main", cwd=code)
    git("add", "-A", cwd=code)
    git("commit", "-q", "-m", "code", cwd=code, env=IDENTITY)
    head = git("rev-parse", "HEAD", cwd=code).strip()
    git("init", "-q", "-b", "main", cwd=assembly)
    (assembly / "contracts").mkdir()
    digest = tree_digest(code / ".git", head)
    (assembly / "contracts" / "code-pin.yaml").write_text(PIN_TEXT.format(
        source="opensoft/openRepoTools-code", path="code", commit=head,
        digest=digest), encoding="utf-8")
    (assembly / "project.yaml").write_text(PROJECT_YAML, encoding="utf-8")
    (assembly / "openRepoTools").write_bytes(ROOT_PLACEHOLDER)
    git("add", "contracts", "project.yaml", "openRepoTools", cwd=assembly)
    git("update-index", "--add", "--cacheinfo", f"160000,{head},code", cwd=assembly)
    git("commit", "-q", "-m", "assembly", cwd=assembly, env=IDENTITY)
    return assembly, code, head


# =========================================================================
# ROW 1 — the existing raw/gh one-liners
# =========================================================================

@NEEDS_JQ
def test_r01_the_one_liner_against_a_single_repository_installs_as_before(tmp_path):
    """Today's layout through today's one-liner: every name, every destination,
    and no line a person has not seen before — the output of a fetching
    install is the output of a local one."""
    world = World(tmp_path)
    world.single(tag=None)
    home = tmp_path / "home"
    result = run_stdin(world, home, network(world), "--install")
    assert result.returncode == 0, result.stdout + result.stderr
    assert_installed(home, None, result)
    local_home = tmp_path / "local-home"
    local = run_file(local_tree(tmp_path / "tree", None) / "openRepoTools", local_home,
                     network(world), "--install")
    assert local.returncode == 0, local.stderr
    assert (result.stdout.replace(str(home), "<home>")
            == local.stdout.replace(str(local_home), "<home>"))


@NEEDS_JQ
@pytest.mark.parametrize("transport", ["gh", "curl"])
def test_r01_the_one_liner_against_an_adopted_assembly_installs_the_pinned_code(
        tmp_path, transport):
    """The default `opensoft/openRepoTools` is the ASSEMBLY after the split:
    the implementation and its payload are the code leg's, at the commit the
    assembly pins, by `gh` or — where there is none — by `curl` and `jq`."""
    world = World(tmp_path)
    code = world.code()
    world.assembly(code)
    home = tmp_path / "home"
    result = run_stdin(world, home, network(world, gh=transport == "gh"), "--install")
    assert result.returncode == 0, result.stdout + result.stderr
    assert_installed(home, "pinned", result)
    assert (f"openRepoTools: source: opensoft/openRepoTools at main"
            in result.stdout), result.stdout
    assert f"opensoft/openRepoTools-code at {code}" in result.stdout


#: Every request a single repository's install may make: a file at the ref it
#: was given, by `gh api …/contents` or by the raw URL. Nothing else.
def single_layout_requests_only(world: World, ref: str = "main") -> None:
    for r in world.requests():
        target = r["target"]
        if r["tool"] == "gh":
            assert re.fullmatch(rf"repos/opensoft/openRepoTools/contents/[^?]+\?ref={re.escape(ref)}",
                                target), f"a single repository's install asked {target}"
        else:
            assert target.startswith(
                f"https://raw.githubusercontent.com/opensoft/openRepoTools/{ref}/"), (
                f"a single repository's install asked {target}")


@NEEDS_JQ
@pytest.mark.parametrize("api_fault", ["transport", "rate-403"])
def test_r01_a_single_repository_by_curl_never_needs_api_github_com(tmp_path, api_fault):
    """Today's layout on a machine with no `gh`: the one-liner always needed
    raw.githubusercontent.com and nothing else, so an api.github.com that is
    unreachable or rate-limited (60 an hour, unauthenticated, per address)
    changes nothing. #191's review, F1: the single repository keeps its network
    needs byte for byte."""
    world = World(tmp_path)
    world.single(tag="single")
    fault = ({"kind": "transport"} if api_fault == "transport"
             else {"kind": "status", "status": 403})
    world.faults = [{"tool": "curl", "match": r"^https://api\.github\.com/", **fault}]
    world.write_conf()
    home = tmp_path / "home"
    result = run_stdin(world, home, network(world, gh=False), "--install")
    assert result.returncode == 0, result.stdout + result.stderr
    assert_installed(home, "single", result)
    single_layout_requests_only(world)
    assert len(world.payload_requests()) == len(PAYLOAD)


def test_r01_a_single_repository_without_jq_fetches_then_names_jq_as_it_always_did(tmp_path):
    """No `gh` and no `jq`: today's layout fetches every payload file by the raw
    URL and THEN refuses naming `jq` for the hook merge, placing nothing — the
    order and the words it always had (#191's review, F1)."""
    world = World(tmp_path)
    world.single(tag="single")
    fakes = network(world, gh=False).split(os.pathsep)[0]
    (world.root / "farm-without-jq").mkdir()
    farm = path_farm(world.root / "farm-without-jq", ("gh", "curl", "jq"))
    home = tmp_path / "home"
    result = run_stdin(world, home, f"{fakes}{os.pathsep}{farm}", "--install")
    assert_nothing_placed(home, result)
    assert result.stderr.startswith("\nREFUSED: `--install` needs `jq` to merge its TWO hook entries"), result.stderr
    single_layout_requests_only(world)
    assert len(world.payload_requests()) == len(PAYLOAD)


@NEEDS_JQ
def test_r01_a_single_repository_by_gh_asks_for_files_and_nothing_else(tmp_path):
    """With `gh`: every request is `contents/<file>?ref=<the ref given>` — no
    `commits/`, no `git/trees/` — and the only file asked for that is not
    payload is, at most, the one that tells the layouts apart."""
    world = World(tmp_path)
    world.single(tag="single")
    home = tmp_path / "home"
    result = run_stdin(world, home, network(world), "--install")
    assert result.returncode == 0, result.stdout + result.stderr
    assert_installed(home, "single", result)
    single_layout_requests_only(world)
    others = {r["target"] for r in world.requests()} - {
        r["target"] for r in world.payload_requests()}
    assert others <= {"repos/opensoft/openRepoTools/contents/contracts/code-pin.yaml?ref=main"}, others
    assert len(world.payload_requests()) == len(PAYLOAD)


@NEEDS_COMPOSED
@NEEDS_JQ
@pytest.mark.parametrize("line", ["openRepoShape", "gh"])
def test_r01_composed_the_documented_one_liners_resolve_through_the_root_entry_point(
        tmp_path, line):
    """openRepoShape's own `--install` pointer (openRepoShape:280 at 7f84ca4)
    and README's `gh api` line, BYTE FOR BYTE, against an assembly whose root
    carries the real entry point: the root resolves `main` ONCE, reads the code
    pin there and hands every argument to the pinned implementation, which
    places the pinned payload."""
    require_composed()
    world = World(tmp_path)
    code = world.code()
    world.assembly(code, root_entry=(ASSEMBLY / "openRepoTools").read_bytes())
    home = tmp_path / "home"
    pipeline = {
        "openRepoShape": "curl -fsSL https://raw.githubusercontent.com/opensoft/"
                         "openRepoTools/main/openRepoTools | bash -s -- --install",
        "gh": "gh api repos/opensoft/openRepoTools/contents/openRepoTools "
              "-H 'Accept: application/vnd.github.raw' | bash -s -- --install",
    }[line]
    cwd = tmp_path / "cwd"
    cwd.mkdir()
    result = subprocess.run(["bash", "-c", "set -o pipefail; " + pipeline],
                            capture_output=True, text=True, check=False, cwd=str(cwd),
                            env=env_for(home, network(world)))
    assert result.returncode == 0, result.stdout + result.stderr
    assert_installed(home, "pinned", result)
    resolutions = [r for r in world.requests()
                   if r["target"].startswith("repos/opensoft/openRepoTools/commits/")
                   or "/repos/opensoft/openRepoTools/commits/" in r["target"]]
    assert [r["target"].rsplit("/", 1)[1] for r in resolutions].count("main") == 1, resolutions


@NEEDS_COMPOSED
@NEEDS_JQ
def test_r01_composed_the_root_entry_point_delegates_locally(tmp_path):
    """`./openRepoTools` at an assembly checkout IS the pinned implementation
    for every argument: the same help, the same refusal and exit status, the
    same install."""
    require_composed()
    world = World(tmp_path)
    home = tmp_path / "home"
    root = ASSEMBLY / "openRepoTools"
    path = network(world)
    for args in (("--help",), ("--version",), ("park",)):
        mine = run_file(root, home, path, *args)
        theirs = run_file(COMMAND, home, path, *args)
        assert (mine.returncode, mine.stdout, mine.stderr) == \
            (theirs.returncode, theirs.stdout, theirs.stderr), args
    result = run_file(root, home, path, "--install")
    assert result.returncode == 0, result.stdout + result.stderr
    assert_installed(home, None, result)
    assert "nothing fetched" in result.stdout
    assert world.requests() == []


@NEEDS_COMPOSED
@NEEDS_JQ
def test_r01_composed_a_signal_reaches_the_implementation_and_its_temporaries_go(tmp_path):
    """The root EXECs the implementation, so a TERM sent to the pid the person
    started is a TERM to the installer itself, whose own EXIT trap removes its
    temporary directory."""
    require_composed()
    world = World(tmp_path)
    home = tmp_path / "home"
    gate = tmp_path / "gate"
    real_cp = shutil.which("cp")
    slow_cp = (f"#!/bin/sh\n: > '{gate}'\n"
               f"while [ -e '{gate}' ]; do sleep 0.1; done\nexec '{real_cp}' \"$@\"\n")
    tmp = tmp_path / "t"
    tmp.mkdir()
    proc = subprocess.Popen(["bash", str(ASSEMBLY / "openRepoTools"), "--install"],
                            stdout=subprocess.PIPE, stderr=subprocess.PIPE,
                            env=env_for(home, network(world, extra_shims={"cp": slow_cp}),
                                        TMPDIR=str(tmp)))
    for _ in range(300):
        if gate.exists():
            break
        time.sleep(0.05)
    assert gate.exists(), "the install never reached its first copy"
    proc.send_signal(signal.SIGTERM)
    try:
        proc.wait(timeout=20)
    finally:
        gate.unlink()
    assert proc.returncode in (-signal.SIGTERM, 128 + signal.SIGTERM), proc.returncode
    assert list(tmp.iterdir()) == [], "the installer's temporary directory survived"


# =========================================================================
# ROW 2 — offline local single repository / adopted checkout
# =========================================================================

@NEEDS_JQ
def test_r02_a_complete_single_repository_tree_installs_offline_byte_for_byte(tmp_path):
    """workBenches runs `--install` from its vendored tree with a SENTINEL
    `$OPENREPOTOOLS_REPO`/`$OPENREPOTOOLS_REF` so that only sibling copies can
    succeed (consumer-reads W5). A complete tree is copied, nothing is asked of
    any network, and the output is today's to the line."""
    world = World(tmp_path)
    tree = local_tree(tmp_path / "vendored", None)
    home = tmp_path / "home"
    result = run_file(tree / "openRepoTools", home, network(world), "--install",
                      OPENREPOTOOLS_REPO="pinned-by-workBenches-no-fetch",
                      OPENREPOTOOLS_REF="pinned-by-workBenches-no-fetch")
    assert result.returncode == 0, result.stdout + result.stderr
    assert_installed(home, None, result)
    assert world.requests() == []
    assert "source:" not in result.stdout


@NEEDS_JQ
@pytest.mark.parametrize("pin", ["valid", "crlf"])
def test_r02_a_complete_tree_inside_another_projects_assembly_installs_as_before(tmp_path, pin):
    """workBenches vendors a complete tree deep inside whatever holds it. A
    `contracts/code-pin.yaml` above that tree which does not mount it as a code
    leg — in the two layouts the design names, `<root>/<submodule_path>` and
    `<root>/worktrees/<NNN>/<submodule_path>` — is another project's: it is not
    read, and the sentinel run is today's to the line (#191's review, note 7)."""
    world = World(tmp_path)
    triad = tmp_path / "someTriad"
    (triad / "contracts").mkdir(parents=True)
    text = PIN_TEXT.format(source="opensoft/someTriad-code", path="code", commit="a" * 40,
                           digest="b" * 64)
    (triad / "contracts" / "code-pin.yaml").write_bytes(
        (text if pin == "valid" else text.replace("\n", "\r\n")).encode())
    tree = local_tree(triad / "code" / "devBenches" / "base-image" / "files" / "openrepotools",
                      None)
    sentinel = {"OPENREPOTOOLS_REPO": "pinned-by-workBenches-no-fetch",
                "OPENREPOTOOLS_REF": "pinned-by-workBenches-no-fetch"}
    home = tmp_path / "home"
    result = run_file(tree / "openRepoTools", home, network(world), "--install", **sentinel)
    assert result.returncode == 0, result.stdout + result.stderr
    assert_installed(home, None, result)
    assert world.requests() == []
    plain_home = tmp_path / "plain-home"
    plain = run_file(local_tree(tmp_path / "plain", None) / "openRepoTools", plain_home,
                     network(world), "--install", **sentinel)
    assert plain.returncode == 0, plain.stderr
    assert (result.stdout.replace(str(home), "<home>")
            == plain.stdout.replace(str(plain_home), "<home>")), result.stdout


@NEEDS_JQ
def test_r02_an_adopted_checkout_installs_its_pinned_code_offline(tmp_path):
    """Run from the code leg mounted in an assembly checkout: the pin and the
    gitlink agree, every payload file is the pinned commit's bytes, and they
    are copied with no network at all — and the run says which commit that
    was."""
    world = World(tmp_path)
    assembly, code, head = local_assembly(world)
    home = tmp_path / "home"
    result = run_file(code / "openRepoTools", home, network(world), "--install")
    assert result.returncode == 0, result.stdout + result.stderr
    assert_installed(home, "local", result)
    assert world.requests() == []
    assert (f"openRepoTools: source: the code mounted at {assembly}/code, "
            f"opensoft/openRepoTools-code at {head}") in result.stdout, result.stdout
    assert "nothing fetched" in result.stdout


@NEEDS_JQ
def test_r02_an_adopted_checkout_whose_pin_comments_its_path_is_still_its_assembly(tmp_path):
    """A pin `pin_parse` accepts — `submodule_path: code  # the mounted leg` —
    is recognised as this checkout's assembly, so the pin, the gitlink and the
    bytes are all checked, rather than the tree being copied as a plain
    complete tree with none of them checked (#191, Copilot's first round)."""
    world = World(tmp_path)
    assembly, code, head = local_assembly(world)
    pin = assembly / "contracts" / "code-pin.yaml"
    text = pin.read_text(encoding="utf-8")
    assert "submodule_path: code\n" in text
    pin.write_text(text.replace("submodule_path: code\n",
                                "submodule_path: code  # the mounted leg\n"), encoding="utf-8")
    home = tmp_path / "home"
    result = run_file(code / "openRepoTools", home, network(world), "--install")
    assert result.returncode == 0, result.stdout + result.stderr
    assert_installed(home, "local", result)
    assert world.requests() == []
    assert (f"openRepoTools: source: the code mounted at {assembly}/code, "
            f"opensoft/openRepoTools-code at {head}") in result.stdout, result.stdout


# =========================================================================
# ROW 3 — an explicit local code feature
# =========================================================================

@NEEDS_JQ
def test_r03_an_explicit_code_feature_checkout_installs_its_own_bytes_and_names_them(tmp_path):
    """A paired feature worktree, `<assembly>/worktrees/<NNN>/code`, run by
    its own `openRepoTools`: ITS bytes — committed and uncommitted — are what
    is placed, and the run names that checkout and its commit and says it is
    not the code the assembly pins."""
    world = World(tmp_path)
    assembly, code, pinned = local_assembly(world)
    feature = assembly / "worktrees" / "001-x" / "code"
    git("clone", "-q", str(code), str(feature))
    (feature / "park").write_bytes(variant("park", "feature-committed"))
    git("commit", "-q", "-am", "feature", cwd=feature, env=IDENTITY)
    head = git("rev-parse", "HEAD", cwd=feature).strip()
    (feature / "status").write_bytes(variant("status", "feature-uncommitted"))
    home = tmp_path / "home"
    result = run_file(feature / "openRepoTools", home, network(world), "--install")
    assert result.returncode == 0, result.stdout + result.stderr
    bin_dir = home / ".local" / "bin"
    assert (bin_dir / "park").read_bytes() == variant("park", "feature-committed")
    assert (bin_dir / "status").read_bytes() == variant("status", "feature-uncommitted")
    assert world.requests() == []
    assert f"the code checkout {feature} at {head} with uncommitted changes" \
        in result.stdout, result.stdout
    assert f"NOT the code {assembly} pins" in result.stdout
    assert pinned in result.stdout


@NEEDS_JQ
def test_r03_an_incomplete_code_feature_checkout_is_refused_not_completed_from_elsewhere(tmp_path):
    """A feature checkout missing a payload file is not completed from any
    remote: its own bytes or none."""
    world = World(tmp_path)
    world.code()
    world.assembly(world.code(tag="remote"))
    assembly, code, _ = local_assembly(world)
    feature = assembly / "worktrees" / "002-y" / "code"
    git("clone", "-q", str(code), str(feature))
    (feature / "lanes-index").unlink()
    home = tmp_path / "home"
    result = run_file(feature / "openRepoTools", home, network(world), "--install")
    assert_nothing_placed(home, result)
    assert "lanes-index" in result.stderr
    assert world.requests() == []


# =========================================================================
# ROW 4 — installed reinstallation and skill-only operation
# =========================================================================

@NEEDS_JQ
def test_r04_an_installed_copy_reinstalls_from_the_adopted_source_without_any_checkout(tmp_path):
    """The INSTALLED `openRepoTools` has its seventeen siblings beside it and
    no skills: that is an incomplete local set, and on an adopted source it is
    never topped up with pinned skills. Every payload file comes from the code
    the assembly pins NOW, and the run says the siblings were not used."""
    world = World(tmp_path)
    home = tmp_path / "home"
    install_prior(world, home, "prior")
    code = world.code(tag="pinned-now")
    world.assembly(code)
    result = run_file(home / ".local" / "bin" / "openRepoTools", home, network(world),
                      "--install")
    assert result.returncode == 0, result.stdout + result.stderr
    assert_installed(home, "pinned-now", result)
    assert "are not used" in result.stdout, result.stdout


@NEEDS_JQ
def test_r04_an_installed_copy_on_a_single_repository_keeps_the_sibling_rule(tmp_path):
    """Today's promise, unchanged on today's layout: the commands beside the
    installed copy are copied, and only the skills and command files, which are
    not beside it, are fetched."""
    world = World(tmp_path)
    home = tmp_path / "home"
    install_prior(world, home, "prior")
    world.single(tag="remote")
    result = run_file(home / ".local" / "bin" / "openRepoTools", home, network(world),
                      "--install")
    assert result.returncode == 0, result.stdout + result.stderr
    for dest, path in destinations(home).items():
        want = "prior" if path in INSTALLABLES else "remote"
        assert Path(dest).read_bytes() == variant(path, want), dest
    assert "source:" not in result.stdout


# =========================================================================
# ROW 5 — single-repository override / adopted fork
# =========================================================================

@NEEDS_JQ
def test_r05_a_single_repository_fork_named_by_the_override_installs_as_before(tmp_path):
    world = World(tmp_path)
    world.single("someone/fork", tag="fork")
    home = tmp_path / "home"
    result = run_stdin(world, home, network(world), "--install",
                       OPENREPOTOOLS_REPO="someone/fork")
    assert result.returncode == 0, result.stdout + result.stderr
    assert_installed(home, "fork", result)


@NEEDS_JQ
def test_r05_an_adopted_fork_follows_its_own_pin_not_a_guessed_code_name(tmp_path):
    """A fork of the assembly whose pin names `forker/tools-implementation`:
    that repository is the payload, and neither `forker/openRepoTools-code`
    (the guess an appended `-code` makes) nor the upstream code leg is asked
    for anything."""
    world = World(tmp_path)
    world.code("forker/openRepoTools-code", tag="guessed")
    world.code("opensoft/openRepoTools-code", tag="upstream")
    code = world.code("forker/tools-implementation", tag="fork-pinned")
    world.assembly(code, slug="forker/openRepoTools",
                   code_slug="forker/tools-implementation")
    home = tmp_path / "home"
    result = run_stdin(world, home, network(world), "--install",
                       OPENREPOTOOLS_REPO="forker/openRepoTools")
    assert result.returncode == 0, result.stdout + result.stderr
    assert_installed(home, "fork-pinned", result)
    assert not [r for r in world.requests() if "openRepoTools-code" in r["target"]]


# =========================================================================
# ROW 6 — branch, tag, commit and slash-containing refs
# =========================================================================

def ref_world(world: World, form: str, layout: str) -> tuple[str, str, str]:
    """`opensoft/openRepoTools` with the `form` payload at a ref of that form,
    and something else entirely on `main`, so a run that read `main` instead of
    the ref it was given installs the decoy. The ref, the commit it names, and
    the commit the payload is at."""
    if layout == "adopted":
        code = world.code(tag=form)
        sha = world.assembly(code, branch=None)
        payload_commit = code
        world.assembly(world.code(tag="decoy-main", branch=None))
    else:
        sha = world.single(tag=form, branch=None)
        payload_commit = sha
        world.single(tag="decoy-main")
    ref = {"branch": "release", "tag": "v1.0", "commit": sha,
           "slash": "feature/triad-x"}[form]
    if form == "tag":
        world.ref("opensoft/openRepoTools", f"refs/tags/{ref}", sha)
    elif form != "commit":
        world.ref("opensoft/openRepoTools", f"refs/heads/{ref}", sha)
    return ref, sha, payload_commit


@NEEDS_JQ
@pytest.mark.parametrize("form", ["branch", "tag", "commit", "slash"])
def test_r06_every_ref_form_is_resolved_once_and_every_payload_names_one_commit(
        tmp_path, form):
    """ADOPTED: the ref is asked about ONCE, and every payload request after
    that names the one immutable commit — never the ref, which can move."""
    world = World(tmp_path)
    ref, sha, payload_commit = ref_world(world, form, "adopted")
    home = tmp_path / "home"
    result = run_stdin(world, home, network(world), "--install",
                       OPENREPOTOOLS_REF=ref)
    assert result.returncode == 0, result.stdout + result.stderr
    assert_installed(home, form, result)
    asked = [r for r in world.requests()
             if re.search(r"repos/opensoft/openRepoTools/commits/", r["target"])]
    assert len(asked) == 1, asked
    payload = world.payload_requests()
    assert len(payload) == len(PAYLOAD), payload
    for r in payload:
        assert payload_commit in r["target"], r


@NEEDS_JQ
@pytest.mark.parametrize("form", ["branch", "tag", "commit", "slash"])
def test_r06_a_single_repository_reads_every_ref_form_as_it_always_did(tmp_path, form):
    """LEGACY: every ref form installs its own payload, and every request names
    the ref exactly as it was given — the one-liner's behaviour before the
    triad, kept byte for byte (#191's review, F1). Resolving it to a commit
    first would need api.github.com, which this layout never needed."""
    world = World(tmp_path)
    ref, _, _ = ref_world(world, form, "single")
    home = tmp_path / "home"
    result = run_stdin(world, home, network(world), "--install",
                       OPENREPOTOOLS_REF=ref)
    assert result.returncode == 0, result.stdout + result.stderr
    assert_installed(home, form, result)
    single_layout_requests_only(world, ref)


# =========================================================================
# ROW 7 — a branch that moves between downloads
# =========================================================================

@NEEDS_JQ
def test_r07_a_branch_that_moves_between_downloads_never_mixes_versions(tmp_path):
    """ADOPTED. A single repository is read file by file at its ref, as it
    always was (`test_r06_a_single_repository_reads_every_ref_form_as_it_always_did`):
    freezing it would need api.github.com, which that layout never needed."""
    world = World(tmp_path)
    first = world.assembly(world.code(tag="first"))
    second = world.assembly(world.code(tag="second", branch=None), branch=None)
    assert first != second
    world.moves = [{"after": 6, "repo": "opensoft/openRepoTools",
                    "ref": "refs/heads/main", "to": second}]
    world.write_conf()
    home = tmp_path / "home"
    result = run_stdin(world, home, network(world), "--install")
    assert result.returncode == 0, result.stdout + result.stderr
    assert_installed(home, "first", result)
    assert git("--git-dir", str(world.repo("opensoft/openRepoTools")), "rev-parse",
               "main").strip() == second, "the branch never moved: the test proved nothing"


# =========================================================================
# ROW 8 — missing pin in a valid single repository / partial adopted layout
# =========================================================================

@NEEDS_JQ
def test_r08_a_single_repository_without_a_code_pin_is_permitted(tmp_path):
    """Today's tree has `contracts/` — the dependency pin — and no code pin,
    and no adoption manifest: a single repository, installed as one."""
    world = World(tmp_path)
    world.single(tag="single")
    home = tmp_path / "home"
    result = run_stdin(world, home, network(world), "--install")
    assert result.returncode == 0, result.stdout + result.stderr
    assert_installed(home, "single", result)


@NEEDS_JQ
def test_r08_an_assembly_root_without_its_code_pin_refuses_as_a_single_repository_would(
        tmp_path):
    """GitHub's 404 for `contracts/code-pin.yaml` IS the single-repository
    answer, and nothing more is asked: a second question on that path (the
    manifest, `project.yaml`) would be a second request on today's layout. An
    adopter writes the pin and the manifest in ONE commit and `make validate`
    refuses one without the other, so a published assembly without its pin is
    a broken one — and since an assembly root carries no payload, it refuses
    exactly as a single repository missing those files always did."""
    world = World(tmp_path)
    world.assembly(world.code(), with_pin=False)
    home = tmp_path / "home"
    result = run_stdin(world, home, network(world), "--install")
    assert_nothing_placed(home, result)
    missing = [n for n in INSTALLABLES if n != "openRepoTools"]
    assert result.stderr == "\nREFUSED: " + single_refusal(missing), result.stderr
    single_layout_requests_only(world)


@NEEDS_COMPOSED
@NEEDS_JQ
@pytest.mark.parametrize("transport", ["gh", "curl"])
def test_r08_composed_the_root_entry_point_refuses_a_pin_its_gitlink_disagrees_with(
        tmp_path, transport):
    """The assembly's root entry point checks the lockstep rule ITSELF, before
    it fetches or runs any implementation: the gitlink at the pin's
    `submodule_path`, in the commit it resolved, must be the pinned commit.
    A stale or rolled-back pin is refused there, naming both commits, and the
    code repository is never asked for anything (lane 3's review of the T007
    patch, T3)."""
    require_composed()
    world = World(tmp_path)
    old = world.code(tag="old")
    new = world.code(tag="new")
    world.assembly(new, gitlink=old, root_entry=(ASSEMBLY / "openRepoTools").read_bytes())
    home = tmp_path / "home"
    result = run_stdin(world, home, network(world, gh=transport == "gh"), "--install",
                       script=ASSEMBLY / "openRepoTools")
    assert_nothing_placed(home, result)
    assert old in result.stderr and new in result.stderr, result.stderr
    assert "nothing ran" in result.stderr, result.stderr
    assert not [r for r in world.requests() if "openRepoTools-code" in r["target"]], \
        world.requests()


def malformed(pin: str, how: str) -> str:
    sha = re.search(r'commit: "([0-9a-f]{40})"', pin).group(1)
    return {
        "leg-role": lambda: pin.replace("leg_role: code", "leg_role: spec"),
        "commit-abbreviated": lambda: pin.replace(sha, sha[:7]),
        "commit-uppercase": lambda: pin.replace(sha, sha.upper()),
        "commit-a-branch": lambda: pin.replace(f'"{sha}"', "main"),
        "repository-not-a-slug": lambda: pin.replace("opensoft/openRepoTools-code",
                                                     "openRepoTools-code"),
        "repository-traversal": lambda: pin.replace("opensoft/openRepoTools-code",
                                                    "opensoft/.."),
        "path-nested": lambda: pin.replace("submodule_path: code", "submodule_path: legs/code"),
        "digest-short": lambda: re.sub(r'tree_sha256: "([0-9a-f]{63})[0-9a-f]"',
                                       r'tree_sha256: "\1"', pin),
        "digest-definition": lambda: pin.replace("digest_definition: sorted-ls-tree-r-v1",
                                                 "digest_definition: tarball-v0"),
        "digest-algorithm": lambda: pin.replace("digest_algorithm: sha256",
                                                "digest_algorithm: md5"),
        "revision-kind": lambda: pin.replace("revision_kind: commit", "revision_kind: tag"),
        "kind": lambda: pin.replace("kind: pinned_contract_manifest", "kind: something-else"),
        "duplicate-commit": lambda: pin.replace("revision_kind: commit",
                                                f'commit: "{"0" * 40}"\nrevision_kind: commit'),
        "missing-verify-pin": lambda: pin.replace("verify_pin: scripts/validate-pins.py\n", ""),
        "missing-resync-runbook": lambda: re.sub(r"resync_runbook: .*\n", "", pin),
        "crlf": lambda: pin.replace("\n", "\r\n"),
        "unterminated-quote": lambda: pin.replace(f'"{sha}"', f'"{sha}'),
        "digests-not-a-mapping": lambda: pin.replace("digests:\n", 'digests: "x"\n'),
        "empty": lambda: "",
    }[how]()


@NEEDS_JQ
@pytest.mark.parametrize("how", [
    "leg-role", "commit-abbreviated", "commit-uppercase", "commit-a-branch",
    "repository-not-a-slug", "repository-traversal", "path-nested", "digest-short",
    "digest-definition", "digest-algorithm", "revision-kind", "kind",
    "duplicate-commit", "missing-verify-pin", "missing-resync-runbook", "crlf",
    "unterminated-quote", "digests-not-a-mapping", "empty"])
def test_r08_a_malformed_code_pin_is_refused_never_read_as_a_single_repository(tmp_path, how):
    """A pin that is PRESENT and wrong refuses, naming what is wrong — and the
    assembly root's own copies of the payload (decoys here) are never what a
    refusal falls back to."""
    world = World(tmp_path)
    code = world.code()
    good = PIN_TEXT.format(source="opensoft/openRepoTools-code", path="code", commit=code,
                           digest=tree_digest(world.repo("opensoft/openRepoTools-code"), code))
    world.assembly(code, pin=malformed(good, how),
                   extra={p: variant(p, "decoy") for p in PAYLOAD})
    home = tmp_path / "home"
    result = run_stdin(world, home, network(world), "--install")
    assert_nothing_placed(home, result)
    assert "contracts/code-pin.yaml" in result.stderr, result.stderr
    assert world.payload_requests() == []


@NEEDS_JQ
def test_r08_a_pin_the_gitlink_disagrees_with_is_refused(tmp_path):
    world = World(tmp_path)
    old = world.code(tag="old")
    new = world.code(tag="new")
    world.assembly(new, gitlink=old)
    home = tmp_path / "home"
    result = run_stdin(world, home, network(world), "--install")
    assert_nothing_placed(home, result)
    assert old in result.stderr and new in result.stderr, result.stderr
    assert world.payload_requests() == []


@NEEDS_JQ
def test_r08_a_pin_naming_a_commit_its_repository_lacks_is_refused(tmp_path):
    world = World(tmp_path)
    elsewhere = world.code("someone/else", tag="elsewhere")
    world.repo("opensoft/openRepoTools-code")
    world.assembly(elsewhere, pin=PIN_TEXT.format(
        source="opensoft/openRepoTools-code", path="code", commit=elsewhere,
        digest=tree_digest(world.repo("someone/else"), elsewhere)))
    home = tmp_path / "home"
    result = run_stdin(world, home, network(world), "--install")
    assert_nothing_placed(home, result)
    assert "opensoft/openRepoTools-code" in result.stderr, result.stderr
    assert world.payload_requests() == []


# =========================================================================
# ROW 9 — missing or malformed API answers, authorization, transport
# =========================================================================

STEPS = {
    "resolve": lambda w, a, c: r"repos/opensoft/openRepoTools/commits/",
    "list-root": lambda w, a, c: rf"repos/opensoft/openRepoTools/git/trees/{a}",
    "list-contracts": lambda w, a, c: (r"repos/opensoft/openRepoTools/git/trees/"
                                       + w.tree_of("opensoft/openRepoTools", a, "contracts")),
    "pin": lambda w, a, c: r"contracts/code-pin\.yaml",
    "code-commit": lambda w, a, c: r"repos/opensoft/openRepoTools-code/commits/",
}
FAULTS = {
    "auth-401": {"kind": "status", "status": 401},
    "rate-403": {"kind": "status", "status": 403},
    "missing-404": {"kind": "status", "status": 404},
    "transport": {"kind": "transport"},
    "garbage": {"kind": "garbage"},
}


@NEEDS_JQ
@pytest.mark.parametrize("step,fault", [
    # GitHub's own 404 for the pin is not a failure: it is the answer that
    # there is no pin, which is a single repository (row 8). Every other
    # answer at every step is a failure.
    (step, fault) for step in STEPS for fault in FAULTS
    if (step, fault) != ("pin", "missing-404")])
def test_r09_an_api_failure_is_a_refusal_never_a_fallback_to_a_single_repository(
        tmp_path, step, fault):
    """Every round trip the resolution makes, failing every way a network
    fails, on BOTH transports: a refusal that says what answered, nothing
    placed, and never the assembly root's own copies (the decoys an older
    installer would fetch as a single repository)."""
    world = World(tmp_path)
    code = world.code()
    sha = world.assembly(code, extra={p: variant(p, "decoy") for p in PAYLOAD})
    world.faults = [{"tool": "any", "match": STEPS[step](world, sha, code), **FAULTS[fault]}]
    world.write_conf()
    home = tmp_path / "home"
    result = run_stdin(world, home, network(world), "--install")
    assert_nothing_placed(home, result)
    assert world.payload_requests() == [], world.payload_requests()
    tried = {r["tool"] for r in world.requests()}
    if (step, fault) != ("pin", "garbage"):
        # A pin `gh` DID deliver is refused for what it says, not re-fetched.
        assert tried == {"gh", "curl"}, f"both transports are tried: {tried}"


@NEEDS_JQ
def test_r09_a_pin_the_listing_shows_but_that_will_not_come_back_is_refused_saying_what_answered(
        tmp_path):
    """The adopted path's pin fetch at the resolved commit: when it fails, the
    refusal says what each transport ANSWERED, not only what was asked (#191's
    review, lane 2's (d))."""
    world = World(tmp_path)
    code = world.code()
    sha = world.assembly(code, extra={p: variant(p, "decoy") for p in PAYLOAD})
    world.faults = [{"tool": "any", "kind": "status", "status": 503,
                     "match": rf"code-pin\.yaml\?ref={sha}|/{sha}/contracts/code-pin\.yaml"}]
    world.write_conf()
    home = tmp_path / "home"
    result = run_stdin(world, home, network(world), "--install")
    assert_nothing_placed(home, result)
    assert world.payload_requests() == []
    assert "What answered:" in result.stderr, result.stderr
    assert "gh: Error (HTTP 503)" in result.stderr and "curl: HTTP 503" in result.stderr, result.stderr


# =========================================================================
# ROW 10 — changed local gitlink / changed payload / incomplete local payload
# =========================================================================

@NEEDS_JQ
def test_r10_a_local_gitlink_that_disagrees_with_the_pin_is_refused_before_staging(tmp_path):
    world = World(tmp_path)
    assembly, code, head = local_assembly(world)
    (code / "README-moved").write_text("x\n", encoding="utf-8")
    git("add", "README-moved", cwd=code)
    git("commit", "-q", "-m", "moved on", cwd=code, env=IDENTITY)
    moved = git("rev-parse", "HEAD", cwd=code).strip()
    git("update-index", "--cacheinfo", f"160000,{moved},code", cwd=assembly)
    home = tmp_path / "home"
    result = run_file(code / "openRepoTools", home, network(world), "--install")
    assert_nothing_placed(home, result)
    assert moved in result.stderr and head in result.stderr, result.stderr
    assert world.requests() == []


@NEEDS_JQ
def test_r10_a_changed_local_payload_is_refused_before_staging(tmp_path):
    world = World(tmp_path)
    assembly, code, head = local_assembly(world)
    (code / "park").write_bytes(variant("park", "edited-in-place"))
    home = tmp_path / "home"
    result = run_file(code / "openRepoTools", home, network(world), "--install")
    assert_nothing_placed(home, result)
    assert "park" in result.stderr and head in result.stderr, result.stderr
    assert world.requests() == []


@NEEDS_JQ
def test_r10_an_incomplete_local_adopted_payload_is_refused_without_a_fetch(tmp_path):
    world = World(tmp_path)
    world.assembly(world.code(tag="remote"))
    assembly, code, head = local_assembly(world)
    (code / "skills" / "restart" / "SKILL.md").unlink()
    home = tmp_path / "home"
    result = run_file(code / "openRepoTools", home, network(world), "--install")
    assert_nothing_placed(home, result)
    assert "skills/restart/SKILL.md" in result.stderr, result.stderr
    assert world.requests() == []


# =========================================================================
# ROW 11 — missing command, skill or alias, or a settings merge that fails
# =========================================================================

@NEEDS_JQ
@pytest.mark.parametrize("withheld", ["park", "skills/restart/SKILL.md", "commands/swap.md"])
def test_r11_a_payload_file_missing_from_the_pinned_code_changes_nothing(tmp_path, withheld):
    world = World(tmp_path)
    home = tmp_path / "home"
    install_prior(world, home)
    before = snapshot(home)
    code = world.code(without=(withheld,))
    world.assembly(code)
    result = run_stdin(world, home, network(world), "--install")
    assert result.returncode == 2, result.stdout + result.stderr
    assert snapshot(home) == before, "a refused install changed the prior one"
    # The refusal is today's all-or-none text, naming the source it could not
    # complete from: the code the assembly pins, never the assembly root.
    assert "NOTHING was installed" in result.stderr, result.stderr
    assert f"opensoft/openRepoTools-code at {code}" in result.stderr, result.stderr


#: `--install`'s refusals for a single repository missing files, in the words
#: `openRepoTools` at `c4864ac` printed them, from `$REPO` at `$REF` as given.
def single_refusal(withheld: str | list[str], ref: str = "main") -> str:
    names = withheld if isinstance(withheld, list) else [withheld]
    if names[0] in INSTALLABLES:
        return (f"could not fetch {' '.join(names)} from opensoft/openRepoTools at {ref}, so NOTHING was installed\n"
                "    and nothing already installed was replaced. `--install` places all\n"
                f"    {len(INSTALLABLES)} files or none: a new openRepoTools beside a missing park is\n"
                "    a half-install that reads like a whole one. Both ways were tried:\n"
                f"    gh api repos/opensoft/openRepoTools/contents/<file>?ref={ref}\n"
                f"    curl -fsSL https://raw.githubusercontent.com/opensoft/openRepoTools/{ref}/<file>\n")
    return (f"could not fetch one of the {len(SKILLS)} skills ({' '.join(SKILLS)}) or the "
            f"{len(COMMANDS)} command file ({' '.join(COMMANDS)}) from opensoft/openRepoTools at {ref}, so\n"
            "    NOTHING was installed and nothing already installed was replaced.\n")


@NEEDS_JQ
@pytest.mark.parametrize("withheld", ["park", "skills/restart/SKILL.md"])
def test_r11_a_single_repository_missing_a_file_refuses_in_the_words_it_always_did(
        tmp_path, withheld):
    """#191's review, F1: the single repository's refusal names `$REPO` at
    `$REF` as given, and not a commit it was never asked to resolve."""
    world = World(tmp_path)
    world.single(tag="single", without=(withheld,))
    home = tmp_path / "home"
    result = run_stdin(world, home, network(world), "--install")
    assert_nothing_placed(home, result)
    assert result.stderr == "\nREFUSED: " + single_refusal(withheld), result.stderr


@NEEDS_JQ
@pytest.mark.parametrize("transport", ["gh", "curl"])
def test_r11_a_single_repository_at_a_ref_it_lacks_refuses_in_the_words_it_always_did(
        tmp_path, transport):
    """A ref the repository does not have: every file 404s, and the refusal
    names every one of them at that ref, as it always did — not a commit
    lookup that failed first (#191's review, F1)."""
    world = World(tmp_path)
    world.single(tag="single")
    home = tmp_path / "home"
    result = run_stdin(world, home, network(world, gh=transport == "gh"), "--install",
                       OPENREPOTOOLS_REF="no-such-ref")
    assert_nothing_placed(home, result)
    assert result.stderr == "\nREFUSED: " + single_refusal(list(INSTALLABLES), "no-such-ref"), \
        result.stderr
    single_layout_requests_only(world, "no-such-ref")


@NEEDS_JQ
def test_r11_a_settings_merge_that_cannot_be_computed_changes_nothing(tmp_path):
    world = World(tmp_path)
    home = tmp_path / "home"
    install_prior(world, home)
    (home / ".claude" / "settings.json").write_text("{ not json\n", encoding="utf-8")
    before = snapshot(home)
    world.assembly(world.code())
    result = run_stdin(world, home, network(world), "--install")
    assert result.returncode == 2, result.stdout + result.stderr
    assert snapshot(home) == before
    assert "settings.json" in result.stderr, result.stderr
    assert world.payload_requests(), "the source was resolved before the merge was planned"


# =========================================================================
# ROW 12 — modes, ownership receipts, custom targets, foreign files, hooks
# =========================================================================

@NEEDS_JQ
def test_r12_an_adopted_install_keeps_modes_receipts_targets_and_what_is_not_ours(tmp_path):
    world = World(tmp_path)
    code = world.code()
    world.assembly(code)
    home = tmp_path / "home"
    bin_dir, profiles, claude, data = (tmp_path / "custom-bin", tmp_path / "profiles",
                                       tmp_path / "claude", tmp_path / "data")
    bin_dir.mkdir()
    (bin_dir / "mytool").write_text("#!/bin/sh\necho mine\n", encoding="utf-8")
    (bin_dir / "mytool").chmod(0o750)
    claude.mkdir()
    settings = {"theme": "dark", "hooks": {
        "UserPromptSubmit": [{"hooks": [{"type": "command", "command": "usage-guard check"}]}],
        "PreToolUse": [{"matcher": "Bash", "hooks": [{"type": "command", "command": "audit"}]}]}}
    (claude / "settings.json").write_text(json.dumps(settings), encoding="utf-8")
    result = run_stdin(world, home, network(world), "--install",
                       OPENREPOTOOLS_BIN_DIR=str(bin_dir), CLAUDE_PROFILES_HOME=str(profiles),
                       CLAUDE_USER_DIR=str(claude), OPENREPOTOOLS_DATA_DIR=str(data))
    assert result.returncode == 0, result.stdout + result.stderr
    placed = destinations(home, bin_dir=bin_dir, profiles=profiles, claude=claude)
    assert_installed(home, "pinned", result, bin_dir=bin_dir, profiles=profiles, claude=claude)
    for dest, path in placed.items():
        want = 0o755 if path in INSTALLABLES else 0o644
        assert stat.S_IMODE(Path(dest).stat().st_mode) == want, dest
    rows = [line.split("\t") for line in
            (data / "installed.tsv").read_text(encoding="utf-8").splitlines() if line]
    assert {row[1] for row in rows} == set(placed), rows
    for row in rows:
        assert row[2] == hashlib.sha256(Path(row[1]).read_bytes()).hexdigest(), row
    assert len(rows) == len(INSTALLABLES) + 2 * len(SKILLS) + 2 * len(COMMANDS)
    assert (bin_dir / "mytool").read_text(encoding="utf-8") == "#!/bin/sh\necho mine\n"
    assert stat.S_IMODE((bin_dir / "mytool").stat().st_mode) == 0o750
    merged = json.loads((claude / "settings.json").read_text(encoding="utf-8"))
    assert merged["theme"] == "dark"
    assert merged["hooks"]["PreToolUse"] == settings["hooks"]["PreToolUse"]
    commands = [h["command"] for e in merged["hooks"]["UserPromptSubmit"] for h in e["hooks"]]
    assert "usage-guard check" in commands
    assert "~/projects/xFactory/lanes-edit.sh guard" in commands
    assert stat.S_IMODE((claude / "settings.json").stat().st_mode) == 0o600


# =========================================================================
# ROWS 13 AND 14 — `wip init` takes the standard from code's dependency pin
# =========================================================================

def shape_repository(world: World) -> tuple[str, str]:
    """`opensoft/openRepoShape` with the pinned standard's real templates at
    one commit and a DECOY of them on `main`, so a seed taken from the wrong
    commit is visible in its bytes."""
    templates = UPSTREAM / "templates" / "workspace-root"
    files = {}
    for p in sorted(templates.rglob("*")):
        if p.is_file():
            files[f"templates/workspace-root/{p.relative_to(templates).as_posix()}"] = p.read_bytes()
    repo = world.repo("opensoft/openRepoShape")
    pinned = commit(repo, files, branch=None, message="pinned standard")
    decoy = {k: (v + b"\n<!-- DECOY FROM MAIN -->\n" if k.endswith(".md") else v)
             for k, v in files.items()}
    main = commit(repo, decoy, message="moved on")
    return pinned, main


def run_installed_wip(world: World, tmp_path: Path,
                      **extra: str) -> tuple[subprocess.CompletedProcess, Path]:
    home = tmp_path / "home"
    bin_dir = home / "bin"
    bin_dir.mkdir(parents=True)
    shutil.copy2(COMMAND, bin_dir / "openRepoTools")
    (home / "projects").mkdir()
    result = subprocess.run(
        ["bash", str(bin_dir / "openRepoTools"), "wip", "init", "--login", "brettheap",
         "--team", "platform", "--org", "opensoft"],
        input="", capture_output=True, text=True, check=False, cwd=str(home),
        env=env_for(home, network(world), PROJECTS_DIR=str(home / "projects"),
                    OPENREPOTOOLS_BIN_DIR=str(bin_dir), **extra))
    return result, home / "projects" / "brettheap-wip"


@NEEDS_TEMPLATES
@NEEDS_JQ
def test_r13_wip_init_takes_the_standard_from_codes_dependency_pin_not_the_assemblys(tmp_path):
    """An INSTALLED `openRepoTools` (no checkout beside it) seeding a workspace
    against an adopted assembly: the template comes from the openRepoShape
    commit the CODE leg pins in `contracts/openreposhape-pin.yaml` — not a
    same-named file at the assembly root, and not `main`."""
    world = World(tmp_path)
    pinned, moved = shape_repository(world)
    code = world.code(shape=pinned)
    world.assembly(code, extra={"contracts/openreposhape-pin.yaml": shape_pin(moved)})
    result, checkout = run_installed_wip(world, tmp_path)
    assert result.returncode == 0, result.stdout + result.stderr
    assert f"template files from opensoft/openRepoShape @ {pinned}" in result.stdout, result.stdout
    assert "DECOY FROM MAIN" not in (checkout / "README.md").read_text(encoding="utf-8")


@NEEDS_TEMPLATES
@NEEDS_JQ
def test_r13_an_installed_wip_init_whose_source_does_not_answer_seeds_from_main_as_before(
        tmp_path):
    """#191's review, F2: an installed `wip init` whose `$REPO` does not answer
    at all (both transports fail to reach it) takes the standard's `main`, as it
    always did, rather than refusing at step 7 after steps 5 and 6 made and
    cloned the repository."""
    world = World(tmp_path)
    shape_repository(world)
    world.single(tag="single")
    world.faults = [{"tool": "any", "match": r"opensoft/openRepoTools/", "kind": "transport"}]
    world.write_conf()
    result, checkout = run_installed_wip(world, tmp_path)
    assert result.returncode == 0, result.stdout + result.stderr
    assert "template files from opensoft/openRepoShape @ main" in result.stdout, result.stdout
    assert (checkout / "README.md").is_file()


@NEEDS_TEMPLATES
@NEEDS_JQ
def test_r13_an_installed_wip_init_at_a_ref_the_source_lacks_seeds_from_main_as_before(
        tmp_path):
    """#191's review, F2: `OPENREPOTOOLS_REF` naming a ref the repository does
    not have leaves the standard's `main`, as it always did — not a refusal at
    step 7 after steps 5 and 6 made and cloned the repository."""
    world = World(tmp_path)
    shape_repository(world)
    world.single(tag="single")
    result, checkout = run_installed_wip(world, tmp_path, OPENREPOTOOLS_REF="no-such-ref")
    assert result.returncode == 0, result.stdout + result.stderr
    assert "template files from opensoft/openRepoShape @ main" in result.stdout, result.stdout
    assert (checkout / "README.md").is_file()


@NEEDS_TEMPLATES
@NEEDS_JQ
def test_r13_an_installed_wip_init_never_needs_a_single_repositorys_commit_lookup(tmp_path):
    """#191's review, F2: a 502 on `commits/<ref>` — an endpoint a single
    repository's `wip init` never asked — changes nothing: the dependency pin
    is read at the ref as given and the template comes from it."""
    world = World(tmp_path)
    pinned, _ = shape_repository(world)
    world.single(tag="single", shape=pinned)
    world.faults = [{"tool": "any", "match": r"repos/opensoft/openRepoTools/commits/",
                     "kind": "status", "status": 502}]
    world.write_conf()
    result, checkout = run_installed_wip(world, tmp_path)
    assert result.returncode == 0, result.stdout + result.stderr
    assert f"template files from opensoft/openRepoShape @ {pinned}" in result.stdout, result.stdout
    assert "DECOY FROM MAIN" not in (checkout / "README.md").read_text(encoding="utf-8")


@NEEDS_TEMPLATES
@NEEDS_JQ
def test_r13_an_installed_wip_init_on_a_single_repository_reads_its_pin_as_before(tmp_path):
    """Today's layout: the dependency pin at `$REPO`'s `contracts/`, at the ref
    given, by `gh api …/contents` — and no `commits/` or `git/trees/` request
    for `$REPO`."""
    world = World(tmp_path)
    pinned, moved = shape_repository(world)
    world.single(tag="single", shape=pinned)
    result, checkout = run_installed_wip(world, tmp_path)
    assert result.returncode == 0, result.stdout + result.stderr
    assert f"template files from opensoft/openRepoShape @ {pinned}" in result.stdout, result.stdout
    assert "DECOY FROM MAIN" not in (checkout / "README.md").read_text(encoding="utf-8")
    asked = [r["target"] for r in world.requests()
             if "opensoft/openRepoTools/" in r["target"]]
    assert asked and all("/contents/" in t and t.endswith("?ref=main") for t in asked), asked


@NEEDS_TEMPLATES
@NEEDS_JQ
def test_r13_an_adopted_source_wip_init_cannot_follow_refuses_in_step_7s_words(tmp_path):
    """An adopted assembly whose pin is wrong refuses at step 7 — after steps 5
    and 6 made and cloned the repository — so the refusal says what step 7 did
    not do and keeps what came before, rather than claiming nothing was
    written (#191's review, F2)."""
    world = World(tmp_path)
    pinned, _ = shape_repository(world)
    code = world.code(shape=pinned)
    good = PIN_TEXT.format(source="opensoft/openRepoTools-code", path="code", commit=code,
                           digest=tree_digest(world.repo("opensoft/openRepoTools-code"), code))
    world.assembly(code, pin=malformed(good, "leg-role"))
    result, checkout = run_installed_wip(world, tmp_path)
    assert result.returncode == 2, result.stdout + result.stderr
    assert "contracts/code-pin.yaml" in result.stderr, result.stderr
    assert "Step 7 seeded nothing" in result.stderr, result.stderr
    assert "nothing was fetched, placed or written" not in result.stderr
    assert "NOTHING was installed" not in result.stderr
    assert (checkout / ".git").is_dir(), "step 6's clone is what the refusal keeps"
    assert not (checkout / "README.md").exists()


@NEEDS_TEMPLATES
@NEEDS_JQ
def test_r14_with_no_nested_standard_anywhere_the_dependency_pin_alone_selects(tmp_path):
    """Standalone code with its nested dependency nowhere on disk — the
    installed copy, the vendored tree: the dependency PIN is what selects the
    standard, fetched from the code the assembly pins; `main` is only the
    documented answer when that pin cannot be read at all."""
    world = World(tmp_path)
    pinned, moved = shape_repository(world)
    world.assembly(world.code(shape=pinned))
    result, checkout = run_installed_wip(world, tmp_path)
    assert result.returncode == 0, result.stdout + result.stderr
    assert f"@ {pinned}" in result.stdout, result.stdout
    assert moved not in result.stdout
    assert "DECOY FROM MAIN" not in (checkout / "README.md").read_text(encoding="utf-8")


def test_r14_the_documented_upstream_skip_is_unchanged():
    """Without the submodule the command tests SKIP, naming the one command
    that fixes it (AGENTS.md, "Testing your changes"); conftest says so."""
    import conftest
    # Read from conftest's text: in a composed run `NEEDS_UPSTREAM` is a
    # fixture that FAILS instead (#190), and the standalone skip is still there.
    assert "git submodule update --init upstream/openRepoShape" in \
        Path(conftest.__file__).read_text(encoding="utf-8")


@NEEDS_COMPOSED
def test_r14_composed_acceptance_requires_the_nested_dependency():
    """Composed acceptance REFUSES an absent dependency rather than skipping
    it: a mounted code leg without its pinned standard is not the assembled
    state T015 accepts."""
    require_composed()
    assert (UPSTREAM / "scripts" / "repo_shape.py").is_file(), (
        "the code leg is mounted but its nested openRepoShape is not: run "
        "`git submodule update --init --recursive` (or `make bootstrap`) at the assembly")


# =========================================================================
# ROW 15 — Linux/macOS bash 3.2, Windows/WSL
# =========================================================================

BASH4 = [(re.compile(r"\$\{[A-Za-z_][A-Za-z0-9_]*(,,|\^\^)"), "${x,,} / ${x^^}"),
         (re.compile(r"\bmapfile\b|\breadarray\b"), "mapfile/readarray"),
         (re.compile(r"\bdeclare\s+-[a-zA-Z]*[An]"), "declare -A / -n"),
         (re.compile(r"\blocal\s+-n\b"), "local -n"),
         (re.compile(r"\|&"), "|&"),
         (re.compile(r"\bcoproc\b"), "coproc"),
         (re.compile(r"\[\[\s+-v\b"), "[[ -v ]]")]


def bash4_constructs(text: str) -> list[str]:
    found = []
    for number, line in enumerate(text.splitlines(), 1):
        code = line.split("#", 1)[0] if not line.lstrip().startswith("#") else ""
        for pattern, name in BASH4:
            if pattern.search(code):
                found.append(f"{number}: {name}: {line.strip()}")
    return found


def test_r15_the_installer_uses_nothing_bash_3_2_lacks():
    """CI's `parse-macos` parses every shipped file under Apple's bash 3.2;
    this names the constructs a Linux bash 5 would accept silently."""
    assert bash4_constructs(SOURCE_TEXT) == []
    assert subprocess.run(["bash", "-n", str(COMMAND)]).returncode == 0


def test_r15_the_three_lists_stay_one_line_arrays_a_consumer_parses():
    """workBenches' `estate-commands-start` `sed`-reads `INSTALLABLES`,
    `SKILLS` and `COMMANDS` out of the vendored `openRepoTools` (consumer-reads
    row W4): one line each, or that step reads nothing."""
    for name in ("INSTALLABLES", "SKILLS", "COMMANDS"):
        assert one_line_array(SOURCE_TEXT, name)


@NEEDS_JQ
def test_r15_the_adopted_path_holds_under_macos_one_true_awk(tmp_path):
    """macOS's awk refuses a newline in an `awk -v` value (exit 2, no output);
    gawk and mawk accept it, so no Linux job sees it. The adopted resolution
    runs here under a shim that IS that rule."""
    real_awk = shutil.which("awk")
    shim = textwrap.dedent(f"""\
        #!/bin/sh
        prev=""
        for a in "$@"; do
          if [ "$prev" = "-v" ]; then
            case "$a" in *'
        '*) echo "awk: newline in string $a" >&2; exit 2 ;; esac
          fi
          prev="$a"
        done
        exec '{real_awk}' "$@"
        """)
    world = World(tmp_path)
    world.assembly(world.code())
    home = tmp_path / "home"
    result = run_stdin(world, home, network(world, extra_shims={"awk": shim}), "--install")
    assert result.returncode == 0, result.stdout + result.stderr
    assert_installed(home, "pinned", result)


#: THE PIN READER THE ROOT ENTRY POINT CARRIES IS A DELIBERATE COPY of the
#: implementation's: the root must read the pin before there is an
#: implementation to ask. Copies that may not drift are compared, here.
PIN_READER = ("ORT_ALNUM", "ORT_TAB", "ORT_CR", "is_lower_hex", "is_slug",
              "is_segment", "pin_scalar", "pin_bad", "pin_parse", "recorded_gitlink")


def shell_definitions(text: str) -> dict[str, str | None]:
    out: dict[str, str | None] = {}
    for name in PIN_READER:
        if name.isupper():
            m = re.search(rf"^{name}=.*$", text, re.M)
        else:
            m = re.search(rf"^{name}\(\) \{{.*?^\}}\n", text, re.S | re.M)
        out[name] = m.group(0) if m else None
    return out


@NEEDS_COMPOSED
def test_r15_composed_the_root_entry_points_pin_reader_is_the_implementations():
    require_composed()
    mine = shell_definitions((ASSEMBLY / "openRepoTools").read_text(encoding="utf-8"))
    theirs = shell_definitions(SOURCE_TEXT)
    assert all(theirs.values()), theirs
    assert mine == theirs, [n for n in PIN_READER if mine[n] != theirs[n]]


@NEEDS_COMPOSED
def test_r15_composed_the_root_entry_point_parses_and_uses_nothing_bash_3_2_lacks():
    require_composed()
    root = ASSEMBLY / "openRepoTools"
    assert bash4_constructs(root.read_text(encoding="utf-8")) == []
    assert subprocess.run(["bash", "-n", str(root)]).returncode == 0
