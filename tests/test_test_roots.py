# SPDX-License-Identifier: Apache-2.0
"""THE FOUR ROOTS AND THE TWO MODES, held (opensoft/openRepoTools#186, T009 of
`specs/004-migrate-to-triad/tasks.md`).

`tests/conftest.py` resolves a CODE root (the commands, `tests/`, the pin), an
ASSEMBLY root (`README.md`, `AGENTS.md`, `CLAUDE.md`, the leg pins), a SPEC root
(`docs/`, `openspec/`, `specs/`) and the DEPENDENCY nested in the code root
(`upstream/openRepoShape`) — from `OPENREPOTOOLS_CODE_ROOT`,
`OPENREPOTOOLS_ASSEMBLY_ROOT` and `OPENREPOTOOLS_SPEC_ROOT` where they are set,
from the layout where they are not. `OPENREPOTOOLS_COMPOSED=1` makes the run a
claim about the whole arrangement: every root present, each leg at the commit
the assembly pins, and nothing skipped for want of one.

TWO KINDS OF TEST HERE. The resolver is asked directly about fixture layouts
built under `tmp_path` — today's single tree, a triad, a standalone code leg —
which is fast and runs everywhere. And because a resolver nobody calls proves
nothing about the suite, the SUITE ITSELF is run against those fixtures, in a
nested `pytest` with the variables set: the hygiene module must read the
README from the fixture's assembly root and the lane manual from its spec
root, the pin module must read the fixture code root's own gitlink, the
no-submodule skip must still be today's skip, and a composed run missing a
context must refuse rather than start. Those nested runs are what was red at
`origin/main`, where every one of those variables was ignored.

NOTHING HERE TOUCHES A REAL REPOSITORY'S STATE. Every fixture is a copy or a
fresh `git init` under `tmp_path`; the real code root and its dependency are
only READ (a `git ls-files`, a local `git clone`). Every fixture's legs are
pinned with the tree digest recomputed from the fixture's own tree, never
written in to agree.
"""

from __future__ import annotations

import hashlib
import os
import re
import shutil
import subprocess
import sys
import xml.etree.ElementTree as ET
from pathlib import Path

import pytest

import conftest
from conftest import NEEDS_UPSTREAM, REPO, WINDOWS_SKIP

TESTS = Path(__file__).resolve().parent
DEPENDENCY = REPO / "upstream" / "openRepoShape"
WRAPPER = REPO / "tests" / "run.sh"

#: What a code leg does NOT carry after the split, by the adoption mapping's
#: placement table: the root files went to the assembly and the four trees to
#: the spec leg. A fixture code leg is the code root less these. EXCEPT
#: `.gitattributes`, which the table also sends to the assembly and which the
#: code leg must carry too — git never applies the assembly's inside a
#: submodule (conftest's `GUIDANCE_DOCUMENTS` note) — so a fixture leg keeps
#: it, as the leg is meant to be (Copilot on #190). `LICENSE` and `.gitignore`
#: likewise: T006's `code-0001` gives the code leg its own copy of each, so a
#: fixture leg keeps them too (#193 item 7).
ASSEMBLY_FILES = ("README.md", "AGENTS.md", "CLAUDE.md")
SPEC_TREES = ("docs", "openspec", "specs", "ideation")

INSTALL_LINE = (
    "curl -fsSL https://raw.githubusercontent.com/opensoft/openRepoTools/main/"
    "openRepoTools | bash -s -- --install")
FORK_ACT = "lane-end <lane> --retire <pid|uuid>"

#: The rehearsed assembly's `contracts/code-pin.yaml` grammar
#: (`adopt/three-repo-shape` at 2726d3a), field for field.
LEG_PIN = """\
schema_version: 1
kind: pinned_contract_manifest

leg_role: {role}
source_repository: example/fixture-{role}
submodule_path: {role}

commit: "{commit}"
revision_kind: commit

digest_algorithm: sha256
digest_definition: sorted-ls-tree-r-v1
digests:
  tree_sha256: "{digest}"

verify_pin: scripts/validate-pins.py
resync_runbook: "README.md#the-lockstep-invariant"
"""

PROJECT_YAML = """\
schema_version: 1
kind: project-manifest
id: fixture
name: "fixture"
legs:
  - role: assembly
    repository: example/fixture
    path: "."
  - role: spec
    repository: example/fixture-spec
    path: spec
  - role: code
    repository: example/fixture-code
    path: code
"""

#: Git in a fixture: an identity of its own. The one clone of the dependency
#: is a local-path clone, which needs no `protocol.file.allow` (#193 item 7).
GIT_ENV = {"GIT_AUTHOR_NAME": "openRepoTools CI",
           "GIT_AUTHOR_EMAIL": "ci@openrepotools.invalid",
           "GIT_COMMITTER_NAME": "openRepoTools CI",
           "GIT_COMMITTER_EMAIL": "ci@openrepotools.invalid"}


def run_git(cwd: Path, *args: str) -> str:
    env = dict(os.environ)
    env.update(GIT_ENV)
    proc = subprocess.run(["git", *args], cwd=str(cwd), capture_output=True,
                          text=True, env=env, check=False)
    assert proc.returncode == 0, (f"git {' '.join(args)} in {cwd}:\n"
                                  f"{proc.stderr}{proc.stdout}")
    return proc.stdout.strip()


def tree_sha256(repository: Path, commit: str) -> str:
    """`sorted-ls-tree-r-v1`, exactly as the pin grammar defines it."""
    out = subprocess.run(["git", "ls-tree", "-r", "-z", commit],
                         cwd=str(repository), capture_output=True,
                         check=True).stdout
    records = sorted(record for record in out.split(b"\0") if record)
    return hashlib.sha256(b"".join(r + b"\n" for r in records)).hexdigest()


def pinned_commit() -> str:
    for line in (REPO / "contracts" / "openreposhape-pin.yaml").read_text(
            encoding="utf-8").splitlines():
        if line.startswith("commit:"):
            return line.split(":", 1)[1].strip().strip('"')
    raise AssertionError("the dependency pin records no commit")


def dependency_present() -> bool:
    return (DEPENDENCY / "scripts" / "repo_shape.py").is_file()


# --- fixture layouts ----------------------------------------------------------

def code_leg(dest: Path, *, single: bool = False, repository: bool = False,
             gitlink: str = "", dependency: str = "") -> Path:
    """A copy of the code root's tracked files at `dest`.

    `single` keeps the assembly's files and the spec trees (today's layout);
    otherwise they are left out, as the split leaves them. `repository` makes
    it a repository of its own with one commit, recording `gitlink` (default:
    the pinned commit) at `upstream/openRepoShape`. `dependency` is "" for no
    directory there, "empty" for the empty one a clone without
    `--recurse-submodules` leaves, or "clone" for a checkout of the real
    dependency at the pinned commit.
    """
    listed = run_git(REPO, "ls-files", "-z").split("\0")
    for rel in filter(None, listed):
        top = rel.split("/", 1)[0]
        if not single and (rel in ASSEMBLY_FILES or top in SPEC_TREES):
            continue
        source = REPO / rel
        if not source.is_file():
            continue          # the dependency's gitlink, which is not a file
        target = dest / rel
        target.parent.mkdir(parents=True, exist_ok=True)
        shutil.copy2(source, target)
    if single:
        # TODAY'S TREE EVEN WHERE THIS RUN IS A CODE LEG (the composed job):
        # the documents and the spec trees a single repository carries.
        for rel, text in (("README.md", f"# fixture\n\n    {INSTALL_LINE}\n"),
                          ("AGENTS.md", "# fixture\n"),
                          ("docs/README-lanes.md", f"# Lanes\n\n{FORK_ACT}\n"),
                          ("openspec/README.md", "# fixture spec\n")):
            target = dest / rel
            if not target.exists():
                target.parent.mkdir(parents=True, exist_ok=True)
                target.write_text(text, encoding="utf-8")
    if repository:
        run_git(dest, "init", "-q")
        run_git(dest, "add", "-A")
        run_git(dest, "update-index", "--add", "--cacheinfo",
                f"160000,{gitlink or pinned_commit()},upstream/openRepoShape")
        run_git(dest, "commit", "-q", "-m", "the code leg, copied for a fixture")
    if dependency == "empty":
        (dest / "upstream" / "openRepoShape").mkdir(parents=True, exist_ok=True)
    elif dependency == "clone":
        target = dest / "upstream" / "openRepoShape"
        if target.exists():
            target.rmdir()
        run_git(dest, "clone", "-q", "--no-checkout", str(DEPENDENCY), str(target))
        run_git(target, "checkout", "-q", "--detach", pinned_commit())
    return dest


def spec_leg(dest: Path, *, manual: str = f"# Lanes\n\n{FORK_ACT}\n",
             repository: bool = False) -> Path:
    (dest / "docs").mkdir(parents=True)
    (dest / "docs" / "README-lanes.md").write_text(manual, encoding="utf-8")
    (dest / "openspec").mkdir()
    (dest / "openspec" / "README.md").write_text("# fixture spec\n",
                                                 encoding="utf-8")
    if repository:
        run_git(dest, "init", "-q")
        run_git(dest, "add", "-A")
        run_git(dest, "commit", "-q", "-m", "the spec leg, for a fixture")
    return dest


def assembly(dest: Path, *, readme: str = f"# fixture\n\n    {INSTALL_LINE}\n",
             code: Path | None = None, spec: Path | None = None,
             repository: bool = False) -> Path:
    """An assembly root at `dest`: the manifest, the two leg pins and a
    README. With `repository`, a repository of its own whose HEAD records
    `code` and `spec` as gitlinks at each one's own HEAD, the pins recording
    the same commits and each leg's recomputed tree digest."""
    (dest / "contracts").mkdir(parents=True, exist_ok=True)
    (dest / "project.yaml").write_text(PROJECT_YAML, encoding="utf-8")
    (dest / "README.md").write_text(readme, encoding="utf-8")
    heads = {}
    for role, leg in (("code", code), ("spec", spec)):
        head = run_git(leg, "rev-parse", "HEAD") if (leg and repository) else "0" * 40
        digest = tree_sha256(leg, head) if (leg and repository) else "0" * 64
        heads[role] = head
        (dest / "contracts" / f"{role}-pin.yaml").write_text(
            LEG_PIN.format(role=role, commit=head, digest=digest),
            encoding="utf-8")
    if repository:
        run_git(dest, "init", "-q")
        run_git(dest, "add", "--", "project.yaml", "README.md", "contracts")
        for role in ("code", "spec"):
            run_git(dest, "update-index", "--add", "--cacheinfo",
                    f"160000,{heads[role]},{role}")
        run_git(dest, "commit", "-q", "-m", "the assembly, for a fixture")
    return dest


# --- the suite, run nested against a fixture ----------------------------------

class Nested:
    def __init__(self, proc: subprocess.CompletedProcess, outcomes: dict):
        self.returncode = proc.returncode
        self.output = proc.stdout + proc.stderr
        self.outcomes = outcomes

    def outcome(self, name: str) -> tuple:
        assert name in self.outcomes, (
            f"{name} did not run; the nested run said:\n{self.output[-3000:]}")
        return self.outcomes[name]


_nested_runs = [0]


def nested(tmp_path: Path, env: dict, select: str, *modules: str) -> Nested:
    """`python -m pytest` on this suite's own `modules`, `-k select`, with
    `env` as the ONLY `OPENREPOTOOLS_*` variables: a run that read anything
    from the outer run's roots would prove nothing about these."""
    _nested_runs[0] += 1
    n = _nested_runs[0]
    junit = tmp_path / f"nested-{n}.xml"
    child = {k: v for k, v in os.environ.items()
             if not k.startswith("OPENREPOTOOLS_") and k != "PYTEST_ADDOPTS"}
    child.update(GIT_ENV)
    child.update(env)
    child["PYTHONDONTWRITEBYTECODE"] = "1"
    command = [sys.executable, "-m", "pytest", "-q", "-p", "no:cacheprovider",
               "-rA", f"--junitxml={junit}",
               f"--basetemp={tmp_path / f'nested-{n}-tmp'}", "-k", select,
               *(str(TESTS / module) for module in modules)]
    proc = subprocess.run(command, cwd=str(tmp_path), env=child,
                          capture_output=True, text=True, timeout=900,
                          check=False)
    outcomes = {}
    if junit.is_file():
        for case in ET.parse(str(junit)).getroot().iter("testcase"):
            outcome, message = "passed", ""
            for kind in ("failure", "error", "skipped"):
                found = case.find(kind)
                if found is not None:
                    outcome = kind
                    message = (found.get("message") or "") + (found.text or "")
                    break
            outcomes[case.get("name")] = (outcome, message)
    return Nested(proc, outcomes)


README_TEST = "test_the_readme_prints_the_install_line_the_pointer_prints"
MANUAL_TEST = "test_the_manual_offers_the_fork_act_and_not_a_kill"
LOCKSTEP_TEST = "test_the_gitlink_and_the_pin_name_the_same_commit"
DIGEST_TEST = "test_the_tree_digest_is_the_pinned_commits_own_number"
HEAD_TEST = "test_the_checked_out_submodule_is_at_the_recorded_commit"


def test_the_hygiene_suite_reads_the_readme_from_the_assembly_root(tmp_path):
    """`OPENREPOTOOLS_ASSEMBLY_ROOT` decides which README the install-line
    test reads: one that lacks the line FAILS it, one that carries it passes.
    Red at `origin/main`, which read this checkout's own README either way."""
    lacking = assembly(tmp_path / "lacking", readme="# no install line here\n")
    carrying = assembly(tmp_path / "carrying")
    red = nested(tmp_path, {"OPENREPOTOOLS_ASSEMBLY_ROOT": str(lacking)},
                 README_TEST, "test_repo_hygiene.py")
    outcome, message = red.outcome(README_TEST)
    assert outcome == "failure" and "does not carry the install line" in message, (
        f"the README test {outcome} against an assembly README with no install "
        f"line; it did not read the assembly root:\n{message}\n{red.output[-2000:]}")
    green = nested(tmp_path, {"OPENREPOTOOLS_ASSEMBLY_ROOT": str(carrying)},
                   README_TEST, "test_repo_hygiene.py")
    assert green.outcome(README_TEST)[0] == "passed", green.output[-3000:]


def test_the_hygiene_suite_reads_the_lane_manual_from_the_spec_root(tmp_path):
    """`OPENREPOTOOLS_SPEC_ROOT` decides which `docs/README-lanes.md` is read:
    a manual that never spells the fork act FAILS the manual test."""
    lacking = spec_leg(tmp_path / "lacking", manual="# Lanes\n\nnothing here\n")
    carrying = spec_leg(tmp_path / "carrying")
    red = nested(tmp_path, {"OPENREPOTOOLS_SPEC_ROOT": str(lacking)},
                 MANUAL_TEST, "test_repo_hygiene.py")
    outcome, message = red.outcome(MANUAL_TEST)
    assert outcome == "failure" and "never spells the one fork act" in message, (
        f"the manual test {outcome} against a spec root whose manual lacks the "
        f"act; it did not read the spec root:\n{message}\n{red.output[-2000:]}")
    green = nested(tmp_path, {"OPENREPOTOOLS_SPEC_ROOT": str(carrying)},
                   MANUAL_TEST, "test_repo_hygiene.py")
    assert green.outcome(MANUAL_TEST)[0] == "passed", green.output[-3000:]


AGENTS_CAP_TEST = "test_agents_md_is_short_enough_to_be_read"
README_CAP_TEST = "test_readme_is_short_enough_to_be_read"


PIN_RULES_TEST = "test_agents_md_names_the_pin_rules"


@pytest.mark.parametrize("prefixed, outcome", [
    pytest.param(True, "passed", id="the-assemblys-code-prefixed-rules"),
    pytest.param(False, "failure", id="todays-spelling-at-an-assembly-root"),
])
def test_the_pin_rules_are_read_with_the_assemblys_code_prefix(tmp_path, prefixed, outcome):
    """At an assembly root the pin rules name the submodule through the code
    mount, `code/upstream/openRepoShape` and `git -C code submodule update
    …`, as T006's `assembly-0001` writes them; today's spelling there names a
    path the assembly does not have, and FAILS (#193 item 14). Red at
    `fb77bed`, which held the assembly's AGENTS.md to today's spelling."""
    where, init = (("code/", "git -C code submodule update")
                   if prefixed else ("", "git submodule update"))
    root = assembly(tmp_path / "asm")
    (root / "AGENTS.md").write_text(
        f"1. **Never edit anything under `{where}upstream/openRepoShape` in place.**\n"
        "2. **Never pin a commit that is not on that repository's `main`.**\n"
        "3. **The digest is RECOMPUTED, never adjusted.**\n"
        f"    {init} --init upstream/openRepoShape\n", encoding="utf-8")
    run = nested(tmp_path, {"OPENREPOTOOLS_ASSEMBLY_ROOT": str(root)},
                 PIN_RULES_TEST, "test_repo_hygiene.py")
    assert run.outcome(PIN_RULES_TEST)[0] == outcome, run.output[-2000:]


def test_the_length_caps_are_the_assembly_roots_where_one_is_named(tmp_path):
    """At an assembly root the two caps are 347 and 510 — this repository's 323
    and 486 plus the twenty-four lines each that T006's root guidance adds
    there — and they are asked of the ASSEMBLY's files: one line over FAILS,
    the cap itself passes. Red at `origin/main`, which counted this checkout's
    own README and AGENTS.md whatever was named."""
    def lines(n: int) -> str:
        return "".join(f"line {i}\n" for i in range(n))
    at_cap = assembly(tmp_path / "at", readme=lines(510))
    (at_cap / "AGENTS.md").write_text(lines(347), encoding="utf-8")
    over = assembly(tmp_path / "over", readme=lines(511))
    (over / "AGENTS.md").write_text(lines(348), encoding="utf-8")
    select = f"{AGENTS_CAP_TEST} or {README_CAP_TEST}"
    green = nested(tmp_path, {"OPENREPOTOOLS_ASSEMBLY_ROOT": str(at_cap)},
                   select, "test_repo_hygiene.py")
    for name in (AGENTS_CAP_TEST, README_CAP_TEST):
        assert green.outcome(name)[0] == "passed", green.output[-3000:]
    red = nested(tmp_path, {"OPENREPOTOOLS_ASSEMBLY_ROOT": str(over)},
                 select, "test_repo_hygiene.py")
    for name, said in ((AGENTS_CAP_TEST, "AGENTS.md is 348 lines; the cap is 347"),
                       (README_CAP_TEST, "README.md is 511 lines; the cap is 510")):
        outcome, message = red.outcome(name)
        assert outcome == "failure" and said in message, (
            f"{name} {outcome} on an assembly file one line over its cap:\n"
            f"{message}\n{red.output[-2000:]}")


def test_the_lane_suite_fails_a_missing_manual_by_name():
    """`tests/test_lane_helpers.sh` reads the lane manual where the run's roots
    put it, and a manual that is not there FAILS naming the path, before the
    `cat … || :` that would otherwise hand the assertions an empty string
    (T006's record of 2026-10-08, §10). Held on the text, as this module's
    neighbours hold the shell suite's other properties: the suite itself is
    forty minutes of bash, and its own run proves the readable branch."""
    lines = (REPO / "tests" / "test_lane_helpers.sh").read_text(
        encoding="utf-8").splitlines()
    reads = [i for i, line in enumerate(lines)
             if "README-lanes.md" not in line and 'cat "$LANE_MANUAL"' in line]
    assert len(reads) == 2, f"expected the two manual reads, found {len(reads)}"
    assert not any('cat "$SRC_DIR/docs/README-lanes.md"' in l for l in lines), (
        "a manual read still bypasses the run's roots")
    for i in reads:
        guard = "\n".join(lines[max(0, i - 3):i])
        assert '[ -r "$LANE_MANUAL" ]' in guard and "bad " in guard and \
            "no readable file at $LANE_MANUAL" in guard, (
            f"line {i + 1} reads the manual with no failure for a missing one "
            f"in the three lines above it:\n{guard}")


# --- the lane suite's manual sections, read and run ---------------------------

SUITE = REPO / "tests" / "test_lane_helpers.sh"
MANUAL_GUARD = re.compile(r'^if \[ -n "\$LANE_MANUAL" \]$')
MANUAL_USE = re.compile(r'\$\{?(?:ln_doc|ss_doc)\b')
HEREDOC = re.compile(r"""<<(-?)\s*\\?(['"]?)([A-Za-z_][A-Za-z0-9_]*)\2""")


def shell_commands(line: str) -> list:
    """`line` cut at each `;` outside quotes, stopping at a `#` comment: a
    reading of the suite's one-line `if …; then …` / `else …; fi` forms that
    is enough to follow their nesting, and no more than that."""
    out, cur, quote, i = [], [], None, 0
    while i < len(line):
        ch = line[i]
        if quote:
            cur.append(ch)
            if ch == "\\" and quote == '"' and i + 1 < len(line):
                cur.append(line[i + 1])
                i += 2
                continue
            if ch == quote:
                quote = None
        elif ch in "\"'":
            quote = ch
            cur.append(ch)
        elif ch == "\\" and i + 1 < len(line):
            cur.append(line[i:i + 2])
            i += 2
            continue
        elif ch == "#" and (not cur or "".join(cur)[-1:].isspace()):
            break
        elif ch == ";":
            out.append("".join(cur).strip())
            cur = []
        else:
            cur.append(ch)
        i += 1
    out.append("".join(cur).strip())
    return [c for c in out if c]


def heredoc_in(line: str):
    """The first here-document `line` opens outside quotes, as (dash, word):
    its body is not shell this reading follows (the suite writes fakes and
    Python through them)."""
    quote, i = None, 0
    while i < len(line):
        ch = line[i]
        if quote:
            if ch == "\\" and quote == '"':
                i += 2
                continue
            if ch == quote:
                quote = None
        elif ch in "\"'":
            quote = ch
        elif ch == "\\":
            i += 2
            continue
        elif ch == "#" and (i == 0 or line[i - 1].isspace()):
            return None
        elif line.startswith("<<", i) and not line.startswith("<<<", i):
            found = HEREDOC.match(line, i)
            return (found.group(1) == "-", found.group(3)) if found else None
        i += 1
    return None


def manual_reads(lines: list):
    """Follow the suite's `if`/`elif`/`else`/`fi` nesting, here-documents
    skipped. Returns each use of the manual's text (`$ss_doc`, `$ln_doc`, in
    either spelling) with whether the THEN branch of an
    `if [ -n "$LANE_MANUAL" ]` holds it; each such section's first and last
    line; and the frames still open at the end, which must be none for the
    reading to be trusted."""
    stack, uses, blocks, heredoc = [], [], [], None
    for n, raw in enumerate(lines):
        if heredoc is not None:
            if (raw.lstrip("\t") if heredoc[0] else raw) == heredoc[1]:
                heredoc = None
            continue
        if raw.lstrip().startswith("#"):
            continue
        opened = heredoc_in(raw)
        for cmd in shell_commands(raw):
            word, _, rest = cmd.partition(" ")
            rest = rest.strip()
            if word in ("then", "do") and rest:
                cmd = rest
                word, _, rest = cmd.partition(" ")
                rest = rest.strip()
            if word == "if":
                stack.append([bool(MANUAL_GUARD.match(cmd)), False, n])
                continue
            if word in ("elif", "else"):
                if stack:
                    stack[-1][1] = True
                if word == "elif" or not rest:
                    continue
                cmd = rest
            if word == "fi":
                if stack:
                    frame = stack.pop()
                    if frame[0]:
                        blocks.append((frame[2], n))
                continue
            if MANUAL_USE.search(cmd):
                uses.append((n, any(f[0] and not f[1] for f in stack)))
        if opened:
            heredoc = opened
    return uses, blocks, stack


def test_the_lane_suite_reads_the_manual_only_inside_its_guard():
    """Every use of the manual's text in `tests/test_lane_helpers.sh` sits in
    the THEN branch of an `if [ -n "$LANE_MANUAL" ]` guard. `ss_doc` and
    `ln_doc` are bound only there, and the suite runs under `set -u`, so one
    use outside a guard does not skip in a code leg with no spec root: it
    ABORTS the whole suite with `ln_doc: unbound variable` (lane
    openRepoTools-3's review of #190; fixed in `b50f197`).

    The nesting is FOLLOWED, not guessed from the nearest line spelled `fi`:
    the first reading missed a `${ln_doc}` and an indented closing `fi` (the
    review of `b50f197`, point 6; #193 item 7). The reading planted with both
    is held by the test below."""
    uses, blocks, still_open = manual_reads(
        SUITE.read_text(encoding="utf-8").splitlines())
    assert not still_open, (
        f"the suite's if/fi nesting could not be followed past line "
        f"{still_open[0][2] + 1}, so where the manual is read cannot be vouched for")
    assert len(uses) >= 16 and len(blocks) >= 3, (
        f"expected the manual's sixteen uses in three guarded sections, found "
        f"{len(uses)} in {len(blocks)}")
    unguarded = [n + 1 for n, guarded in uses if not guarded]
    assert not unguarded, (
        f"the manual's text is used outside its guard at line(s) {unguarded}, "
        f"which aborts a run with no spec root under `set -u`")


@pytest.mark.parametrize("text, unguarded", [
    pytest.param(
        'if [ -n "$LANE_MANUAL" ]; then\n'
        'ln_doc="$(cat "$LANE_MANUAL" 2>/dev/null || :)"\n'
        'has "a" "$ln_doc" "x"\n'
        'fi\n'
        'has "b" "${ln_doc}" "y"\n', [5], id="braced-use-after-the-guard"),
    pytest.param(
        'if [ -n "$LANE_MANUAL" ]; then\n'
        '  ln_doc="$(cat "$LANE_MANUAL" 2>/dev/null || :)"\n'
        '  fi\n'
        'has "c" "$ln_doc" "z"\n', [4], id="indented-closing-fi"),
    pytest.param(
        'if [ -n "$LANE_MANUAL" ]; then\n'
        'ss_doc="$(cat "$LANE_MANUAL")"\n'
        'else\n'
        '  has "d" "$ss_doc" "w"\n'
        'fi\n', [4], id="use-in-the-guards-else"),
    pytest.param(
        'if [ -n "$LANE_MANUAL" ]; then\n'
        'if [ -r "$LANE_MANUAL" ]; then ok "r"\n'
        'else bad "r" "no readable file"; fi\n'
        'cat <<EOF\n'
        'fi\n'
        'EOF\n'
        'has "e" "${ln_doc}" "v"\n'
        'fi\n', [], id="nested-if-and-a-heredoc-inside-the-guard"),
])
def test_the_guard_reading_follows_the_nesting_not_a_spelling(text, unguarded):
    """The planted cases the first reading got wrong (a braced use after the
    guard, an indented closing `fi`) and two it must keep right."""
    uses, _blocks, still_open = manual_reads(text.splitlines())
    assert not still_open
    assert [n + 1 for n, guarded in uses if not guarded] == unguarded


def suite_helpers() -> str:
    """The suite's own one-line assertion helpers, verbatim, and a stand-in
    for the `excerpt` its `has` calls."""
    wanted = re.compile(r"^(ok|bad|skip|has|hasnt)\(\) *\{")
    found = [line for line in SUITE.read_text(encoding="utf-8").splitlines()
             if wanted.match(line)]
    assert len(found) == 5, f"expected the suite's five helpers, found {found}"
    return "\n".join(found + ["excerpt() { printf '%.200s' \"$1\"; }"])


@WINDOWS_SKIP
@pytest.mark.skipif(shutil.which("bash") is None, reason="the suite is bash")
def test_the_lane_suites_manual_sections_fail_skip_or_pass_by_name(tmp_path):
    """THE MISSING-MANUAL BRANCH, RUN (#193 item 3; until now only its text
    was checked). The suite's three `$LANE_MANUAL` sections, cut out of it by
    the reading above and run under its own `set -uo pipefail` and its own
    helpers:

      * a manual that is NOT THERE is a FAIL naming the path, in each section
        that reads it — never an empty string the quotes then misread;
      * NO manual (no spec root) is three named skips, and the run reaches
        its end — never `unbound variable`;
      * the run's own manual, where it has one, passes every quote."""
    lines = SUITE.read_text(encoding="utf-8").splitlines()
    _uses, blocks, _open = manual_reads(lines)
    body = "\n".join("\n".join(lines[a:b + 1]) for a, b in blocks)
    script = tmp_path / "manual-sections.sh"
    script.write_text(
        "set -uo pipefail\npass=0; fail=0; skipped=0\n" + suite_helpers()
        + '\nLANE_MANUAL="$MANUAL_UNDER_TEST"\n' + body
        + '\nprintf "END %s passed, %s failed, %s skipped\\n" '
          '"$pass" "$fail" "$skipped"\n', encoding="utf-8")

    def run(manual: str) -> str:
        env = dict(os.environ, MANUAL_UNDER_TEST=manual)
        proc = subprocess.run([shutil.which("bash") or "bash", str(script)],
                              env=env, capture_output=True, text=True,
                              timeout=60, check=False)
        out = proc.stdout + proc.stderr
        assert proc.returncode == 0 and "\nEND " in "\n" + out, (
            f"the manual sections did not run to their end with "
            f"LANE_MANUAL={manual!r}:\n{out}")
        assert "unbound variable" not in out, out
        return out

    missing = tmp_path / "no-spec-leg" / "docs" / "README-lanes.md"
    out = run(str(missing))
    named = out.count(f"no readable file at {missing}")
    assert named == 2 and "\nFAIL " in out, (
        f"a missing manual must FAIL naming {missing} in both sections that "
        f"check it; it was named {named} time(s):\n{out}")
    out = run("")
    assert "END 0 passed, 0 failed, 3 skipped" in out, out
    assert out.count("no spec root in this run") == 3, out
    manual = conftest.ROOTS.root_of("spec")
    if manual is not None:
        out = run(str(manual / "docs" / "README-lanes.md"))
        assert " 0 failed, 0 skipped" in out, out



def test_a_redirected_run_names_its_roots_where_quiet_output_keeps_them(tmp_path):
    """A run whose roots a variable named says them at its foot, under the
    `-q` every CI job and `tests/run.sh` use. The report header that said them
    is dropped by `-q`, so a run pointed at another tree was silent about it
    (lane openRepoTools-3's review of #190, #193 item 6). A run on today's
    layout with no variable prints nothing new."""
    root = assembly(tmp_path / "asm")
    named = nested(tmp_path, {"OPENREPOTOOLS_ASSEMBLY_ROOT": str(root)},
                   README_TEST, "test_repo_hygiene.py")
    assert named.outcome(README_TEST)[0] == "passed", named.output[-2000:]
    assert "openRepoTools test roots" in named.output, named.output[-2000:]
    assert f"assembly: {root.resolve()} (OPENREPOTOOLS_ASSEMBLY_ROOT)" in named.output, (
        named.output[-2000:])
    plain = nested(tmp_path, {}, README_TEST, "test_repo_hygiene.py")
    if conftest.ROOTS.layout == "single" and not conftest.ROOTS.how:
        assert "openRepoTools test roots" not in plain.output, (
            "today's layout, with no variable, printed the roots section:\n"
            + plain.output[-2000:])


def test_a_standalone_code_leg_skips_what_only_the_assembly_carries(tmp_path):
    """A code leg cloned on its own has no README: standalone, the README test
    SKIPS naming the assembly root, which is the courtesy the missing submodule
    gets; composed, the session is REFUSED naming it (exit 4), never a skip."""
    leg = code_leg(tmp_path / "code")
    standalone = nested(tmp_path, {"OPENREPOTOOLS_CODE_ROOT": str(leg)},
                        README_TEST, "test_repo_hygiene.py")
    outcome, message = standalone.outcome(README_TEST)
    assert outcome == "skipped" and "assembly root" in message, (
        f"a standalone code leg's README test {outcome}, not a skip naming the "
        f"assembly root:\n{message}\n{standalone.output[-2000:]}")
    composed = nested(tmp_path, {"OPENREPOTOOLS_CODE_ROOT": str(leg),
                                 "OPENREPOTOOLS_COMPOSED": "1"},
                      README_TEST, "test_repo_hygiene.py")
    assert composed.returncode == 4, (
        f"a composed run with no assembly root exited {composed.returncode}, "
        f"not pytest's refusal (4):\n{composed.output[-3000:]}")
    assert "the ASSEMBLY root is absent" in composed.output, composed.output[-3000:]
    assert "the SPEC root is absent" in composed.output, composed.output[-3000:]
    assert not composed.outcomes, "a refused session ran tests anyway"


#: The command's half of three mixed hygiene tests, and the line each asserts.
COMMAND_HALVES = (
    ("test_the_documents_say_what_bare_park_does_now", "park",
     "PARKED EVERY ESTATE unasked"),
    ("test_the_documents_say_what_status_is_and_is_not", "status",
     "--no-optional-locks"),
    ("test_the_documents_say_what_a_bare_lanes_lists", "openRepoTools",
     "lanes [--all] [--fetch]"),
)


def test_a_standalone_code_leg_still_checks_each_commands_own_half(tmp_path):
    """Where a test reads a command and the documents about it, the command's
    half is asserted FIRST, so a standalone code leg — which skips the
    documents — still checks the command (the #190 review). A leg whose three
    commands lost their lines FAILS those three tests rather than skipping
    them with the documents."""
    leg = code_leg(tmp_path / "code")
    for _, name, line in COMMAND_HALVES:
        path = leg / name
        text = path.read_text(encoding="utf-8")
        assert line in text, f"{name} no longer carries {line!r}; this test is stale"
        path.write_text(text.replace(line, "(removed for the fixture)"),
                        encoding="utf-8")
    run = nested(tmp_path, {"OPENREPOTOOLS_CODE_ROOT": str(leg)},
                 " or ".join(test for test, _, _ in COMMAND_HALVES),
                 "test_repo_hygiene.py")
    for test, name, _ in COMMAND_HALVES:
        outcome, message = run.outcome(test)
        assert outcome == "failure", (
            f"{test} {outcome} on a leg whose {name} lost its line: the "
            f"command's half was not asserted before the documents' skip:\n"
            f"{message}\n{run.output[-2000:]}")


def test_the_pin_checks_read_the_code_roots_own_git_identity(tmp_path):
    """The lockstep check reads `git ls-tree HEAD` IN the code root it is given:
    a code leg whose gitlink disagrees with its pin FAILS it. Red at
    `origin/main`, which read this checkout's gitlink whatever was named."""
    leg = code_leg(tmp_path / "code", repository=True, gitlink="1" * 40)
    run = nested(tmp_path, {"OPENREPOTOOLS_CODE_ROOT": str(leg)},
                 LOCKSTEP_TEST, "test_upstream_pin.py")
    outcome, message = run.outcome(LOCKSTEP_TEST)
    assert outcome == "failure" and "1" * 40 in message, (
        f"the lockstep check {outcome} on a code root whose gitlink is "
        f"{'1' * 40}; it did not read that root:\n{message}\n{run.output[-2000:]}")


def test_the_no_submodule_skip_is_todays_skip_and_composed_refuses_it(tmp_path):
    """A code root whose dependency was never initialized — the empty directory
    a clone without `--recurse-submodules` leaves — SKIPS the three checks of
    the dependency's bytes with today's reason, standalone, while the checks of
    the pin itself still run and pass; composed, the session is refused
    naming the dependency. The worktree's own submodule is never touched."""
    leg = code_leg(tmp_path / "code", repository=True, dependency="empty")
    select = f"{LOCKSTEP_TEST} or {DIGEST_TEST} or {HEAD_TEST}"
    standalone = nested(tmp_path, {"OPENREPOTOOLS_CODE_ROOT": str(leg)},
                        select, "test_upstream_pin.py")
    assert standalone.returncode == 0, standalone.output[-3000:]
    assert standalone.outcome(LOCKSTEP_TEST)[0] == "passed", standalone.output[-3000:]
    for name in (DIGEST_TEST, HEAD_TEST):
        outcome, message = standalone.outcome(name)
        assert outcome == "skipped" and (
            "the pinned openRepoShape is not checked out; run `git submodule "
            "update --init upstream/openRepoShape`") in message, (
            f"{name} {outcome} without the dependency, not today's skip:\n{message}")
    composed = nested(tmp_path, {"OPENREPOTOOLS_CODE_ROOT": str(leg),
                                 "OPENREPOTOOLS_COMPOSED": "1"},
                      select, "test_upstream_pin.py")
    assert composed.returncode == 4, composed.output[-3000:]
    assert "the DEPENDENCY" in composed.output and "is not initialized" in \
        composed.output, composed.output[-3000:]


@NEEDS_UPSTREAM
def test_a_composed_triad_runs_every_check_and_skips_none(tmp_path):
    """THE POSITIVE CONTROL: a fixture triad — an assembly whose HEAD pins a
    code leg and a spec leg at their own HEADs, the dependency checked out at
    its pin — runs the README, manual and pin checks composed, found by
    discovery alone (only the code root is named), and every one PASSES.
    Then one moved gitlink: the spec leg no longer at its pin is refused."""
    code = code_leg(tmp_path / "asm" / "code", repository=True,
                    dependency="clone")
    spec = spec_leg(tmp_path / "asm" / "spec", repository=True)
    root = assembly(tmp_path / "asm", code=code, spec=spec, repository=True)
    env = {"OPENREPOTOOLS_CODE_ROOT": str(code), "OPENREPOTOOLS_COMPOSED": "1"}
    run = nested(tmp_path, env, f"{README_TEST} or {MANUAL_TEST} or upstream_pin",
                 "test_repo_hygiene.py", "test_upstream_pin.py")
    assert run.returncode == 0, run.output[-4000:]
    assert run.outcomes, run.output[-3000:]
    not_passed = {name: o for name, o in run.outcomes.items() if o[0] != "passed"}
    assert not not_passed, f"a composed run did not pass everything: {not_passed}"
    for name in (README_TEST, MANUAL_TEST, LOCKSTEP_TEST, DIGEST_TEST, HEAD_TEST):
        run.outcome(name)
    (spec / "openspec" / "README.md").write_text("# moved\n", encoding="utf-8")
    run_git(spec, "commit", "-q", "-a", "-m", "the spec leg moves off its pin")
    moved = nested(tmp_path, env, README_TEST, "test_repo_hygiene.py")
    assert moved.returncode == 4, moved.output[-3000:]
    assert f"the spec root {spec.resolve()}" in moved.output and \
        "composed acceptance is for the pinned spec leg" in moved.output, (
        moved.output[-3000:])
    assert root.is_dir()


@WINDOWS_SKIP
@pytest.mark.skipif(shutil.which("bash") is None, reason="the wrapper is bash")
def test_the_wrapper_passes_a_relative_root_through_as_an_absolute_one(tmp_path):
    """`tests/run.sh` `cd`s to its own repository before it runs pytest, so a
    RELATIVE root would be read against the code root, not against where the
    caller stood. It is made absolute first; an absolute one and the mode pass
    as they are. The suite is a stub that records its environment, and `pgrep`
    a stub that sees no other run — the real one would see this suite."""
    fakebin = tmp_path / "fakebin"
    fakebin.mkdir()
    log = tmp_path / "suite.env"
    (fakebin / "python3").write_text(
        "#!/bin/sh\nenv | grep '^OPENREPOTOOLS_' > \"$FAKE_SUITE_LOG\"\nexit 0\n")
    (fakebin / "pgrep").write_text("#!/bin/sh\nexit 1\n")
    for name in ("python3", "pgrep"):
        (fakebin / name).chmod(0o755)
    caller = tmp_path / "caller"
    caller.mkdir()
    env = {k: v for k, v in os.environ.items()
           if not k.startswith(("XDG_", "PYTHON", "OPENREPOTOOLS_"))
           and k not in ("PWD", "OLDPWD")}
    env.update(PATH=f"{fakebin}{os.pathsep}{os.environ.get('PATH', '')}",
               TMPDIR=str(tmp_path), XDG_STATE_HOME=str(tmp_path / "state"),
               XDG_CACHE_HOME=str(tmp_path / "cache"), HOME=str(tmp_path / "home"),
               FAKE_SUITE_LOG=str(log),
               OPENREPOTOOLS_ASSEMBLY_ROOT="asm",
               OPENREPOTOOLS_SPEC_ROOT="asm/spec",
               OPENREPOTOOLS_CODE_ROOT=str(tmp_path / "elsewhere"),
               OPENREPOTOOLS_COMPOSED="1")
    proc = subprocess.run([shutil.which("bash") or "bash", str(WRAPPER), "-k", "x"],
                          cwd=str(caller), env=env, capture_output=True, text=True,
                          stdin=subprocess.DEVNULL, timeout=120, check=False)
    assert proc.returncode == 0, proc.stderr
    seen = dict(line.split("=", 1) for line in log.read_text().splitlines())
    assert seen["OPENREPOTOOLS_ASSEMBLY_ROOT"] == f"{caller.resolve()}/asm", seen
    assert seen["OPENREPOTOOLS_SPEC_ROOT"] == f"{caller.resolve()}/asm/spec", seen
    assert seen["OPENREPOTOOLS_CODE_ROOT"] == str(tmp_path / "elsewhere"), seen
    assert seen["OPENREPOTOOLS_COMPOSED"] == "1", seen
    # A QUOTED `~` is the home directory, as conftest's `expanduser` reads it,
    # never a directory named `~` under the caller (#193 item 7).
    env.update(OPENREPOTOOLS_SPEC_ROOT="~/spec", OPENREPOTOOLS_ASSEMBLY_ROOT="~")
    proc = subprocess.run([shutil.which("bash") or "bash", str(WRAPPER), "-k", "x"],
                          cwd=str(caller), env=env, capture_output=True, text=True,
                          stdin=subprocess.DEVNULL, timeout=120, check=False)
    assert proc.returncode == 0, proc.stderr
    seen = dict(line.split("=", 1) for line in log.read_text().splitlines())
    assert seen["OPENREPOTOOLS_SPEC_ROOT"] == f"{tmp_path / 'home'}/spec", seen
    assert seen["OPENREPOTOOLS_ASSEMBLY_ROOT"] == str(tmp_path / "home"), seen


# --- the resolver, asked directly -------------------------------------------

def test_todays_single_tree_is_every_root_at_once(tmp_path):
    """Today's layout: the code root carries the spec trees beside the
    commands, so it answers for the assembly and the spec leg too, and a
    document test reads exactly the file it always read."""
    code = code_leg(tmp_path / "repo", single=True)
    roots = conftest.resolve_roots({}, code)
    assert roots.refusal() is None, roots.refusal()
    assert (roots.layout, roots.assembly, roots.spec) == ("single", None, None)
    assert roots.root_of("assembly") == roots.root_of("spec") == roots.code
    assert roots.path_for("README.md") == roots.code / "README.md"
    assert roots.path_for("docs/README-lanes.md") == roots.code / "docs/README-lanes.md"
    assert [role for role, _ in roots.tracked_roots()] == ["code"]


def test_a_mounted_code_leg_finds_its_assembly_and_spec_leg(tmp_path):
    code = code_leg(tmp_path / "asm" / "code", repository=True)
    spec = spec_leg(tmp_path / "asm" / "spec", repository=True)
    root = assembly(tmp_path / "asm", code=code, spec=spec, repository=True)
    roots = conftest.resolve_roots({}, code)
    assert roots.layout == "leg"
    assert roots.assembly == root.resolve() and roots.spec == spec.resolve()
    assert roots.path_for("README.md") == root.resolve() / "README.md"
    assert roots.path_for("AGENTS.md").parent == root.resolve()
    assert roots.path_for("docs/README-lanes.md") == spec.resolve() / "docs/README-lanes.md"
    assert roots.path_for(".gitattributes") == code.resolve() / ".gitattributes", (
        "the line-ending rule is the code root's: git does not read a "
        "superproject's attributes into a submodule")
    assert roots.path_for("tests/run.sh") == code.resolve() / "tests/run.sh"
    for own in ("LICENSE", ".gitignore"):
        assert roots.path_for(own) == code.resolve() / own, (
            f"{own} is the code root's: the code leg carries its own (T006's "
            f"code-0001), and it is the copy that governs the leg's files")
    assert [role for role, _ in roots.tracked_roots()] == ["code", "assembly", "spec"]


def test_a_directory_that_does_not_mount_the_code_root_is_not_its_assembly(tmp_path):
    """An assembly above a code root that it does not record as its code
    gitlink is somebody else's: discovery answers no rather than borrow it."""
    root = assembly(tmp_path / "asm")              # no repository, no gitlink
    code = code_leg(root / "code")
    assert conftest.resolve_roots({}, code).assembly is None


def paired_triad(tmp_path: Path, *, spec_worktree: bool = True):
    """An assembly with both legs mounted, and a feature's paired worktrees
    `worktrees/001-feature/{code,spec}` made from those legs, as T006's root
    guidance and the code leg's AGENTS.md lay them out."""
    code = code_leg(tmp_path / "asm" / "code", repository=True)
    spec = spec_leg(tmp_path / "asm" / "spec", repository=True)
    root = assembly(tmp_path / "asm", code=code, spec=spec, repository=True)
    feature = root / "worktrees" / "001-feature"
    run_git(code, "worktree", "add", "-q", "-b", "001-feature",
            str(feature / "code"))
    if spec_worktree:
        run_git(spec, "worktree", "add", "-q", "-b", "001-feature",
                str(feature / "spec"))
    return root, feature


def test_a_paired_feature_worktree_finds_its_assembly_and_its_own_spec(tmp_path):
    """The paired layout: a feature's code worktree at
    `<assembly>/worktrees/<feature>/code` reads the assembly's README and its
    own spec worktree's manual. Discovery returned None there, so every
    document test would skip in a feature worktree after Gate C (lane
    openRepoTools-3's review of #190, #193 item 5)."""
    root, feature = paired_triad(tmp_path)
    roots = conftest.resolve_roots({}, feature / "code")
    assert roots.refusal() is None, roots.refusal()
    assert roots.assembly == root.resolve(), roots.describe()
    assert roots.spec == (feature / "spec").resolve(), roots.describe()
    assert roots.path_for("README.md") == root.resolve() / "README.md"
    assert roots.path_for("docs/README-lanes.md") == (
        feature / "spec" / "docs" / "README-lanes.md").resolve()
    assert "paired feature worktree" in roots.how["assembly"], roots.how
    # Without a spec worktree of its own, the feature reads the mounted one.
    root2, feature2 = paired_triad(tmp_path / "two", spec_worktree=False)
    roots2 = conftest.resolve_roots({}, feature2 / "code")
    assert roots2.spec == (root2 / "spec").resolve(), roots2.describe()


def test_only_the_two_designed_places_are_an_assemblys_code(tmp_path):
    """Discovery stays bounded to the mount and the paired worktree: a
    repository that is not the code leg's, at the paired path, is not found,
    and neither is the code leg's own worktree anywhere but `worktrees/`."""
    root, feature = paired_triad(tmp_path)
    # A repository of its own with a history of its own: built from the same
    # files, but never holding the commit the assembly pins (a fixture leg
    # committed in the same second with the same tree would BE that commit).
    stranger = code_leg(root / "worktrees" / "002-stranger" / "code")
    (stranger / "STRANGER").write_text("not the code leg\n", encoding="utf-8")
    run_git(stranger, "init", "-q")
    run_git(stranger, "add", "-A")
    run_git(stranger, "commit", "-q", "-m", "a history of its own")
    assert conftest.resolve_roots({}, stranger).assembly is None, (
        "a checkout that does not hold the pinned commit was taken for the leg")
    elsewhere = root / "elsewhere" / "001-feature" / "code"
    run_git(root / "code", "worktree", "add", "-q", "-b", "elsewhere",
            str(elsewhere))
    assert conftest.resolve_roots({}, elsewhere).assembly is None, (
        "a worktree outside worktrees/ was taken for a paired one")
    # Found is not accepted: a feature's commits are not the pinned leg, and
    # a composed run there is refused for that, naming it.
    run_git(feature / "code", "commit", "-q", "--allow-empty", "-m", "feature work")
    composed = conftest.resolve_roots({"OPENREPOTOOLS_COMPOSED": "1"},
                                      feature / "code").refusal()
    assert composed and "composed acceptance is for the pinned code leg" in composed, (
        composed)


def test_a_stale_manifest_under_a_feature_does_not_hide_its_assembly(tmp_path):
    """An ancestor carrying the assembly's two markers but failing the rest
    (not a repository's top level, no gitlink) is skipped, not the end of the
    search: discovery stopped there and found nothing (Copilot round 2 on
    #195)."""
    root, feature = paired_triad(tmp_path)
    (feature / "contracts").mkdir()
    (feature / "contracts" / "code-pin.yaml").write_text(
        LEG_PIN.format(role="code", commit="0" * 40, digest="0" * 64), encoding="utf-8")
    (feature / "project.yaml").write_text(PROJECT_YAML, encoding="utf-8")
    roots = conftest.resolve_roots({}, feature / "code")
    assert roots.assembly == root.resolve(), roots.describe()


def test_a_stray_spec_tree_beside_a_paired_code_worktree_is_not_its_spec(tmp_path):
    """The feature's own spec worktree must be a repository holding the spec
    commit the assembly pins, as the paired code worktree must. A plain `docs/`
    there is not it, and the mounted spec leg is read instead (Copilot round 2
    on #195)."""
    root, feature = paired_triad(tmp_path, spec_worktree=False)
    stray = spec_leg(feature / "spec")              # files only, no repository
    assert (stray / "docs" / "README-lanes.md").is_file()
    roots = conftest.resolve_roots({}, feature / "code")
    assert roots.spec == (root / "spec").resolve(), roots.describe()
    assert roots.how["spec"] == "the assembly's spec leg", roots.how


def test_the_variables_name_the_roots(tmp_path):
    code = code_leg(tmp_path / "code")
    root = assembly(tmp_path / "elsewhere" / "asm")
    spec = spec_leg(tmp_path / "spec")
    roots = conftest.resolve_roots({"OPENREPOTOOLS_CODE_ROOT": str(code),
                                    "OPENREPOTOOLS_ASSEMBLY_ROOT": str(root),
                                    "OPENREPOTOOLS_SPEC_ROOT": str(spec)},
                                   tmp_path / "unused")
    assert roots.refusal() is None, roots.refusal()
    assert (roots.code, roots.assembly, roots.spec) == (
        code.resolve(), root.resolve(), spec.resolve())
    assert roots.how == {"code": "OPENREPOTOOLS_CODE_ROOT",
                         "assembly": "OPENREPOTOOLS_ASSEMBLY_ROOT",
                         "spec": "OPENREPOTOOLS_SPEC_ROOT"}
    assert roots.dependency == code.resolve() / "upstream" / "openRepoShape"


@pytest.mark.parametrize("variable, value, said", [
    ("OPENREPOTOOLS_COMPOSED", "yes", "is neither 1"),
    ("OPENREPOTOOLS_CODE_ROOT", "missing", "is not a code root"),
    ("OPENREPOTOOLS_ASSEMBLY_ROOT", "missing", "is not an assembly root"),
    ("OPENREPOTOOLS_SPEC_ROOT", "missing", "is not a spec root"),
])
def test_a_variable_that_names_the_wrong_thing_is_refused_in_either_mode(
        tmp_path, variable, value, said):
    """A root named by hand that is not that root is a typo, not a layout:
    refused before any test, standalone as well as composed."""
    code = code_leg(tmp_path / "repo", single=True)
    target = value if variable == "OPENREPOTOOLS_COMPOSED" else str(tmp_path / value)
    refusal = conftest.resolve_roots({variable: target}, code).refusal()
    assert refusal and said in refusal and variable in refusal, refusal


@pytest.mark.parametrize("variable, role", [
    ("OPENREPOTOOLS_SPEC_ROOT", "SPEC"),
    ("OPENREPOTOOLS_ASSEMBLY_ROOT", "ASSEMBLY"),
])
def test_composed_names_the_value_a_rejected_root_was_named_by(
        tmp_path, variable, role):
    """A root that was NAMED and refused is absent because of that value,
    and the composed refusal says so: never that its variable "is unset", or
    that there is "no" such variable, when the run set it (#193 item 15, lane
    openRepoTools-2's reading of the composed-run logs). The refusal itself was
    right before; only its words were wrong."""
    code = code_leg(tmp_path / "asm" / "code", repository=True)
    spec = spec_leg(tmp_path / "asm" / "spec", repository=True)
    assembly(tmp_path / "asm", code=code, spec=spec, repository=True)
    wrong = tmp_path / "not-a-root"
    wrong.mkdir()
    refusal = conftest.resolve_roots(
        {"OPENREPOTOOLS_COMPOSED": "1", variable: str(wrong)}, code).refusal()
    assert refusal, "a named root that is not one must be refused"
    absent = [part for part in refusal.split("; ")
              if part.startswith(f"the {role} root is absent")]
    assert absent, refusal
    assert f"{variable} names {wrong}" in absent[0], absent[0]
    for misnomer in (f"{variable} is unset", f"no {variable}"):
        assert misnomer not in refusal, (
            f"the refusal says {misnomer!r} although the run named "
            f"{variable}={wrong}:\n{refusal}")


def test_composed_names_every_absent_context(tmp_path):
    leg = code_leg(tmp_path / "code", repository=True, dependency="empty")
    refusal = conftest.resolve_roots({"OPENREPOTOOLS_COMPOSED": "1"}, leg).refusal()
    assert refusal is not None
    for context in ("the ASSEMBLY root is absent", "the SPEC root is absent",
                    "the DEPENDENCY", "is not initialized"):
        assert context in refusal, refusal
    assert conftest.resolve_roots({}, leg).refusal() is None, (
        "standalone, the same leg is a layout and not a refusal")


def test_composed_refuses_a_code_leg_off_its_pin_or_with_changes(tmp_path):
    code = code_leg(tmp_path / "asm" / "code", repository=True)
    spec = spec_leg(tmp_path / "asm" / "spec", repository=True)
    assembly(tmp_path / "asm", code=code, spec=spec, repository=True)
    (code / "upstream" / "openRepoShape").mkdir(parents=True, exist_ok=True)
    for probe in ("scripts/repo_shape.py", "templates/workspace-root/README.md"):
        target = code / "upstream" / "openRepoShape" / probe
        target.parent.mkdir(parents=True, exist_ok=True)
        target.write_text("# a probe\n", encoding="utf-8")
    composed = {"OPENREPOTOOLS_COMPOSED": "1"}
    assert conftest.resolve_roots(composed, code).refusal() is None, (
        conftest.resolve_roots(composed, code).refusal())
    (code / "park").write_text("#!/usr/bin/env bash\n# edited\n", encoding="utf-8")
    refusal = conftest.resolve_roots(composed, code).refusal()
    assert refusal and "has changes to tracked files" in refusal, refusal
    run_git(code, "commit", "-q", "-a", "-m", "the code leg moves off its pin")
    refusal = conftest.resolve_roots(composed, code).refusal()
    assert refusal and "composed acceptance is for the pinned code leg" in refusal, refusal


def test_composed_refuses_a_leg_whose_status_cannot_be_read(tmp_path):
    """A `git status` that fails is not a clean one (Copilot on #190): a code
    leg at its pin whose index is unreadable is refused, naming it, rather
    than accepted because no changes were printed."""
    code = code_leg(tmp_path / "asm" / "code", repository=True)
    spec = spec_leg(tmp_path / "asm" / "spec", repository=True)
    assembly(tmp_path / "asm", code=code, spec=spec, repository=True)
    for probe in ("scripts/repo_shape.py", "templates/workspace-root/README.md"):
        target = code / "upstream" / "openRepoShape" / probe
        target.parent.mkdir(parents=True, exist_ok=True)
        target.write_text("# a probe\n", encoding="utf-8")
    composed = {"OPENREPOTOOLS_COMPOSED": "1"}
    assert conftest.resolve_roots(composed, code).refusal() is None
    (code / ".git" / "index").write_bytes(b"not an index")
    refusal = conftest.resolve_roots(composed, code).refusal()
    assert refusal and "answered no `git status`" in refusal, refusal


def test_composed_refuses_a_pin_that_names_another_commit_than_the_gitlink(tmp_path):
    """The leg pin's `commit:` and the gitlink are one invariant. A pin moved
    off the gitlink, with the gitlink and the leg's HEAD still agreeing, was
    accepted (`refusal()` was None) while `scripts/validate-pins.py` exits 1 on
    the same tree (Copilot round 2 on #190, #193 item 4). Refused now, naming
    the pin, the gitlink and the mount."""
    code = code_leg(tmp_path / "asm" / "code", repository=True)
    spec = spec_leg(tmp_path / "asm" / "spec", repository=True)
    root = assembly(tmp_path / "asm", code=code, spec=spec, repository=True)
    for probe in ("scripts/repo_shape.py", "templates/workspace-root/README.md"):
        target = code / "upstream" / "openRepoShape" / probe
        target.parent.mkdir(parents=True, exist_ok=True)
        target.write_text("# a probe\n", encoding="utf-8")
    composed = {"OPENREPOTOOLS_COMPOSED": "1"}
    assert conftest.resolve_roots(composed, code).refusal() is None, (
        conftest.resolve_roots(composed, code).refusal())
    pin = root / "contracts" / "code-pin.yaml"
    head = run_git(code, "rev-parse", "HEAD")
    pin.write_text(pin.read_text(encoding="utf-8").replace(head, "1" * 40),
                   encoding="utf-8")
    refusal = conftest.resolve_roots(composed, code).refusal()
    assert refusal and "contracts/code-pin.yaml pins " + "1" * 40 in refusal, refusal
    assert f"records {head}" in refusal and "one invariant" in refusal, refusal


@pytest.mark.parametrize("variable, markers", [
    ("OPENREPOTOOLS_CODE_ROOT", ("openRepoTools", "contracts/openreposhape-pin.yaml")),
    ("OPENREPOTOOLS_ASSEMBLY_ROOT", ("contracts/code-pin.yaml", "project.yaml")),
])
def test_a_directory_spelled_like_a_marker_is_not_one(tmp_path, variable, markers):
    """A root's markers are files. A tree whose `openRepoTools` or
    `project.yaml` is a DIRECTORY is not that root, and naming it is refused
    like any other wrong tree; with `exists()` it passed (#193 item 4)."""
    code = code_leg(tmp_path / "repo", single=True)
    fake = tmp_path / "fake"
    for marker in markers:
        (fake / marker).mkdir(parents=True)
    refusal = conftest.resolve_roots({variable: str(fake)}, code).refusal()
    assert refusal and variable in refusal and "is not a" in refusal, (
        f"{variable} naming a tree of marker-named directories was accepted: "
        f"{refusal}")


def test_this_runs_roots_are_the_ones_it_is_running_with():
    """This session's own roots: coherent, and — composed — complete. The
    composed half is the same check `pytest_configure` refused on, held as a
    test so a green composed run lists it."""
    roots = conftest.ROOTS
    assert roots.refusal() is None, roots.refusal()
    assert REPO == roots.code == conftest.CODE_ROOT
    for marker in ("openRepoTools", "contracts/openreposhape-pin.yaml"):
        assert (roots.code / marker).exists(), marker
    if roots.composed:
        assert roots.assembly is not None and roots.spec is not None
        assert roots.dependency_initialized()
