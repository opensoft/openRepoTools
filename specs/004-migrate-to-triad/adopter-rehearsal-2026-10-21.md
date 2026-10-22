# Gate C rehearsal, run D, at the frozen source — October 21, 2026

**Task:** T003–T005's rehearsal evidence for Gate C, under
[#186](https://github.com/opensoft/openRepoTools/issues/186).
No task is checked complete by it.
**Tool:** openRepoShape `190133d5e704e380c430f87ca9c4e31746de0012`, the commit
its tag `v1.1.0` peels to (the clone's `HEAD`, `v1.1.0^{commit}` and the
checkout agree at setup, and `190133d` is on its `main`), with
`git-filter-repo` 2.47.0 (`git filter-repo --version` printed `a40bce548d2c`)
(`runD/run-header.txt`, `logs/shape-clone.log`, `logs/setup-filter-repo.log`).
**Source:** main `33ce26dffc5286e68f1d29ab5c6458edef0330c0`, the EXPECT, read
with `git ls-remote` at 2026-10-21T16:22:30Z just before cloning. It is #299's
squash of `076fa70` on `50d05d4`, lane 1's `composed.yml` runner pin, merged
2026-10-21T14:07:41Z (GitHub's `merged_at`; lane 3's LANDED line is stamped 14:08:04Z):
the last landing before the freeze. The clone has 156
commits and 200 files, and its `upstream/openRepoShape` gitlink and
`contracts/openreposhape-pin.yaml` both name `190133d`
(`logs/source-clone.log`, `<S>.observe/before-setup.txt`).
**Authority:** Brett Heap's words, as lane 1's coordinator relayed them (`<P>/PLAN.md`
10.4), each a single turn, timed by that turn in lane 1's session transcript:
"yes to e2 and D7, names only" (2026-10-20T22:56:11Z); "yes to one rehearsal and
e4; include P7, P8, P10" (2026-10-21T10:31:16Z); "yes to the link-only 70 fallback"
(2026-10-21T13:43:26Z). The start, which lane 1's freeze notice quotes: "continue;
start D when the freeze is ready" (2026-10-21T13:55:01Z). All four turns carry
`promptSource: suggestion_accepted` with `turnOrigin: human` in that transcript. The house
test (lane 2, #186 6327441086) has four conditions: each turn answers a question lane 1
asked just before it, none repeats an earlier text, no other user turn follows within 3
minutes, and no py-bench lane can type into lane 1's pane. A message typed while the
session is busy is recorded as a `queued_command` attachment of human origin, not as a
`user` entry, so the third condition counts both; the earlier checks counted only `user`
entries (lane 2, 6327441086; lane 3, 6332521834 and 6333819643). The transcript was
read 3 minutes either side of each turn, and the one `queued_command` within 3 minutes
of the e2 and D7 turn, 49.0 s after it, is of `task-notification` origin, not human,
so it is not counted. By turn, on the first condition (lane 3, #186 6332521834 and
6333819643, and lane 1's transcript) and the third (lane 2, #186 6333755295): the e2 and
D7 turn fails the first, because lane 1's message just before it (2026-10-20T22:38:30Z)
names those answers as still needed but asks no question; the e4 turn meets the first,
because lane 1's last message before it (2026-10-20T23:39:23Z) asked three explicit
questions, and fails the third, because Brett's own message "usage reset, resume all. …"
follows it by 31.6 s, recorded as a queued message at 10:31:47Z, and the same text reached
lane 2's pane at 10:31:43Z; the link-only turn meets all four, after one explicit question
(13:34:15Z); and the start turn fails the first, because the status message before it
(13:44:21Z) asked nothing. The other three turns meet the third condition, and all four
meet the second and the fourth: each is the only user turn with its text, so none repeats
an earlier one, and no py-bench lane can type into lane 1's pane. The e2 and D7 turn came
9 s after lane 5's submitted-suggestion incident, in which a turn that repeated Brett's
earlier word was lane 5's own input suggestion, submitted when lane 3 typed into its pane
(2026-10-20T22:56:02Z; corrected in lane 5's log at 23:04:15Z; lane 5, #186 6332551316).
At Gate C Brett is asked to confirm three turns in a word: the e2 and D7 turn, the e4 turn
and the start turn.
**Private receipt:** `rehearsal-d`, with its observation directory
`rehearsal-d.observe`, under `work-20261021`.

Below, `<S>` is the sandbox `rehearsal-d`, `<S>.observe` its observation
directory, `<P>` the prep directory `rehearsal-prep` (`PLAN.md` and `scripts/`),
`<W>` the work directory `work-20261021`, and `~` the lane's home. Each figure
names its file relative to `<S>`, `<S>.observe` or `<P>`.

**The freeze (e2).** Lane 1's notice, #186 comment 6320876769, was created
2026-10-21T16:21:27Z by GitHub's stamp, before the first observation (16:22:00Z on the
bench's clock). The bench's clock runs ahead of GitHub's: the call that posted the notice,
`XdFtRAfU` in the extract under The STOP gate, ran from 16:21:34Z to 16:21:39Z on it, so
the order holds on either clock. Its heading says
"16:3xZ", which was lane 1's slip (the post was drafted before it went up): GitHub's
time stands, and the comment is left unedited, because an edit re-fires other lanes'
`since=` watchers. It says "Main stays at `33ce26d` until the cutover", and its
rules hold until lane 1 posts D's end:

- nothing lands on main, no `adopt/*` ref is pushed, no leg repository is created,
  and no HOLD or LANDING line is written, because D's observations fail closed on
  a new one;
- on any bench, no `openRepoTools --install` or `--uninstall`, no workBenches
  setup, and no edits to `~/.claude/skills`, `~/.claude/commands`,
  `~/.claude-profiles/shared/` or `~/.claude/settings.json`;
- on cloud-bench, relaunch only pinned (`CLAUDE_BIN` at the 2.1.306 executable,
  `DISABLE_AUTOUPDATER=1`) and install nothing into `~/.local/bin`;
- Brett's ruling: a P10 exit 70 whose difference is only the `claude` or `codex`
  link row is recorded as attributed.

The register's last HOLD, LANDING and LANDED lines on `opensoft/openRepoTools main`
before it are lane 3's for #299 (14:05:43Z to 14:08:49Z, `<S>.observe/before-setup.txt`),
and lane 1 asked every lane to land nothing more at 14:12Z (#186 6318207326).

**Reviewed bytes.** `<P>/scripts/REVIEWED.sha256` as D ran it (13 lines, sha256
`fcfe0653d2f08d04e4a81252ca3c4e41dfccd57b92697d0bbbeec50b3929d9b4`, kept since
2026-10-22T04:24:09Z as `REVIEWED.sha256.v8-20261021`; that path now holds the post-D
round's `410890f7…`) was written by lane 1 on 2026-10-21 at 16:20:45Z from the bytes the
reviews name, and `setup_d.sh` refuses (65) any script not on record there.
`<S>/logs/setup-scripts.log` checks each copy, `observe_d.sh` and setup's own bytes
against it: 12 `reviewed` lines, setup's own line, no MISMATCH. These are the 13 rows
(`<P>/scripts/REVIEWED.md` names each review):

| File | sha256 | Review that covers these bytes |
| --- | --- | --- |
| `setup_d.sh` | `20d82fda…` | Lane 3, #186 6320744628 (round 5c, 2026-10-21T16:16Z): READY, no MUST, no SHOULD; earlier bytes 6315175076. Not copied: it checks its own bytes |
| `env-d.sh` | `e5c12db0…` | Lane 3, 6315175076 (rounds 5, 5b) and 6320744628 (5c): read unchanged since round 4, READY |
| `run_rehearsal_d.sh` | `4ec81498…` | Lane 3, 6320744628: READY, no MUST, no SHOULD (NITs 131–135 and 141–144 left for after D) |
| `observe_d.sh` | `a157c257…` | Lane 3, 6315175076 and 6320744628: read unchanged since round 4, READY. Not copied: it runs from `<P>/scripts` |
| `resolve_plan_d.py` | `89bb3490…` | Lane 2, #186 6290828597: READY at these bytes. The first round, 6289380127, read earlier bytes: READY after fixes, no MUST, three SHOULDs; the sandbox re-run under fix round 4's caller is 6297569490 |
| `publish_plan_d.py` | `2d40606f…` | Lane 2, 6290828597: READY at these bytes. The first round, 6289380127, read earlier bytes: READY after fixes, one SHOULD; the sandbox re-run under fix round 4's caller is 6297569490 |
| `independent_accounting_d.py` | `e0160b89…` | Lane 2, 6290828597: READY at these bytes. The first round, 6289380127, read earlier bytes: READY after fixes, one MUST (the review's only one), three SHOULDs; the sandbox re-run under fix round 4's caller is 6297569490 |
| `decisions-new-paths.json` | `5a5a50f1…` | Lane 2, 6290828597: READY at these bytes (lane 1's D2 of 2026-10-20, amended at 11:1xZ). The first round, 6289380127, read earlier bytes: READY; the sandbox re-run under fix round 4's caller is 6297569490 |
| `suites_d.sh` | `c452ab6a…` | Lane 3, 6319760887 (post-run rounds 4b and 4c, 2026-10-21T15:29Z): READY, no MUST, no SHOULD (NITs 121–123 left for after D) |
| `install_d.sh` | `7bf6781c…` | The same |
| `wheel_d.sh` | `fe196121…` | The same |
| `rollback_d.sh` | `bbb11d6f…` | The same |
| `provenance_d.py` | `22b29dde…` | Lane 3, 6314817974 (round 4): READY, no MUST, no SHOULD, at these bytes; rounds 4b and 4c did not change it |

Lane 1 ran D on round 5c's reviewed bytes, not on lane 3's suggested round 5d (#186
6320876769). NIT 142 cannot fire in D: the real git configuration holds no URL with
a query (`runD/realcfg-names.txt` has no `?`). NIT 141 needs a second stage
invocation while `stage2` runs, and `runD/exits.txt` has one `stage2 begins` line. The
NITs went into the post-D round, now installed (Remaining gates).

**Run D supersedes nothing.** Runs A (`c4864ac`) and B (the repin candidate `e43b243`)
stand as recorded in [adopter-rehearsal-2026-10-07.md](adopter-rehearsal-2026-10-07.md),
and run C (`837928a`) in
[adopter-rehearsal-2026-10-08.md](adopter-rehearsal-2026-10-08.md). Run D is the one
rehearsal Brett approved for the cutover: one `execute`, in a fresh sandbox, with the
tool at v1.1.0 and the source frozen at `33ce26d`. Every check on its outputs can be
repeated; a second `execute`, in a new sandbox, happens only on Brett's word. Its
plan, as published, stays with this record on an evidence branch until the root-split
PR (e2), so the mapping on main stays run C's plan: the link is
[main's plan at `33ce26d`](https://github.com/opensoft/openRepoTools/blob/33ce26dffc5286e68f1d29ab5c6458edef0330c0/openspec/changes/migrate-to-triad/adoption-plan.yaml)
(sha256 `5321b736…`), because on this branch the path opens D's plan. Like run C, it is
kept host-local outside every repository. Clone
paths, local remote URLs, exact command lines and complete logs stay in the private
receipt.

## Setup

Lane 1's observation `before-setup` and `setup_d.sh` ran 2026-10-21T16:22:00Z to
16:22:51Z and ended `setup ok`, exit 0 (`<W>/d-operator-log/act0-act1.log`).

- **Scripts:** setup copied 11 files into `<S>/scripts`: the six recipe files,
  decisions file included, and the five post-run scripts. None was absent. Each copy
  has the sha256 the table above lists (`logs/setup-scripts.log`).
- **filter-repo (e4):** `git-filter-repo` 2.47.0 in a private venv, `<S>/venv`. The
  bench has no `ensurepip` (the first observation records `python3-venv` and
  `python3.12-venv` as not installed, and `import ensurepip` exiting 1), so the venv
  was made with `--without-pip`. The wheel is run C's, sha256
  `2cd04929b9024e83e65db571cbe36aec65ead0cb5f9ec5abe42158654af5ad83`: `sha256sum -c`
  OK, installed with `--no-index --no-deps`, EXIT 0 (`logs/setup-filter-repo.log`).
- **Tool and source:** a fresh clone of openRepoShape detached at `190133d`, equal to
  `v1.1.0^{commit}`, clean, and a bare mirror of it for the recursive clones
  (`logs/shape-clone.log`). A fresh single-branch clone of main, one worktree, `HEAD`
  equal to the EXPECT: MATCH, `origin` still the public GitHub URL
  (`logs/source-clone.log`).
- **Inputs:** seven patches pinned from `33ce26d` itself, no override,
  `PIN_NOTE_ACK: none`, each at the digest the recipe expects: assembly-0001
  `2ec48bbf…`, code-0001 `74b98ff9…`, spec-0001 `c11070f0…`, T007 `67d8e7ce…`, T009's
  caps `2dd4aac2…`, T010's assembly job `60245cb9…` and T010's code-leg workflow
  `1406ead3…`. `SHA256SUMS` (`37256f12…`) is anchored and the directory is read-only
  (`logs/inputs-patches.log`).
- **Transport:** of the stages, by the recipe only setup reaches the network (NET 1–4):
  `git ls-remote` and the clones of the tool's tag and of the source, and
  `pip download --require-hashes` of the two release locks, 7 wheels each, EXIT 0 twice
  (`logs/wheels-net4.log`). The observations are separate: they read GitHub and the
  register with `gh api` and `git ls-remote`. After setup, `scripts/env-d.sh` limits git
  to local files (`GIT_ALLOW_PROTOCOL=file`), and `gh`, `curl` and `wget` are shims that
  refuse and log; `logs/network-shim-calls.log` is empty (0 bytes) after stage 4. The
  shims and that setting stop only `gh`, `curl`, `wget` and git's non-file transports:
  Python, pip and raw sockets are not stopped, so none of this says that a run used no
  network. The recursive clones reached code's nested openRepoShape through the local
  mirror.
- **Isolation:** `scripts/env-d.sh` points `GIT_CONFIG_GLOBAL` at `home/.gitconfig`, an
  empty file (0 bytes), and sets `GIT_CONFIG_NOSYSTEM=1`. `logs/setup-env.log` records the
  environment's names after it and the inherited names left over, which are only those
  it sets itself. Its `git config --show-origin --list`, headed "isolated: expect
  nothing", printed 160 rows, all `file:.git/config`. Acts 0 and 1 ran from lane 1's tool
  shell, whose working directory is the shared openRepoTools checkout (PLAN 10.1 named
  none), so the rows are that checkout's own local configuration, read only. No row came
  from a global or system file, which is what the check is for. After D,
  `git --no-optional-locks status --short` there prints 0 lines and no work-tree file is
  newer than `<S>.observe/before-setup.txt` (16:22:12Z); this record's writer read both
  again at 21:01Z. The post-run starts used `cd /tmp`: starting the stage acts from a
  neutral directory too was a NIT for the post-D round, which put `cd /tmp` into PLAN 10.1.

## Mapping (T003)

Since run C's source the tree gained 80 files (120 to 200) and two top-level paths,
`pyproject.toml` and `src/` (#228). The plan has 36 entries where run C's reference
plan has 34.

- **`plan`** (exit 0) read 200 files and 156 commits and left 18 questions.
  **`resolve_plan_d.py`** (exit 0) checked the reference plan's sha256 first,
  `5321b73626e7426b2985ba4e5aa804114919fd2f73540a5b8de0303b495e0084`, and applied 22
  resolutions verbatim, all from the reference plan: 18 answer the tool's questions
  (all to code), 3 move `commands/`, `contracts/` and `skills/` from spec to code,
  and 1 confirms `ideation/` in spec; 21 code, 1 spec (`runD/resolve.log`,
  `runD/resolve-report.json`). The decisions file's two entries, `pyproject.toml` and
  `src/` to code, were kept (`runD/decisions-effective.log`: "kept ['pyproject.toml',
  'src/']") and not needed: the tool puts both in code with no question (rules
  `code-build-manifests` and `code-source-and-tests`, confidence high), so neither is
  among the 18 `generated_questions` of `resolve-report.json`, and all 22 `applied`
  entries are `from: reference`. The file's other parts did apply: its
  `__extra_follow_ups__` entry is the extra follow-up, and its `__retire_hand_follow_ups__`
  entry's text is absent from the plan.
- **Follow-ups:** the tool's 32 over the resolved entries, 9 of the reference's 10
  hand-written ones (item 6, "Regenerate this preliminary plan after planning lands
  and baseline freeze; …", retired byte for byte; one count edited, "120-file" to
  "200-file"), and the decisions file's one extra, on the wheel's `license-files` and
  T006 code-0001: 42 in all. After resolution the plan assigns spec 108 files
  (1,694,221 bytes), code 86 (7,604,620), root 6 (69,263), none unresolved.
- **The diffs:** `runD/plan-vs-generated.diff` (26 hunks) is what resolve changed in
  the tool's plan: 18 `leg: null` and 3 `leg: spec` lines become `leg: code`, 22
  `resolution:` lines are added, the follow-ups are re-derived (55 become 42) and
  the summary moves (spec 115 to 108 files, code 61 to 86, unresolved 18 to 0).
  `runD/plan-vs-reference.diff` (29 hunks) holds the kinds of change PLAN section 4
  lists: the header block, `generated_on`, `source:` (commit `33ce26df…`, 200 files,
  9,368,104 bytes, 156 commits, `cloned: false`), the pins comment, `.github/` (4
  files, rule `consensus`, medium), `.gitmodules` and `upstream/` (rule
  `ambiguous-gitmodules`), the two new entries, the shortened `reason:` of `contracts/`,
  `docs/`, `openspec/` and `specs/` (4 entries, 8 lines: #628), new counts,
  `review_required: true` where a question was asked, the follow-ups and the summary, and
  two comments that list omits: the default-rule comment (2 lines) and the `cloned:`
  comment (3 lines).
- **`check`** of the executed plan, and **`check-published`** of the published copy:
  each exit 0, `plan ok`, 0 FINDING lines and one NOTE (it did not ask whether the url
  of `upstream/openRepoShape`, a network url, answers). The two logs are equal byte
  for byte. The published copy differs from the executed plan only by its header,
  `local_path: .`, and the closing `planning_status: rehearsal-input-not-cutover` and
  `execution_authorized: false`; their sha256 are `84198e59…` and `45b0ec8d…`
  (`runD/check.log`, `runD/check-published.log`, `runD/plans.sha256`). The published
  plan's header says the new top-level paths were "answered as
  scripts/decisions-new-paths.json of the private receipt records". That sentence is
  the publish step's fixed text and overstates D's case: resolve applied none of the
  file's path answers, though both say code, as the tool did. The header also drops run
  C's "Gate B remains open (T006-T011)". Both were NITs for the post-D round, whose
  `publish_plan_d.py` fixes them.
- **`check-realcfg`** (ledger I4, D7, names only), `check` of the published copy under
  the real shell's git configuration, started with `D7_REALCFG=1`: exit 0, no FINDING
  or REFUSED code kept (`runD/check-realcfg.log`). `runD/realcfg-names.txt` (12 lines,
  726 bytes, sha256 `15d9494e…`) holds 12 name rows from one file, the global
  configuration (7 `credential`, 2 `url`, 2 `user`, 1 `safe`; 10 distinct names), no
  value and no redaction mark. The names stay out of this record. Two rows hold an at
  sign: the 2 `url` rows, in scp form (user name and host, no scheme, no password), which
  count 2 below and the redaction, both keyed on `://`, cannot match. Lane 3 asked for two
  counts, with no name printed (#186 6323118228): lines with a byte outside printable
  ASCII and blanks, and url rows whose userinfo is not redacted. Lane 1 ran both at
  18:11:29Z, before this record: **0 and 0**, with a planted control (a 0xff byte and a
  url with userinfo) giving 1 and 1 (#186 6323149947). `XDG_CONFIG_HOME` was unset in
  the real shell, so git read `~/.config` (`runD/run-header.txt`).
- Stage 1 left the source clone's status and refs unchanged (`runD/source-status.diff`
  and `runD/source-refs-stage1.diff` empty). `runD/exits.txt` has `plan`, `resolve`,
  `check`, `publish`, `check-published` and `check-realcfg` at EXIT 0, 16:23:21Z to
  16:23:26Z, and `STAGE1-PASSED` was written at 16:23:26Z.

## The STOP gate

The gate observation passed (16:24:57Z, `<S>.observe/gate.txt`): origin main `33ce26df…`
FROZEN, both leg repositories absent on GitHub (HTTP 404), no `adopt/` ref on origin, no
register line for `opensoft/openRepoTools main` since the first observation, and the
shared checkout's `HEAD`, status and refs as at the start. `STAGE1-REVIEWED` was made at 16:25:11Z, once it had passed and its
last line was `verdict OK` (`<W>/d-operator-log/act3-gate.log`).

**What lane 1 read before the mark** is in the extract of its session transcript,
`<W>/d-operator-log/act9-transcript-extract-1619-1634.txt` (sha256 `309d978e…`, read
only; its header says 17:16:22Z, the file's time before a header edit at 17:18:01Z, its
mtime, which gives the digest; call `CDdSNjEi`'s result header has no time there, the
transcript has 16:28:41.154Z): every Bash call from 16:19:50Z to 16:34Z with its result.
The gate reads are its calls `tvZ1mEmK` (16:23:38Z, stage 1's output), `M7cWkvuf`
(16:23:51Z, the FINDING counts and the real-config names by count), `h5YC1X5L`
(16:24:03Z, `check-realcfg.log` and the answered-paths and submodules counts), and
`zrRZP87o` (16:24:23Z) and `8HwsX145` (16:24:37Z), on the published plan; `eYWgV1do`
(16:24:57Z) is the gate act itself. Lane 1 checked:

- 22 resolutions; a header naming `33ce26d`, `190133d` and Run D; the `pyproject.toml`,
  `src/` and `.github/` rows; `ambiguous-gitmodules` for `.gitmodules` and `upstream/`;
- 19 answered rows and 1 submodule row; `review_required` on exactly the 18 question
  entries; 42 follow-ups, the extra one last and the retired one absent; a summary root
  of 6;
- `check` and `check-published` at 0 FINDING, `check-realcfg` at exit 0, and
  `realcfg-names.txt` by counts only.

Checked as PLAN 10.1 says: `gate.txt` is a plain file, newer than `STAGE1-PASSED`;
line 1 is `# 2026-10-21T16:24:57Z gate`; line 2 names `observe_d.sh` `a157c257…`, `<S>`
and `33ce26df…`, where `a157c257…` is the `observe_d.sh reviewed` value of
`logs/setup-scripts.log`; it has one `origin main` line, `-> FROZEN`, no FINDING, and
one verdict line, `verdict OK`, last. `before-setup.txt` and `after-execute.txt` carry
the same line 2.

| Observation | Start | HOLD, LANDING, LANDED or WITHDRAWN lines on `opensoft/openRepoTools main` in its window | Verdict |
| --- | --- | --- | --- |
| `before-setup` | 16:22:00Z | 18 in the 24 hours before (no earlier phase), 9 of them a HOLD or a LANDING; the last of those is a LANDING at 14:07:21Z, and the last line a HOLD RELEASED at 14:08:49Z | OK |
| `gate` | 16:24:57Z | 0 since 16:22:00Z | OK |
| `after-execute` | 16:25:51Z | 0 since 16:24:57Z | OK |
| `end` | 20:40:44Z | 0 since 16:25:51Z | OK |

## Run D — main `33ce26d`

`stage2`, the one execute, began 16:25:23Z. `execute` with `--local-remote-dir`,
`--work-dir` and `--yes` exited **0** at 16:25:30Z and printed
`adoption verified: every source path is in exactly one place`
(`runD/exits.txt`, `runD/execute.log`).

| Source accounting (the standard's table) | Run D | Run C |
| --- | ---: | ---: |
| Spec | 108 | 65 |
| Code | 86 | 49 |
| Assembly root | 6 | 6 |
| Dropped | 0 | 0 |
| Total | 200 | 120 |

The standard reported 18 new assembly paths (manifest, pins and shape files), five
collisions written beside the originals under `shape/` (nothing overwritten), and, in
the root `.gitattributes`, a `text eol=lf` line appended for each of 9 pinned copies
(#471), none of its own lines changed.

| Disposable repository | Commit | Kept commits |
| --- | --- | ---: |
| Spec | `de756faf8797ea4ee598bf2a9cee84f2b358fa67` | 69 |
| Code | `d9e7d568011b339e8d4bb87f3f83f58ec653794a` | 145 |
| Assembly split | `92e4e4172779a226a5e98efa6a3c671baa43ba79` | 157 on its branch |

(`runD/results.txt`.) The split's only parent is `33ce26d`, so its branch holds the
source's 156 commits and itself, as `refs/heads/adopt/three-repo-shape` in the source
clone. Spec took 4 plan paths and code 26. Spec's tree digest is
`29c982db162c36aa9fd15d4a5f6c880086559c01a25cc9b1dfa95b5531512421` and code's
`68a05297b1e0dee588c5fa5b1456e465d26717ff5136a023e52bc4f351c55f9b` (the split's
`contracts/*-pin.yaml`, read with `git show`).

- **Commit maps:** filter-repo's two maps, kept under `runD/wd-execute`, are listed in
  `runD/commit-maps.sha256` (code `6dc62d31…`, spec `9370ae10…`). That file's sha256,
  `dec7000db3afd0530be22f82dd91d1262737d0f4cc97f8d5ce30d53d6110df50`, is the single
  anchor line of `runD/exits.txt` (line 9), and `STAGE2A-PASSED` holds the same line.
  The file and both maps are read-only. `v1`, `t006-1` and `cand-v0` each checked the
  anchor first (`commit-maps-check.txt`: one anchor line, equal values, both maps OK).
- **The source clone:** `git status --porcelain --ignored` listed nothing before or
  after `execute` (`runD/source-status-before-execute.txt` and
  `runD/source-status-execute.diff`, both empty), `main` stayed at `33ce26d`, and the
  only change in its refs is the new split ref (the diff at the end of
  `runD/results.txt`).
- `STAGE2A-PASSED` was written at 16:25:31Z.

## After execute

**Observation.** `after-execute` (16:25:51Z) passed: origin main FROZEN at
`33ce26df…`, still no leg repository and no `adopt/` ref on GitHub (`execute` made its
legs only in the sandbox), no register line for that repository since the gate. The
prerequisites block is identical in `before-setup`, `gate` and `after-execute`.

**stage2v, attempt v1** (16:26:08Z to `STAGE2-PASSED` at 16:26:19Z, every command at
EXIT 0 in `runD/exits.txt`):

- **Accounting:** `independent_accounting_d.py` matched path, mode, object type and
  object ID for all 200 entries of `ls-tree -r 33ce26d`: 108 spec, 86 code, 6 root;
  zero missing, duplicate or misplaced owners, no plan-ambiguous entry, no leg extras
  (spec tree 108 entries, code 86), no root shadow. The gitlink `upstream/openRepoShape`
  at `190133d` has one owner, code. The root `.gitattributes` is the source blob
  `3560973e9d45` plus the #471 block of 9 lines, `a9ac338e09f6`: MATCH. `RESULT PASS`
  (`runD/v1/accounting.log`), which lists 22 assembly additions: the 18 new paths plus
  `.gitattributes`, `.gitmodules` and the two leg mounts.
- **Records:** the split's `project.yaml` holds the `submodules` block at 1 row and the
  `answered_paths` block at 19, each MATCH against `resolve-report.json`'s preview
  (`runD/v1/records.log`); the #471 line and the NEXT line are in `eol-line.txt` and
  `next-line.txt`.
- **Recursive clone** through the local mirror: spec `de756faf8797`, code `d9e7d568011b`,
  code's nested openRepoShape at `190133d`, the contract's pin
  (`runD/v1/verify-clone-heads.txt`). The pinned checkout's own `repo_shape.py`
  recomputed the `sorted-ls-tree-r-v1` digest
  `7a66972c7de193c050f77f97bffa13d8543c28d74f61ea210644e65aa3f37912`, equal to the
  contract's (`runD/v1/pin-digest.log`).
- **`scripts/bootstrap.py`** printed `bootstrap ok`; the naming, manifest and pins
  validators (`manifest ok: openRepoTools (openrepotools), 3 legs`, `pins ok`, 11
  copied shape files match their digests) and `make validate` exited 0. Every work
  tree was clean afterwards, ignored files included (`runD/v1/status-after-validate.txt`).
- **OpenSpec** (`runD/v1/openspec.log`): at the spec leg, 1.6.0 passes all 6 changes;
  1.2.0, the `openspec` first on `PATH`, passes 3 and fails 3
  (`interactive-lane-name-repair`, `migrate-to-triad`, `release-tags-pypi`; exit 1). At
  the assembly root both say "No items found to validate." and exit 0.

**stage3, the T006 trial** (`runD/t006-1`, 16:26:44Z to 16:26:45Z). Its inputs were
checked against `SHA256SUMS` first (all seven OK). Five patches, in scratch clones of
the legs and the split, each `git apply --check -v` then `git am --3way`, each at
EXIT 0 (`summary.txt` and the `.check.log` and `.am.log` of each): `assembly-0001` and
`t010-assembly-exact-pin-job` on the split (the second creates `composed.yml`),
`code-0001` and `t010-code-leg-tests-workflow` on the code leg, `spec-0001` on the spec
leg. No hunk was rejected; two applied at an offset: `spec-0001`'s hunk 1 of
`docs/README-claude-current.md` (8 lines) and the code-leg workflow patch's hunk 3 of
`tests.yml` (3 lines). `summary.txt` notes that this patch expects a `tests.yml`
blob `2cfa173` and the code leg has `46feb68`. Not applied here: assembly-0002 and
assembly-0003 (stage 4's `bump-leg.py` makes the bumps); not tried here: the T009 caps
and T007 patches (stage 4 applies them).

## The candidate (stage 4, v0)

`runD/cand-v0`, 16:27:07Z to `STAGE4-PASSED` at 16:27:17Z. It copied D's two leg remotes
into bare repositories of its own, fetched the split into a third, applied the patches
in clones, and pushed only to those copies (`push -q`: the three `push-*.log` are
empty). Every step exited 0 in `runD/exits.txt`, and `inputs.txt` records
`assembly-0001.patch` and `t009-assembly-caps.patch` "applied, as setup pinned it".

| Repository | Candidate | Past D's |
| --- | --- | --- |
| Spec leg | `f41ac906b8f707fd8969e307b658d79aa3827f83` | 1 commit, spec-0001 (70 in all) |
| Code leg | `56142ed741f9cb1d66c62d5d19b3ebf9620a500d` | 3: code-0001, T010's workflow, the T009 caps (148 in all) |
| Assembly, `candidate-v0` | `c67b0e6838c2c1ae25733df2c0b8316bb7e72452` | 5 past the split: assembly-0001, T010's exact-pin job, T007's front door, and two `bump-leg.py` bumps (spec to `f41ac906b8f7`, `2833b34`; then code to `56142ed741f9`, `c67b0e6`), each bump with the trailer `Rehearsal: D v0` (the three patch commits have none) |
| Nested `upstream/openRepoShape` | `190133d5e704e380c430f87ca9c4e31746de0012` | none |

The candidate's pin tree digests are spec `bc2d1813…`, code `45b3f125…` and the shape
and code's openRepoShape pin `7a66972c…`; its `AGENTS.md` has 354 lines and `README.md`
529, the caps T009 sets (`runD/cand-v0/identities.txt`). A fresh recursive clone of
`candidate-v0` checked out all four, `scripts/bootstrap.py` printed `bootstrap ok` (both
legs on `main`, tip equal to the pin), `make validate` exited 0, and `composed.yml`'s
step "every context the composed run claims is here", run as written, exited 0. Every
tree was clean (`status.txt`; `status-tracked.txt`, `diff-check-*.log` and
`listing.diff` empty), D's own outputs and the source clone's refs were unchanged, and
the shim log was empty. The assembly's remote in the candidate's copies holds `main` at
the split `92e4e41…` and `candidate-v0`. D's remotes are read again at the end, below. The
inventory of this stage's patches and commits, for Gate B row 40, is the appendix at the
end of this record.

## The post-run scripts

Each was started detached from lane 1's shell, with the operator's redirect
`runD/<script>-v0.out` that PLAN 10.2's start lines give. Each start is `cd /tmp &&` and
then PLAN 10.2's line for the script, byte for byte (compared by program), headed
`/usr/bin/setsid -f /usr/bin/env -i HOME="$HOME" PATH=/usr/bin:/bin LANG=C.UTF-8`; P10's
adds ` --original-repo` and the shared checkout after `"$S"`, where its header places
options. PLAN 10.2's grep for the five installer variables printed nothing (rc 1) at
16:27:42Z, before the first start, and again before P10's start (calls `tMh5TFaE`,
`hVfNmWJN`, `xmH4S3m1`, `oqqXFS3r`, `CDdSNjEi` and `ky2SHRDr` of lane 1's transcript
extract, at 16:27:42Z, 16:27:47Z, 16:28:06Z, 16:28:16Z, 16:28:36Z and 16:32:56Z). A
script's exit is the last `exit N` in its attempt's `pid.txt`; its receipt was verified in
the attempt with `sha256sum -c --strict RECEIPT.sha256`. The window is `attempt.txt`'s
`started` line to `pid.txt`'s `finished` line, all 2026-10-21Z. The arguments are each
`attempt.txt`'s `argv`: P3 `v0 --state-root` a state root under the system temporary
directory, `must`; P4, P5 and P7 `v0`; P10 `--original-repo` the shared checkout. Lane 1's
milestone, #186 comment 6321243191 (2026-10-21T16:38:23Z), agrees with this record's stage
times and with the PASS counts of P4, P7 and P10, and says the freeze still held; its
16:26:03Z for `after-execute` is that observation's end (16:25:51Z here is its start).

| Script | Attempt | Window | Exit | PASS / FAIL / NOTE | Receipt (`sha256sum -c --strict`) | Surfaces |
| --- | --- | --- | --- | --- | --- | --- |
| P4, `install_d.sh` | `install-v0/a1` | 16:28:17Z to 16:28:55Z | 0 | 36 / 0 / 0 | exit 0, 95 rows OK | unchanged |
| P7, `rollback_d.sh` | `rollback-v0/a1` | 16:28:36Z to 16:29:05Z | 0 | 47 / 0 / 0 | exit 0, 96 rows OK | unchanged |
| P10, `provenance_d.py` | `provenance/a1` | 16:32:56Z to 16:33:02Z | 0 | 22 / 0 / 2 | exit 0, 15 rows OK | unchanged |
| P3, `suites_d.sh`, `must` | `suites-v0/a1` | 16:27:48Z to 19:57:58Z | **1** | jobs: 2 GREEN, 2 RED | exit 0, 32 rows OK | unchanged |
| P5, `wheel_d.sh` | `wheel-v0/a1` | 16:28:08Z to 18:20:03Z | **2** | 10 / 0 / 1 SKIP | exit 0, 36 rows OK | unchanged |

No script exited 70, 71 or 72: the exits are 0, 0, 0, 1 and 2. In a script, 70 means a
watched surface changed, 71 that the surfaces could not be watched, 72 that there is no
sealed record; in `observe_d.sh`, 71 is origin main MOVED and 72 a leg repository EXISTS
(PLAN 10.1, 10.2). For each of the five attempts, and for the two SMOKE attempts under P3,
the shim log and `surfaces.diff` are empty, and `SUMMARY.txt` says "real surfaces:
unchanged". P3's 1 is its two RED jobs; P5's 2, which its header defines as no FAIL but a
step SKIPPED, is the skipped pipx step. Neither is the watch's 70.

**P4, the install comparison** (`install-v0/a1`; seeds s1 and s2, the `p11` seed, a
pre-#237 workstation, not selected). Each seed ran, in a disposable home inside the
attempt, main's `./openRepoTools --install` (A), the candidate's (B), the candidate
again (B2), the checkout absent (D) and main's again over B's home (C): 18 checks per
seed, all PASS. Every install exited 0; the candidate's `--version` exited 0 and `nope`
exited 2. The candidate's install equals main's (the whole home by path, type, mode and
sha256, and the receipt's name, destination and sha256 columns, 29 rows; only its UTC
column may differ); the candidate run again changes nothing and prints no `installed at`
or `updated at` line; rollback by reinstall (C) restores main's install; A and B each
say "17 of 17 placed". `settings.json` is byte-identical after A, B, B2 and C: with the gate open
(s1) 2 of our hook entries are merged, with it closed (s2) none, the seeded guard entry
being removed. With both trees moved away, the 17 installed commands give the same
`--help` output (and `openRepoTools --version`) and exit status as with them present.
B reports that the code is mounted at `openRepoTools-code` `56142ed741f9…`, every payload
file checked against that commit and nothing fetched.

**P7, the rollback drills** (`rollback-v0/a1`; drills a, b1 and b2; 47 PASS: 23, 14 and 9,
and one check that `candidate-v0` descends from the source commit). The drills read D's
repositories only, through bundles and clones. Every push goes to a throwaway bare
repository the attempt made (`b1/<mode>/live.git`, `b2/live.git`), and each refused a
force push that rewinds `main` and a delete of it (`b1-ff-deny.log`,
`b1-squash-deny.log`, `b2-deny.log`).

- **(a) Restore from preserved artifacts:** six bundles (the two execute remotes, the
  three candidate remotes, the source clone), each verified and listed in
  `bundles/SHA256SUMS`, each restored into a fresh bare repository whose `for-each-ref`
  listing equals the original's, connectivity ok. `candidate-v0` and the split were
  cloned recursively from the restored copies (a marker branch only they hold was
  served, so the originals were not read); `bootstrap.py` and `make validate` exited 0
  in both; the restored candidate's four identities equal stage 4's clone's line for
  line (root `c67b0e6838c2`) and the restored split's three heads equal
  `v1/verify-clone-heads.txt`.
- **(b1) A post-merge revert, twice:** `main` at the source commit, then `candidate-v0`
  merged by fast-forward (`main` 6 commits past the source) and reverted over the range
  (6 commits, no conflict); and merged by squash, the repository's own policy
  (1 commit, `783e959f6b6b`) and reverted. Each revert was pushed as a fast-forward,
  `main^{tree}` is the source commit's tree, `15a58404a93b`, and the merged `main`
  stays an ancestor: the revert was added, nothing was rewound.
- **(b2) A pin-bump rollback:** `bump-leg.py` moved the code leg `56142ed741f9` to a new
  leg commit `0e9cb613f658` in one commit and back in one, each a fast-forward; the tree
  after the bump back is the tree before the bump forward (`7d86b1214742`), the gitlink
  is `56142ed741f9` again, and `contracts/code-pin.yaml` is byte-identical. A second bump
  forward was undone by `git revert`, with `main^{tree}` the tree before the first bump:
  four pushes, none a rewrite.

**P10, provenance** (`provenance/a1`; `--original-repo` pointed read-only at the shared
checkout; no `--expect-spec`, because the anchors check `results.txt`'s counts; 22 PASS,
2 NOTE; tables in `provenance.md`).

- **Join:** the anchor in `exits.txt` and in `STAGE2A-PASSED` matches
  `commit-maps.sha256` (`dec7000db3af…`) and each leg's head is the one the split pins
  and `results.txt` records (spec 69 commits, code 145). Every spec-leg commit, 69 of
  69, and every code-leg commit, 145 of 145, joins to an original through its commit
  map, with each changed path's blob and mode equal to the original's (spec 200 paths
  ok, code 611, 0 bad), every path assigned to its leg by the plan, each parent's
  original an ancestor of the commit's original, the same author date, author and
  subject on the original, and the map and that metadata naming the same original.
- **Documents:** 91 files under `openspec/` and `specs/`, in 12 groups, each introduced
  and last changed by a commit that has an original.
- **Hash resolution (NOTE):** 648 distinct hex tokens in those documents (558 with a
  letter a to f). By the file's stated rule, 400 are not an openRepoTools commit here, 17
  are openRepoShape's, 143 resolve only in the original repository and 88 in the source's
  main history; 46 resolve in the spec leg itself, which the file flags as unexpected.
  Lane 2 reads them as earlier runs' spec-leg commits that this deterministic `execute`
  made again (`03818f50c581`, `0c2b499dc1b4` and `2374d2ec8f8f` are in D's spec leg, absent
  from the source clone and cited in `root-guidance-2026-10-08.md`; #186 6327441086). The
  file says its classes follow its own rule and are not comparable with the earlier
  record's figures.
- **Recount (NOTE)** of cross-leg citations in feature 004's working files (40 files):
  by directory entries only, 306 mentions by lines in 34 files (380 by occurrences);
  with the distinctive file names, 435 in 35 (591); with every code-leg entry, the upper
  bound, 1,063 in 37 (1,500). Of the 11 per-file counts the earlier record lists, 7 equal
  the first rule's by lines (5 by occurrences), and 1 equals each of the other rules'.

### P3, the suites (`suites-v0/a1`)

Exit **1**, 16:27:48Z to 19:57:58Z. Its `pytest-version.txt` reads
`pytest 7.4.4 (python3 = /usr/bin/python3)`: run.sh found no repository venv (no log holds
its "runs from the repository venv" line), so the suite ran under the system's Python and
pytest. The state root was `rehearsal-d-state0` under the system temporary directory (23
characters with `/tmp/`), which gives run.sh a predicted TMPDIR of 70 (`suites-v0.out`).

| Job | Verdict | Seconds | Result |
| --- | --- | ---: | --- |
| `upstream-pin` | GREEN | 20 | 15 tests, 0 failed, 0 skipped |
| `composed` | **RED** | 6584 | 3009 tests: 4 failed, 6 skipped; started 16:28:13Z at a load average of 63.28 |
| `refusals` | GREEN | 144 | 6 of 6 broken layouts refused as expected, each exit 4; cases 1 and 5 say "a named root is never replaced by a found one" (#193 item 15) |
| `standalone` | **RED** | 5854 | 3009 tests: 1 failed, 33 skipped; started 18:20:23Z at a load of 3.89 |

**The failures** (5 results, 4 tests; `composed.log`, `standalone.log` and the junit files):

- **(a) `test_repo_hygiene::test_no_committed_file_names_a_host_absolute_path`, composed
  only.** Its four offenders are the rehearsal's own local URLs: lines 3 and 6 of the
  assembly root's `.gitmodules` (D's local leg remotes) and lines 15 and 33 of its
  `shape/README.md` (a `git clone --recurse-submodules` of D's local source clone). They
  come from the tool: with `--local-remote-dir`, openRepoShape `190133d`'s `execute` writes
  the local remotes and source path there (`adopt-project.py:10670-10671`, `_remote_urls` at
  `:10734`, `:10749`, `:11921`; `templates/assembly-root/README.md:15,33`), and without it
  `https://github.com/opensoft/` URLs (`:10741`). Lane 3's run of the test on a copy of
  `cand-v0/clone`, as the composed job runs it, failed on exactly these four lines, and with
  the cutover's URLs in them gave `1 passed, 3008 deselected`, no other offender and 0 shim
  calls, on lane 3's bench with pytest 9.1.1 (#186 6327470307). The rule never matches
  these `https://` URLs (`tests/test_repo_hygiene.py:2592-2617`), so local remotes outside a
  home or the bench root would turn the test green and prove nothing (lane 2).
- **(b) `test_lane_helpers_suite::test_the_lane_helper_suite_passes`, in both jobs,** one
  case each time, "…with clause (c)'s directory and window in the tail, for the person
  reading the row" (composed 4890 passed, 1 failed; standalone 4872 passed, 1 failed, 3
  skipped). The suite's text: "expected to contain [; dir …/projects/repoA; window ]", and
  the row's cell it got ends `; dir …/projects/repoA; ...`, with no window: `lane-start`
  cuts the stamp line at 230 characters (`cut_to_line`, `lane-start:3762-3771`), and the
  case's HOME is under `mktemp -d`, so the stamp grows with run.sh's TMPDIR. Lane 1's record
  writer, lane 2 and lane 3 each recomputed the cut: through `; window ` it is 230 characters
  at a TMPDIR of 69 (a pass) and 231 at 70, and under a C locale, where the em dash counts
  3, it fails from 68. **This is not a condition of the rehearsal.** The case is F3 of r2,
  the Gate B candidate of record (`candidate-2026-10-09.md:261-262`),
  `tests/test_lane_helpers.sh:1272` (`repoA-1`), which #215 left when it closed #180 (it
  moved only `repoA11b`); r2's F4 case, `:8551-8552`, fails from 71 (lane 3). CI's
  `exact-pins` job (T010; `composed.yml:106` in the candidate) runs
  `bash code/tests/run.sh -rs` with no `XDG_STATE_HOME`, at a TMPDIR of 65 plus the pid's
  digits: 69 at four (a pass, no margin), 70 at five (D's failure). "About 72", in PLAN 10.2
  and `suites_d.sh`'s header, was wrong. Tracked as #304.
- **(c) two `test_claude_current` cases, composed only:**
  `test_a_native_another_launch_finished_while_this_one_waited_is_read_again` (it asserts
  "updated by another launch" in stderr, which says only "updating the native install
  toward 2.1.284 … updated") and
  `test_a_copy_ahead_of_npm_that_appears_during_the_wait_is_ahead` (exit 1: "no runnable
  Claude Code was found by absolute path … the update lock … was not free within 4s").
  Both are lock-timing races with a lock holder of 2 s and 1.5 s. Both passed in
  standalone and in `s2`, composed's other 99 `test_claude_current` tests passed, and
  composed began at a load average of 63.28. The load was already 62.04 at P3's own start
  (`attempt.txt`, 16:27:48Z), before D's own P5, P4 and P7 started (16:28:08Z to
  16:28:36Z), and `composed.log:4`'s 5- and 15-minute averages (61.25 and 46.68) show it
  predates them. Tracked as #305.

**The skips,** from `composed.xml` and `standalone.xml` (function names without their
`test_`). The 6 of composed are among standalone's 33 (its 11th to 16th): five
`test_package` wheel
tests, "OPENREPOTOOLS_TEST_WHEEL is unset"
(`wheel_payload_is_the_commits_blobs_byte_for_byte_and_mode_for_mode`,
`wheel_modules_are_the_commits_own`,
`wheel_dist_info_is_the_five_names_with_the_commits_license`,
`wheel_holds_its_member_list_and_nothing_else`,
`wheel_payload_members_are_payload_names_and_the_pin_both_ways`; P5 runs them), and
`test_precision_90a_96`'s `a_count_that_cannot_be_made_is_a_line_over_the_cap[UTF-8]`
("only a byte count past 240 reaches the `wc` recount"). Standalone has no assembly or
spec root and skips 27 more:

- 9 `test_install_payload_source` composed-acceptance cases:
  `r01_composed_the_documented_one_liners_resolve_through_the_root_entry_point`
  (`[openRepoShape]`, `[gh]`), `r01_composed_the_root_entry_point_delegates_locally`,
  `r01_composed_a_signal_reaches_the_implementation_and_its_temporaries_go`,
  `r08_composed_the_root_entry_point_refuses_a_pin_its_gitlink_disagrees_with` (`[gh]`,
  `[curl]`), `r14_composed_acceptance_requires_the_nested_dependency`,
  `r15_composed_the_root_entry_points_pin_reader_is_the_implementations` and
  `r15_composed_the_root_entry_point_parses_and_uses_nothing_bash_3_2_lacks`;
- 11 that need the assembly root's `README.md`: `test_openrepotools_command`'s
  `the_help_and_the_readme_say_the_mode_the_receipt_is_born_at`, and ten of
  `test_repo_hygiene`'s: `the_readme_prints_the_install_line_the_pointer_prints`,
  `the_readme_also_carries_the_gh_api_form`,
  `the_readme_carries_the_two_line_onboarding_chain`,
  `no_document_offers_a_windows_powershell_twin`,
  `the_documents_say_what_bare_park_does_now`,
  `the_documents_say_what_status_is_and_is_not`,
  `the_documents_say_the_sweep_skips_a_root_without_the_overlay`,
  `the_documents_say_what_a_bare_lanes_lists`, `readme_is_short_enough_to_be_read` and
  `readme_says_what_a_release_is_and_offers_no_package_route`;
- 7 more in `test_repo_hygiene`: 3 need its `AGENTS.md` (`agents_md_names_the_pin_rules`,
  `agents_md_is_short_enough_to_be_read`,
  `the_suite_wrapper_takes_one_lock_and_names_it_where_agents_read_it`), 1 its `CLAUDE.md`
  (`claude_md_points_at_agents_md`), and 3 the spec root's `docs/README-lanes.md`
  (`the_directory_precedence_states_every_rung_it_implements`,
  `the_exit_3_documentation_agrees_with_the_die_message_it_describes`,
  `the_manual_offers_the_fork_act_and_not_a_kill`).

**Two SMOKE attempts diagnose the failures.** `suites_d.sh` marks each SUMMARY "SMOKE, NOT
EVIDENCE", and they stand beside P3's results, never in place of them. Each receipt
verifies (15 rows OK), `surfaces.diff` is empty, and each reads P3's pytest line.

| Attempt | Selection (`composed`) | State root, predicted TMPDIR | Window | Result |
| --- | --- | --- | --- | --- |
| `s1` | the lane-helper suite case | `rds2` (9 characters with `/tmp/`), 56 | 20:00:06Z to 20:39:25Z | GREEN: 1 passed in 2357 s, exit 0 |
| `s2` | the hygiene case and the two timing cases | `rehearsal-d-state1` (23 with `/tmp/`, as P3's), 70 | 20:00:30Z to 20:39:47Z | RED: 2 passed, 1 failed in 12.81 s, exit 1 |

`s1` passing says (b) is the length. In `s2` both timing cases pass, but its start load of
3.70 was read at 20:00:31Z, before its wait for the pytest lock (its pytest began at
20:39:34Z, after `s1` ended), so its cases ran with no reading; the stronger evidence for
(c) is standalone, which passed both at a start load of 3.89. The hygiene case fails in
`s2` with the same four offenders, which says (a) is deterministic, from the local URLs. A
first start at P3's own state root was
refused (`runD/suites-v0.out`), because that root was not empty: P3's tests had left
`lanes-index.lock` and `lanes-index.status.json` in it (under the system temporary
directory, not a real surface). P3 and `s1` left their roots, as their notes say; nothing
was removed.

What D shows: P3 is RED for three reasons. (a) is the rehearsal's own local URLs, shown
absent with the cutover's URLs (lane 3's run, above). (c) is load on two timing cases
(#305). (b) is a case #215 left, which CI's `exact-pins` job can hit (#304): it is not a
condition of the rehearsal, and it is not shown absent at the cutover. D has no green
`composed` run.

### P5, the wheel (`wheel-v0/a1`)

Exit **2**, 16:28:08Z to 18:20:03Z; its header defines 2 as "no FAIL but a step was
SKIPPED". Ten steps PASS and one is SKIP (`steps.tsv`, `SUMMARY.txt`):

- **clone** (the code leg at `56142ed741f9`, the assembly's pin) and **venv** (the build
  lock by hash, `--no-index`); **build-a**, **build-b** and **one-file**: the package job's
  two builds give one file, `openrepotools-0.0.0-py3-none-any.whl`, sha256 `b93503b1…`,
  byte for byte; **content**, the package job's own check verbatim: 32 members against
  `HEAD`, 0 problems; **release**: `python -m build --wheel --no-isolation` from a
  `git archive` is build a, byte for byte;
- **package-tests**: `test_package.py`, `test_package_stamp.py` and `test_install_pipx.py`
  against the built wheel, through `tests/run.sh`: 285 passed (116.52 s of pytest, after a
  wait for the pytest lock behind P3 from 16:31:03Z; the step ended 18:19:56Z);
  **zero-skip**: 285 tests, 0 skipped, 0 failed, 0 in error; **control**: the raw leg
  (`d9e7d56`, no LICENSE) is refused by the content check (rc 1), and the `-k dist_info`
  test fails on it, as it must;
- **pipx is SKIP**: "/usr/bin/python3 has no ensurepip, so pipx cannot create its shared
  libraries (python3-venv is not installed); use --python with an interpreter that has
  it". PLAN's P5 line passes no `--python`.

**pipx rests on CI's `package` job, not on D.** Main's CI run at `33ce26d` (run
39614104431, a push created 14:07:44Z) is `success`, and its `package` job's pipx steps (8
to 11) are each `success`: "pipx from its hash lock", "install the wheel with pipx", "the
unstamped --version, line for line" and the `--install` step beside pipx's link. That job
runs Python 3.9.25 and pipx 1.11.1 from the lock, on the single repository's `tests.yml`
(blob `46feb68`), not on D's candidate, and installed main's own wheel, `c23aebce…`, not
D's `b93503b1…` (both 1,078,902 bytes; lane 2 finds them equal but for timestamps, from
different `SOURCE_DATE_EPOCH` values, #186 6327441086). The candidate code leg's
`tests.yml` (blob `a24d126`) has the same four steps and a byte-identical `package` job,
which only the code leg's own CI can run. That is enough for row 33 (its ledger evidence
is P5); for row 34 pipx first runs on the candidate in that CI, after Gate C, which needs
Brett's acceptance (lane 3).

What D's record says of P3 and P5, whatever their results:

- **pytest** is the system's, with no `--pytest-wheels` and no `--pytest-sha256sums`
  (`attempt.txt` of both), so no pytest hash was recorded. P3's `pytest-version.txt` reads
  `pytest 7.4.4 (python3 = /usr/bin/python3)` and P5's reads `pytest 7.4.4`, not the
  8.3.4 CI pins: the isolated HOME hides the user-site pytest the real HOME has
  (`suites-v0.out`, WARNING; `pytest-setup.log`), and run.sh found no repository venv (see
  P3). D and main's CI collect the same 3,009 tests, and CI's two `tests` jobs, at 8.3.4,
  are green (lane 3). P5 ran Python 3.12.3 with pip 24.0, where CI runs Python 3.9.
- **The wheel build** is `--no-index`, but pip's isolated build installs the build's own
  dependencies (hatchling and what it needs) from the find-links directory with no hash
  check. Only the venv's install of the lock is hash-checked.
- **No claim of a run without the network** is made for either (Setup, Transport).

**What did not run in D.** P3's job word was `must`, jobs 1–4 (the table in its section;
`attempt.txt`); its job 5, no-submodule, runs only when it is named, and D did not name
it; P9, lane 2's matrix rerun, does not run in D. Both follow Brett's "include
P7, P8, P10". This record does not say that D ran either. P7, P8 and P10 are the optional
evidence that does run in D. What Gate C's two rows rest on instead:

- **Row 31 rests on main's CI at `33ce26d`** (run 39614104431) and D's runs, not on r2's
  242-skip classification (`candidate-2026-10-09.md:224-242`, over `run-53-r2-nosub.log`),
  which is of a suite of 1,416 tests; D and CI collect 3,009. The `tests-no-submodule` job
  (`-rs`) has 2050 passed and 959 skipped. Lane 3 classified the 959 (#186 6327470307),
  lane 2 parsed the log on its own (6327803546), and the job log repeats it: 884 the
  documented no-submodule skip (the pinned openRepoShape is not checked out), 60 zsh absent
  on the runner, 9 composed acceptance, 5 `OPENREPOTOOLS_TEST_WHEEL` unset, 1 the
  byte-count case. The `tests` job (plain `-q`, no skip list: 2934 passed, 75 skipped) has
  the other four classes' 75, so job 5 adds only the 884; the 717 more than r2's 242 are
  +666 submodule-gated tests, +2 composed-acceptance tests and +66 conditional skips, minus
  17 (documents now resolving to the code root). With D's refusals (6 of 6) and
  standalone's skip list, both lanes' view is that row 31 needs no job 5; the row is
  Brett's call at Gate C.
- **Row 27 rests on lane 2's T008 matrix, not on "15/15, final at `13cc752`".** Its runs are
  four comments: 6073209094, an interim on `2411f40` (the 15/15); 6088812080, the final at
  `13cc752`, with seven open items; 6103618033 at `cddd1f7`; and 6152491855, lane 2's last
  run, R4, at #191's `8246983` (landed as `a74c7fc`), unchanged from `cddd1f7`, with 341
  verdicts. R4 measured `a74c7fc`'s installer, blob `7aa697c`; D ships `ca4fc44`, four
  installer commits later (#209, #237's hook gate, #228's package and #292: 980 lines
  added, 72 removed; 14 of the other 22 payload files changed too, +5,631/−722, which the
  cells place and compare without running them). None of that diff's 35 hunks lies in the
  resolution, pin, collect or receipt code (lines 255–546 and 762–2074 at `33ce26d`; lane
  2, #186 6327803546), so R4's verdicts still hold for rows 3, 5–11, 13, 14a and 16–26
  and, except their hook clause, for rows 1 and 2. Among those that hold, R4's 3 FAIL
  (rows 7 single-branch-moves, 8b and 9 pin-404) and 4 CHANGED (row 6 single) are not
  passes (lane 2, same comment). The gaps: seven verdicts flip by design, because #237's
  gate is closed in a fresh HOME (04a, 12, 15a–e); there is no fresh bash 3.2.57 evidence
  on the new code, and 14b and 14c were last run at `2411f40`; and no cell covers the
  gate-open path, the strip path, `wip init`'s reconcile or pipx and package mode, which
  the in-repo tests and main's CI cover. D adds its composed run of
  `test_install_payload_source` (r01–r15, 109 passed) and P4's local installs with the gate
  open and closed. At a main head the old harness measures run C's installer (`9b7cbd2`),
  so a new run needs a corrected one: Brett's option is a delta P9 (lane 3 endorses it,
  #186 6327831170), which lane 2 makes and runs on his word, over rows 1, 2, 4, 11–13 and
  15 with the gate open and closed and one pipx-link cell. It is judged against R4: the
  expected differences are the seven flips, the hook lines and the shape literal, and
  anything else is a finding. It takes about 30 minutes and 1.6 GB of disk on a quiet
  bench, read-only, with no pytest lock (lane 2). If he declines, the gaps above stand.

### The surface watch

Each script took a snapshot of the real install surfaces when it started and again when it
ended, and exits 70 when the two differ (71 and 72 are defined under the post-run table).

- **The watched places,** as every attempt's `surfaces-before.txt` names them: under `~`,
  `installed.tsv` in `.local/state/openRepoTools/` (absent) and in
  `.local/share/openRepoTools/` (sha256 `5d0ccba5…`, mtime 2026-10-08T20:52:08Z), and
  `.claude/settings.json` (sha256 `d0dafd61…`, mtime 2026-10-15T18:56:28Z), each hashed;
  and `.local/bin`, `.claude/skills`, `.claude/commands`, `.claude-profiles/shared/skills`
  and `.claude-profiles/shared/commands`, each listed (207 lines).
- **It compares listings, not contents.** A directory is listed by each entry's type,
  mode, size, mtime, path and link target; a change that keeps all of those is not seen,
  nor is a subtree the listing cannot read. A skills directory's `synced/` and `.trash/`,
  which Claude Code's skill sync writes many times a day, are left out.
- **Every lane and profile in this container shares those places,** so a 70 would say that
  a place changed during the run, not who changed it; `~/.claude` and `~/.claude-profiles`
  are shared across Eagle's containers, cloud-bench's (where D ran) and py-bench's (on
  py-bench both are host bind mounts; lane 3, #186 6332521834). D's own
  `provenance/a1/surfaces-before.txt` shows it: it matches py-bench's copies by
  size and nanosecond mtime in all 104 entries it lists under `~/.claude` and
  `~/.claude-profiles/shared` and in `settings.json`, but in none of its 95 `~/.local/bin`
  entries (lane 3, #186 6333819643). `~/.local` is each container's own (lane 2's
  `installed.tsv` is `3fe26405…`, D's `5d0ccba5…`), so only the `~/.local` half of an
  install in another container is outside the watch (#186 6327441086): of an install's 29
  files, 17 go under `.local/bin` and 12 under `.claude/commands`, `.claude/skills` and
  `.claude-profiles/shared`, which the watch lists
  (`runD/install-v0/a1/s1/home/.local/share/openRepoTools/installed.tsv`; lane 3, #186
  6329982180). This record does not claim that nothing was written outside an
  attempt: the watch, like the command scan below, is a reader's aid. P3 and `s1` left
  lane-index files under their state roots, and P8 saw other actors' churn outside the watch.
- **Windows** (`attempt.txt`'s `started` to `pid.txt`'s `finished`) are those of the post-run
  and SMOKE tables; their exits are in the same tables, and none is 70.
- **Installs and setups in the windows.** In all seven attempts `surfaces.diff` is empty
  and the before- and after-snapshots hold the same 207 lines: those of P3, P4, P5, P7,
  `s1` and `s2` are byte-identical (sha256 `b812e02a…`), and P10's, which
  `provenance_d.py` writes with its mtimes in epoch seconds, is the same 207 lines once the
  notation is read alike (lane 1's record writer's comparison). The real `installed.tsv`, which an
  `openRepoTools --install` writes, has 29 rows, all stamped 2026-10-08T20:52:08Z (before
  the freeze and every window), and its sha256 is `5d0ccba5…` in every snapshot and when
  lane 1's record writer read it again at 21:01Z: no install wrote it in or after any window. The
  freeze forbids an install and a workBenches setup, and the watch saw neither; it cannot
  say that no lane tried one.
- **The link-only fallback** ("yes to the link-only 70 fallback") covers P10's provenance
  check only, for a 70 whose difference is only the `claude` or `codex` link row under
  `~/.local/bin`. It was not used: no run exited 70, so there is no `surfaces.diff` line
  to quote or attribute. The `claude` row stood at the 2.1.306 executable (mtime
  2026-10-21T12:13:44Z) and the `codex` row at its standalone package
  (2026-10-20T20:38:11Z) in every snapshot.

## P8, T18's method on D's candidate

By hand, on a copy of `runD/cand-v0/clone`, as `t018-disposable-2026-10-09.md` section 1
gives it (Brett's "include P7, P8, P10"). A separate writer (Sonnet 5.5) ran it from
16:38:27Z to 17:29Z in a run directory of its own, `p8-t018-d` under `<W>`. The harness
refused its write of the report, so lane 1 saved its reply verbatim:
`REPORT-p8-20261021T1729Z.md`, sha256 `dbc167be…`. Its `RECEIPT.sha256` (sha256
`3e3e1b54…`; 177 files, the report not among them) verifies: `sha256sum -c --strict` exits
0 with 177 OK, run again by this record's writer.

**The sandbox** is T18's, with these differences:

- three homes, every command under `env -i`, and a copy of the agent root (405 files) with
  its own `workspace.yaml`, the real file unchanged. No lane variable or lane command was
  used: `scripts/sbx.sh` refuses (99) a HOME or directory outside the run directory and an
  extra variable naming HOME, PATH, XDG, `AGENT_PROTOCOL_ROOT`, `LANES_*` or `TMUX*`;
- git moves only by `file`, through six `insteadOf` rules into the run directory's own bare
  copies of D's three candidate remotes and the mirror (D's `.gitmodules` carries its own
  prefix, where T18 rewrote run C's);
- the network is cut by `unshare --net` and the `gh`, `curl` and `wget` shims: 6 calls
  refused (2 probes, 4 `gh api` of `status --fetch`), where T18 logged 2;
- **new, a read-only mount namespace:** inside every command the real home and the
  bench's whole projects tree are read-only (D's sandbox and observation directory among
  them), only the run directory is writable, and capabilities are dropped. T18 relied on
  `HOME` alone;
- the commands under test are installed by the candidate's own `./openRepoTools --install`
  from a fresh recursive clone into each home (17 of 17 placed, 29 files recorded; `park`,
  `resume`, `status` and `openRepoTools` byte-identical to the code leg's blobs at
  `56142ed`), with the Speckit overlay of workBenches `ffd551601e49` (44 files); on all
  three workstations the root, both legs and the nested dependency equal D's
  `identities.txt`.

**Results.** Every step of T18's logs 10 to 93 ran, and none blocked or hung. **55 of the
57 exit statuses T18 logged are equal.** The two exceptions are log `00`, where the
writer's probe ends on a different command, and log `14`, the as-copied root, which sits
on `candidate-v0`, so `status` exits 1 with 2 findings (T18: 0). Every refusal text is
T18's except the Makefile line numbers, one line later (`Makefile:56: park`; T18's `:55`),
because D's split renders the root Makefile with openRepoShape v1.1.0's template. The
other differences are explained: the four installed commands have new blobs (#236, #235,
#242, #243, #191, #228 PR 1, #292); the feature numbers are 007 and 008, because D's spec
leg already holds `006-release-pypi`; OpenSpec 1.2.0, first on the bench's PATH, fails 3
of the spec leg's 6 changes (the new `release-tags-pypi` among them), as it does on the
single-repository `33ce26d`, while 1.6.0 passes all 6; and the hooks and the fork check
are the first and third of the three notes below (workstation 1, a local origin, logs one
`gh api` call where T18 had two).

**T18's eleven follow-ups (its section 5): none is fixed.** Each was checked with its log.
The overlay scripts they belong to are byte-identical between workBenches `ffd5516` and
its `origin/main` `d89869b`, and none of the subjects of the candidate code leg's 60
commits dated from 2026-10-09 on (59 after that day; 3 are the rehearsal's own patches)
names these behaviours: P8 read the subjects, not the diffs. Follow-up 7 is one change
worse (the third failing spec change). Not exercised: macOS, the `gh`-backed fork and
shape-currency checks, and `setup-openspeckit` from workBenches `origin/main` (476
insertions and 6 deletions different).

**Judgement calls:** (1) in P8's own copy of the root remote, `main` is fast-forwarded
to the candidate `c67b0e6`: D's remote holds it as `candidate-v0`, with `main` at the
unpatched split `92e4e41`, and a fresh clone, `resume` and `park` read `main`. D's `main`
is kept there as `refs/d-orig/main`, and D's own remote is untouched. (2) Workstation 1's
copy, a `cp -a` of `cand-v0/clone` on `candidate-v0`, was put on `main` (same commit) after
its as-copied `status` was logged. (3) The wrapper added the read-only mount namespace.

**New for the cutover runbook:** a fresh install writes no `~/.claude/settings.json`
(T18's install created one): the SessionStart hook and the name guard are merged only
once `~/projects/xFactory/lanes-edit.sh` answers `guard` (#237); `status` flags a stage-4
clone left on `candidate-v0`; and `status --fetch`'s fork check runs only for a github.com
origin.

**The proofs** (P8's `state/sources-before.txt` at 16:55:45Z against `sources-after2.txt`
at 17:27:56Z): **D's 12 ref digests are unchanged** (the three `cand-v0/remotes`, the two
`runD/remotes`, the mirror, `source`, `shape`, the clone and its three module git
directories), and so are the tree digests of 7 of the 8 directories read. The 8th, `<S>`
itself, grew by 7 files, all under `runD/suites-v0/a1/`, which D's own P3 was writing.
Lane 1's record writer recomputed the 12 ref digests at 20:49Z with P8's formula: all equal. **The
real surfaces that P3 and P5 watch are unchanged** (listed and hashed at 16:51:38Z and
17:27:56Z: `~/.local/bin`, the share-directory `installed.tsv`, `settings.json`, the
skills and commands, `~/.agents`). **Other actors' churn, outside the watch:**
`lanes-index.sqlite` and `lanes-index.status.json` (the live register index) and Claude
Code's `skills/synced/` files of four sessions. P8 attributes them to others: every one of
those paths was read-only inside its sandbox, and it ran no lane command.

## The end of D

`observed end` ran 20:40:44Z to 20:40:53Z, after every post-run script and both SMOKE
attempts had ended (`<W>/d-operator-log/act10-end.log`; 0 STOP lines in exits.txt). Its
verdict is **OK** (`<S>.observe/end.txt`):

- origin main `33ce26df…` FROZEN; 0 `adopt/` refs; `openRepoTools-spec` and
  `openRepoTools-code` absent (HTTP 404); the shared checkout's `HEAD` (`21e0829e…`),
  status (0 lines) and `adopt/` branches (0) as at the start. Its refs digest moved
  (`35a1e2d9ed5f9b44` to `f469bb3c0ca732e7`) because six worktree heads moved, local
  branches the freeze's rules do not cover: lane 2's `gap-275`, `gap-278`, `gap-279` and
  `gap-287`, lane 4's `ort4-290-named-read` and `ort4-291-control-root`;
- 0 HOLD, LANDING, LANDED or WITHDRAWN lines on `opensoft/openRepoTools main` after
  16:25:51Z; with the windows of the gate and after-execute, none from 16:22:00Z to
  20:40:44Z. The observation reads only that repository's lines: lane openRepoShape-1's
  HOLD, LANDING (#430), LANDED (`038dafb`) and HOLD RELEASED on
  `opensoft/openRepoShape main`, 18:41:48Z to 18:43:16Z, are in this window and not counted;
- line 2 is `observe_d.sh sha256 a157c257…; S=<S>; expect 33ce26df…`, equal to the
  `observe_d.sh reviewed` value of `logs/setup-scripts.log` and to the sha256 of
  `<P>/scripts/observe_d.sh` (PLAN 10.1, F8); `before-setup`, `gate` and `after-execute`
  carry the same line 2;
- `prereq.diff` reads "bench and system installs unchanged" (e4): the prerequisites block
  is the same in all four phase files.

**The command scan** (`<S>.observe/command-scan.txt`) lists 38 lines of `<S>/scripts/*`, as
PLAN 10.2's table expects: 37 in the post-run scripts and 1 in `run_rehearsal_d.sh`. Each
is matched to a row of that table **by its text, not by its number** (lane 1's record writer's match,
by program; the numbers also equal the table's, since D ran the bytes it was made for),
and none is unmatched or matched twice:

| Row | Kind and text | Lines | Where |
| --- | --- | ---: | --- |
| 1 | force-push: `push --force` of `main~1` over `main` in the drill's throwaway repository | 1 | `rollback_d.sh` |
| 2 | push-delete: the delete of `main` there | 1 | `rollback_d.sh` |
| 3 | ref-rewrite: `live_repo()`'s `symbolic-ref HEAD` and `update-ref refs/heads/main` | 2 | `rollback_d.sh` |
| 4 | ref-rewrite: drill (a)'s restored copy, `symbolic-ref HEAD` and the marker branch | 2 | `rollback_d.sh` |
| 5 | ref-rewrite: drill (b2)'s `switch -q -C bump-back` and `bump-again` | 2 | `rollback_d.sh` |
| 6 | signal: `on_signal`'s `kill -TERM "$CHILD"` | 2 | `suites_d.sh`, `wheel_d.sh` |
| 7 | signal: the same TERM after the `INTERRUPTED` check | 2 | `suites_d.sh`, `wheel_d.sh` |
| 8 | signal: `kill -0 "$CHILD"` | 2 | `suites_d.sh`, `wheel_d.sh` |
| 9 | prose naming `kill -TERM`, in comments and messages | 23 | `suites_d.sh` 6, `wheel_d.sh` 6, `install_d.sh` 4, `rollback_d.sh` 4, `provenance_d.py` 3 |
| 10 | history-rewrite: `git filter-repo --version`, in the header stage 1 writes | 1 | `run_rehearsal_d.sh` |

Lane 1's `n13-table.py --check` of PLAN.md, run at 20:42:39Z
(`<W>/d-operator-log/act10c-n13-check.txt`), says OK: the table is its output byte for byte
(10 rows), every listed line is in exactly one row, and D's 11 copied scripts are each
byte-identical to the reviewed ones. The scan lists known forms only: a command written
in a form none of its 38 patterns names is not listed, so it is a reader's aid and never a
proof that nothing else is there.

**D's remotes at the end.** Lane 1 read their refs at 20:40:54Z with `git for-each-ref`
(`<W>/d-operator-log/act10b-remotes-at-end.txt`): D's execute remotes hold `main` at
`de756faf8797` (spec) and `d9e7d568011b` (code), 1 ref each; the candidate's copies hold
`f41ac906b8f7` (spec), `56142ed741f9` (code) and `92e4e4172779` (assembly, 2 refs: `main`,
the commit printed, and `candidate-v0`, which the file does not print: its digest
`bd515adc2eee30f0` recomputes with `candidate-v0` at `c67b0e6838c2`); the source clone is
at `33ce26dffc52` (6 refs). They are the commits `results.txt` and stage 4 recorded.

## Private log SHA256s

Each digest was computed for this record from the file as it stands; the private receipt
keeps the files. The act logs and the extract are under `<W>/d-operator-log/`, the
observations, `command-scan.txt` and `prereq.diff` under `<S>.observe/`, P8's two files
under `<W>/p8-t018-d/`, the rest under `<S>/runD/`.

| File | sha256 |
| --- | --- |
| `act0-act1.log` | `584256836245ada6504f349aeac0d4f3afe5eeb9fd219899a9e2021e9b907f12` |
| `act2-stage1.log` | `e821e1ce2f10fb5bb288208b8c4f1ea88c64d6bbb7ab6472acf432f0cf6637aa` |
| `act3-gate.log` | `d976131484fef691ac7a7d846a50c5574e05956f7a69f04f9a6ae3686d97f9e6` |
| `act4-stage2.log` | `b0b10396d636c375babdd738a3096bf58560cc253aa0da442f7a949049429ff7` |
| `act5-after-execute.log` | `db58c0c17d3071af7ae5949da27eea6f0ec2001ad16b610aed4cba3b28b16885` |
| `act6-stage2v.log` | `616e638eb096b08ea15dc4c791f77c0ebec1b90c450d27d7fb00a0325fb2dad9` |
| `act7-stage3.log` | `030acc93fef0d5addc3467485ab3ade764db95d1c584ec10519e54bf7602ee23` |
| `act8-stage4.log` | `d8fff21ade86a09272b3f9aa0dff891e7054c711af49dbc69128ddd23953b49a` |
| `act9-transcript-extract-1619-1634.txt` | `309d978e07fdf12a4e7018a6f1ffb715d3259e371047f99a4c987c6b006802d9` |
| `act10-end.log` | `0a40bacf588bbb95bbc17f9e262f90e241b7a89dacc0f97029840f0368abd801` |
| `act10b-remotes-at-end.txt` | `952aeaa7eb3fbbc74555e25bf004755e723753ce5039d9e56893106230ebbc5c` |
| `act10c-n13-check.txt` | `9941318ceca793c530a551c7fa17a144da35a5e85a53e3abe74faf16b11cb013` |
| observation `before-setup.txt` | `0788125978b96bca25657832b405530908e89772ecfbda6144e9513198143cb4` |
| observation `gate.txt` | `84254cf17f02c16e7d47ede6b3ceb77fbafbfd5f745b820b6210386f02967e16` |
| observation `after-execute.txt` | `3705342ce67cfdc1686a21404efcfd0174b54d95ee847f34f85df58d20a36a42` |
| observation `end.txt` | `6de121c6f1a6ecebbbca3fcb417b66e1f0beba44db3e0d4337e16d7e8884cf47` |
| `command-scan.txt` | `35b1a9a4f3a725e5603fbf45bea1671b7dff3b675b4b3ba6cfa182b6bef59ed1` |
| `prereq.diff` | `4f80027255652a053715960bfe15b0064bd71d39524d88de9c11e999c7d8f657` |
| `exits.txt` | `c144eb92c18c85e522872b62922ace5769195fa4fc835be340af104c16baa6b2` |
| `execute.log` | `0d50767d7834231f5777a4a7b2fbb7c4d9f6735e60ab3ed7f8c50cfc9e5850eb` |
| `v1/bootstrap.log` | `459b34f31f9ce054d01997ce2c01de586371241478d8fb5a44ff4db06d03e6ea` |
| `v1/accounting.log` | `136bc5dbd8b072febda672a5f3c757d63151c7baa512618cec4375f71b08927b` |
| `cand-v0/bootstrap.log` | `aa0d9006b768d728815837d71a53fcc893454a71f04e83829d68626e9b409494` |
| `RECEIPT.sha256` of P4 (`install-v0/a1`) | `8f66c7aa29b0d2df271e5cd678fd5157e47bb48792dea91b5ce8c76c842f6e50` |
| `RECEIPT.sha256` of P7 (`rollback-v0/a1`) | `fbd1306795bc7d22e86f767a8d99c98f0c478edaff8e37e099ee902e7a37a8a9` |
| `RECEIPT.sha256` of P10 (`provenance/a1`) | `4c5bbcc46f421a97ff0a2ee0d40dff37ad2fde8398194b935e767cf61c5150fe` |
| `RECEIPT.sha256` of P3 (`suites-v0/a1`) | `cd5c9d12040f4daa93a00edd51f027b8b0ad1851d6983eb49f7bbc35334da606` |
| `RECEIPT.sha256` of P5 (`wheel-v0/a1`) | `0cefffef9438d277ea315fd9a9d79737e0020000ca2fe5b14c92885e58cdb92d` |
| `RECEIPT.sha256` of `s1` | `7b5e4cc8444a92d4a45bf9dc9a032acbd68cb6d0723ec10655010503d22b7644` |
| `RECEIPT.sha256` of `s2` | `26906d3c3d9f9f5503b22e0b3e3725d7d8654b5be81839a7e4b89919997ad0f7` |
| P8's `RECEIPT.sha256` | `3e3e1b5442b950d313727f81dfb2a35307457b07c408e6321a55d66c10036dfc` |
| P8's `REPORT-p8-20261021T1729Z.md` | `dbc167be73589591175be0d33c18367dd2e5b2f02871408390d450802c0fbd44` |
| `<P>/scripts/REVIEWED.sha256.v8-20261021` | `fcfe0653d2f08d04e4a81252ca3c4e41dfccd57b92697d0bbbeec50b3929d9b4` |
| the published plan, `published-plan.yaml` | `45b0ec8d7513a7f8dd58b3003c133c2ee155324929e145f44990404823b226ed` |

The published plan is the file on the evidence branch under
`openspec/changes/migrate-to-triad/adoption-plan.yaml`, byte for byte.

## Remaining gates

**Gate C is not given by this record.** It needs Brett Heap's explicit approval, which must
name the revisions, the leg repositories, their visibility and the final plan. Lanes 2 and 3
re-checked the fixes of the reviews of `3845c53`, with the post-D round, at `2f07c53` (#186
6329313690 and 6329982180); `d2bc30a` applied the items they left for the record. Both
then OK'd the record at `d2bc30a`: lane 2 OK, with no MUST and no SHOULD (6332076797);
lane 3 READY AFTER ONE TEXT FIX, 231 (6332521834). `167564c` applied 231 and the NITs they
left for the record in those OKs. Both also OK'd the post-D round's second pass in the
same two comments (r2 there, not Gate B's r2), and lane 1 installed it at
2026-10-22T04:24:09Z (6332671966; lane 3 checked the install, 6332684327). Lanes 2 and 3
then re-checked `167564c`: lane 2 READY AFTER ONE FIX, R1 (6333755295); lane 3 READY AFTER
ONE TEXT FIX, 261 (6333819643). `555bab1` applied R1 and 261 and the NITs they left
for the record: lane 2's 1–8 and lane 3's 262–269. Lanes 2 and 3 then passed `555bab1`:
lane 2 OK, with no MUST and no SHOULD (6334818560); lane 3 READY (6334668981). This
version takes their last clause-level NITs: lane 3's 311–318 and lane 2's optional
one. Still to come after this record:

- P3's `composed` and `standalone` jobs stand RED in D, and the SMOKE attempts do not turn
  them green. Row 34 stays PARTLY:
  - **(b), #304, is open and needs a cutover decision (lane 1 and Brett).** Before
    `exact-pins` becomes a required check (e9, Gate B's question on which checks are
    required: `gate-b-status-2026-10-09.md:187`), port #215's fix to
    `tests/test_lane_helpers.sh:1272` and `:8551-8552` as a reviewed code-leg follow-up at
    T014, or give `exact-pins` a short `XDG_STATE_HOME`; or Brett accepts row 34 resting on
    P3, `s1`, `s2` and lane 3's run, with (b)'s zero margin at a 4-digit pid. A rerun at a
    TMPDIR of 69 or less would hide (b), and a full rerun adds nothing until it is fixed;
  - (a) is the rehearsal's own local URLs, shown absent with the cutover's URLs (lane 3's
    run, above), and (c) is load (#305). After a fix for (b), what would settle row 34 is
    one run of the case at a TMPDIR of 70 or more, about 40 minutes (lane 2 accepts to make
    it, on Brett's word), and one green composed run at CI's run-root length, on a quiet
    bench, with the cutover's URLs on a copy and pytest 8.3.4 (P12's `--pytest-wheels`,
    PLAN 10.2, once the bound is relaxed, or a repository venv at pytest 8.3.4 for a
    direct run; lane 3). `suites_d.sh` cannot make either at that length: the post-D
    round's copy refuses a state root over 22 characters (D's copy allowed 23), so its
    runs stay at a TMPDIR of 69 or less (67 or less at its default root). Each is then a
    direct `tests/run.sh` run, unless the bound is relaxed once #304 is fixed. #304's
    proof is such a run at a TMPDIR of 70 or more, or `exact-pins` on the code leg after
    T014; the composed run of record is the cutover's T010 job and T015, and the legs'
    first CI comes after Gate C;
  - row 33 rests on CI for pipx; row 31 is evidenced without job 5 (which would meet #304
    at a TMPDIR of 70 or more: lane 2); row 27 rests on `7aa697c` with the gaps above,
    unless Brett orders the delta P9;
- the plan, regenerated from the frozen source at the cutover: D's published plan is a
  rehearsal input with `execution_authorized: false`, and stays on an evidence branch with
  this record until the root-split PR (e2);
- inside the cutover, right after `execute` and before the code leg's first package or
  release run: T006 code-0001 in `openRepoTools-code`, and the owner's acts the plan's last
  follow-up names (the testpypi and pypi environments and the tag ruleset in
  `openRepoTools-code`, a test.pypi.org trusted publisher for it, and a pypi.org pending
  publisher naming `openRepoTools-code`, `release.yml` and the pypi environment: #228);
- also inside the cutover, D7's other half (Brett: "yes to e2 and D7, names only"): `check`
  run in the real cutover environment, its `git config --show-origin --list` names recorded
  and never their values; D ran only the I4 half (Mapping);
- the post-D round is done and installed, with `REVIEWED.sha256` `410890f7…` (D ran on
  `fcfe0653…`; Reviewed bytes). It took lane 3's NITs 121–123, 131–135 and 141–144, with
  lane 3's tested fixes for 141 and 142 (#186 6320744628; the round is listed in
  6320876769); the message text at D's `setup_d.sh:237` (`pin_expect`); the published
  plan's header, which overstated what the decisions file did and dropped "Gate B remains
  open (T006-T011)", both fixed in the round's `publish_plan_d.py`; starting the stage
  acts from a neutral directory (Setup); the "about 72" in PLAN 10.2 and `suites_d.sh`'s
  header (the defect is #304), with the sentence that no `suites_d.sh` run reaches a
  TMPDIR of 70; and `pid_write`, which restamped `started` at every rewrite in
  `suites_d.sh` and `wheel_d.sh` (the line was also in `install_d.sh` and
  `rollback_d.sh`): D's `pid.txt` files still show it, P3's reading 19:57:57Z and P5's
  18:20:03Z, where `attempt.txt` has 16:27:48Z and 16:28:08Z, which this record uses.
  The PLAN NITs, lane 3's 234 (its PLAN `:650` half), 236, 237's PLAN half and 239, and
  lane 2's 1, 2, 6 and 8, went into PLAN's touch 4 (`ad34b9bb…`, the bytes the two
  re-checks read): lane 2 OK'd it (#186 6333755295) and lane 3 found it READY
  (6333819643). Touch 4b, made after the re-checks, added lane 3's 271–277 and lane 2's
  N13 and `:1329` NITs, as lane 3 asked for 271 and 272. Lane 1 installed PLAN's touch 4
  and 4b at 2026-10-22T06:19:34Z as `e5fd3268…` (#186 6334204631; lane 2 checked
  the install, 6334243204), and the bytes before, `304eace8…`, are kept as
  `PLAN.md.v9-20261022`. No script and no manifest changed: `REVIEWED.sha256` is still
  `410890f7…`, and `sha256sum -c --strict` reads 13 OK. `REVIEWED.md` gained an entry
  for the install and is now `ea367edf…`, and its bytes before, `576f55a2…`, are kept as
  `REVIEWED.md.v9-20261022` (install log: `<W>/postd-touch4/install-t4b/install-t4b.log`).
  Lane 3 then found touch 4b READY (6334668981). Touch 4c then took lane 3's PLAN NITs 301
  and 302 (6334668981), and lane 1 installed it at 2026-10-22T07:26:33Z as `59646ce5…`;
  the bytes before, `e5fd3268…`, are kept as `PLAN.md.v10-20261022`, `REVIEWED.md` is now
  `3f04a131…`, and the manifest did not change. Still to come from the round, for the
  next touch or the cutover runbook (#186 6332671966): lane 3's NITs 241–243 and 251–254
  (242 and 252 with their PLAN lines) and lane 2's 3 and 7, on the scripts and the test
  harness; and an observation, tracked as #306 for the code leg after the split: the
  lane-helper suite sets HOME (`tests/test_lane_helpers.sh:269`) but never
  `XDG_STATE_HOME`, which `lanes-index` prefers (`lanes-index:174`), so P3 and `s1` wrote
  their index files into their state roots and, under a real `XDG_STATE_HOME`, it would
  write into the live index's directory (lane 2);
- notes that cannot land before the cutover (e2), because they edit main's own documents
  or a landed PR's body: #299's four NITs on the dated notes (lane 3's review of #299,
  comment 6317075196; `gate-b-checklist.md:202`, `candidate-2026-10-09.md:104`,
  `gate-b-status-2026-10-09.md:187`), `gate-b-status-2026-10-09.md:186`'s "none fires
  on `ubuntu-24.04`", which is stale: 66 conditional skips fire there (lane 2, #186
  6327803546), and the pointers to #180 for the row-stamp cases, which are now #304's:
  `git grep -n '#180' 33ce26d -- specs/` finds 19 lines in four files (6 in
  `candidate-2026-10-09.md`, 3 in `gate-ab-evidence-2026-10-09.md`, 5 in
  `gate-b-status-2026-10-09.md` and 5 in `test-roots-and-ci-2026-10-08.md`), 18 of them
  such pointers (lane 3, #186 6332521834) and one, `candidate-2026-10-09.md:404`, a list
  of issues read with `gh` (lane 2 counted the 19 lines, 6332076797). Where they go, for
  example the spec leg after the split, is lane 1's call;
- T18's eleven follow-ups, all still present (the P8 section), for the cutover runbook;
- the e2 freeze: main stays at `33ce26d` until the cutover, and a second `execute`, in a
  new sandbox, happens only on Brett's word.

This evidence authorizes no real conversion, repository creation, merge, default-branch
move or lane rebinding.

## Appendix: follow-up patch and commit inventory (Gate B row 40)

Row 40 of the Gate B checklist (`gate-b-checklist.md:214` on main `33ce26d`) asks for "One
table of every T006–T010 patch, giving the target leg, the rehearsed base commit, the
resulting commit and the review reference." This is that table for run D. The rehearsed
bases and the resulting commits are D's own: stage 4's `candidate-v0` (`runD/cand-v0`,
16:27:07Z to 16:27:17Z). Lane 1 assembled the table from D's receipt and checked it
against the receipt's git repositories and GitHub. Lane 2 then verified all nine rows at
`167564c` (#186 6333755295). Lane 3 held the table row by row and replayed all seven
patches with `git am --3way` on copies of D's bases, and all seven trees equal stage 4's
(6333819643). Both lanes then passed `555bab1` (lane 2, 6334818560; lane 3, 6334668981).

Nine rows in apply order: seven patch files and two commits that openRepoShape's
`bump-leg.py` wrote. They are three commits on the code leg, one on the spec leg and five
on the assembly root, as in the table under The candidate (stage 4, v0). Ids are 12 hex
digits, as this record writes them, and the full ids follow the table. "PR #N review ID"
is a pull-request review, "PR #N comment ID" a comment on that PR's conversation and "#186
comment ID" a comment on #186.

| Patch (sha256 as D pinned it) | Target leg | Rehearsed base | Resulting commit | Review reference | Notes |
| --- | --- | --- | --- | --- | --- |
| **1.** `code-0001` (`74b98ff9…`) | code (`openRepoTools-code`) | `d9e7d568011b`, the code leg `execute` made | `4656dc81e620` | PR #192 review 5464893559 (lane 3: LAND on `71b05cb`; finding 7 rebuilt the patch's commit exactly) | Six files added (`.gitattributes`, `.gitignore`, `AGENTS.md`, `CLAUDE.md`, `LICENSE`, `README.md`), +331. The file at `71b05cb` has the same sha256 as D's pin. That review ran on run C's code leg; stages 3 and 4 are its first applications to D's. The leg's first commit after `execute`, before its first package or release run (Remaining gates). |
| **2.** `t010-code-leg-tests-workflow` (`1406ead3…`) | code | `4656dc81e620` (row 1) | `8b06964f2fd8` | PR #266 comment 6275785285, item 4 (lane 3: LAND on `5162d62`); also PR #299 comment 6317075196, "The job lines" (on `tests.yml` `46feb68` it gives `a24d126`, hunk 3 at offset 3) | `.github/workflows/tests.yml` only, +41 −1: blob `46feb68` to `a24d126`, the blob lane 3 named. The patch expects `2cfa173`, and hunk 3 applies at offset 3 (stage 3's check log). Authored by the fixture identity `openRepoTools CI`; a real author is a T014 item (#186 6089801221, finding 13 (iv)). The earlier file (`7ee3c6d0…`, reviewed in 6089801221 (c)) is superseded. |
| **3.** `t009-assembly-caps` (`2dd4aac2…`) | code. Its header says "Code-leg patch"; the caps it sets are the assembly root's | `8b06964f2fd8` (row 2) | `56142ed741f9`, the candidate's code tip | PR #266 comment 6275785285, item 5 (lane 3: LAND on `5162d62`; "Applies in stage 4's order: `code-0001`, then T010, then T009") | `tests/test_repo_hygiene.py` and `tests/test_test_roots.py`, +38 −17. The two caps go 347 to 354 and 510 to 529, the line counts of the root's `AGENTS.md` and `README.md` after row 5 (330 to 354 and 505 to 529, counted at both commits). Stage 4 only: stage 3 did not try it. The patch's `index` line names `tests/test_repo_hygiene.py` `a97f5a8`; D's file is `1addfd5` (main's at `33ce26d`), the blob #266's review applied the patch to, so the result is `2a8aaf4`, not the `index` line's `832998f`. The mismatch costs only an offset: on D's `1addfd5`, both `tests/test_repo_hygiene.py` hunks apply at offset 1 (`git apply --check -v` gives 1977 and 2522), and the resulting tree equals `56142ed`'s. |
| **4.** `spec-0001` (`c11070f0…`) | spec (`openRepoTools-spec`) | `de756faf8797`, the spec leg `execute` made | `f41ac906b8f7`, the candidate's spec tip | PR #192 review 5464893559 (as row 1) | Five files added (`.gitattributes`, `AGENTS.md`, `CLAUDE.md`, `LICENSE`, `README.md`) and `docs/README-claude-current.md` changed, +301 −2. The same sha256 as at `71b05cb`. Hunk 1 of `docs/README-claude-current.md` applies at offset 8 (stage 3's check log). |
| **5.** `assembly-0001`, re-cut (`2ec48bbf…`) | assembly root (`openRepoTools`) | `92e4e4172779`, the split (`main` of the assembly remote) | `6a36cc17ba0a` | PR #266 comment 6275785285, item 2 (lane 3: LAND on `5162d62`). #192's review 5464893559 covers the earlier file (`cd69c2a9…`), not this one | Four files changed (`.gitattributes`, `.gitignore`, `AGENTS.md`, `README.md`), +97 −53: `AGENTS.md` goes 330 to 354 lines and `README.md` 505 to 529. No offset (stage 3's check log). The patch's `index` line, like #266's review, names `AGENTS.md` `47165cb`, main's file before #294's `acc89ea`; D's split carries main's `0b25c49`, from `acc89ea` (four lines changed, 330 either way), and the patch applies to it all the same, giving `fcbc637` where the `index` line gives `e8a0388`. |
| **6.** `t010-assembly-exact-pin-job` (`60245cb9…`) | assembly root | `6a36cc17ba0a` (row 5) | `d6e5764985b7` | PR #299 comment 6317075196 (lane 3: LAND on `076fa70`; names this sha256 and the created blob). The earlier file (`6ee09f00…`): #186 comment 6089801221 (c) | Creates `.github/workflows/composed.yml`, +106, blob `113f094` as lane 3 measured; `runs-on: ubuntu-24.04` since #299. Authored by the fixture identity `openRepoTools CI` (real author: T014). #304 bears on this job's first run on real legs (P3 (b), above). |
| **7.** `t007-assembly-entry-point`, v3 (`67d8e7ce…`) | assembly root | `d6e5764985b7` (row 6) | `6297ee9f2ab2` | PR #196 review 5481368376 (lane 3, on `7c08f7e`: finding 1, v3 meets T3's required change; its verdict, DO NOT LAND the two files as written, rests on corrections to the installer record, and the patch "can stay as it is" once finding 2's residual is a named T015 item) and PR #196 delta review 5560058266 (lane 3, `7c08f7e..b50c83c`: LAND; the patch is unchanged, sha256 `67d8e7ce…`) | Creates the root `openRepoTools` (mode 100755), +398: blob `ff432c6`, the blob lane 3 measured. T3 is the change lane 3's review of v2 required (PR #191 review 5471121210): confirm the gitlink before running the pinned implementation. T3's second case, a lockstep-consistent pin at code from before #191, stays open as a T015 item (5560058266, finding 2). |
| **8.** spec-leg bump by `bump-leg.py` (no patch file) | assembly root: the `spec` gitlink and `contracts/spec-pin.yaml` | `6297ee9f2ab2` (row 7) | `2833b34a3448` | No patch review. Covered through the reviews of D's record: lane 3 reproduced stage 4's commits (#186 6327470307), and lane 2 checked the trailer (6327441086, NIT 7) | `de756faf8797` to `f41ac906b8f7`, pin tree digest `bc2d1813…`. Written by openRepoShape `190133d`'s `scripts/bump-leg.py` after a dry run; the project's validators printed `pins ok` and `manifest ok`. Carries the trailer `Rehearsal: D v0`. Takes the place of run C's `assembly-0002` (`574c0df1…`), which D did not apply. |
| **9.** code-leg bump by `bump-leg.py` (no patch file) | assembly root: the `code` gitlink and `contracts/code-pin.yaml` | `2833b34a3448` (row 8) | `c67b0e6838c2`, the tip of `candidate-v0` | As row 8 | `d9e7d568011b` to `56142ed741f9`, pin tree digest `45b3f125…`. The same tool, validators and trailer as row 8. Takes the place of run C's `assembly-0003` (`a7f8521b…`), which D did not apply. |

**Order.** Rows 1 to 3 went on in the code clone `w-code`, row 4 in the spec clone
`w-spec` and rows 5 to 9 in the assembly clone `w-assembly` (all under `runD/cand-v0`), in
that sequence (`runD/exits.txt`, `c4-v0` lines). The candidate's remotes end at
`56142ed741f9` (code `main`), `f41ac906b8f7` (spec `main`) and `c67b0e6838c2`
(`candidate-v0`, with the assembly's `main` still at the split). **Not applied in D, so
not in the table:** run C's `assembly-0002` and `assembly-0003`, which rows 8 and 9
replace, and the deletion of the three unpinned `shape/AGENTS.md`, `shape/CLAUDE.md` and
`shape/README.md`, which stays with T014 (all three are still in `candidate-v0`). Main
holds nine patch files at `33ce26d`, D's seven and run C's `assembly-0002` and
`assembly-0003`; the Gate B status note's row 40 (`gate-b-status-2026-10-09.md:195`)
counts "7 patches" (run C's: T006's five and T010's two) and "eight files now" (adding
T009's), without T007's `t007-assembly-entry-point.patch`, which makes nine.

**Stage 3's trial commits.** Stage 3 (`runD/t006-1`, 16:26:44Z to 16:26:45Z) applied five
of the seven patches, `assembly-0001`, `code-0001`, `spec-0001`,
`t010-code-leg-tests-workflow` and `t010-assembly-exact-pin-job`, each as `apply --check`
then `am --3way`, every one EXIT 0, on trial branches of scratch clones at stage 4's
bases, the second patch on a leg on the first's trial commit. It did not try
`t009-assembly-caps` or `t007-assembly-entry-point`. Each trial commit has the same tree
as the stage-4 commit of its row and a different id, because its committer time differs
and, for the second patch on a leg, its parent too: `e1a7ce6843b1` (row 1), `72b0632e2256`
(row 2), `abca47d0fa98` (row 4), `5891e9eba9a5` (row 5) and `0877993eef52` (row 6).

**Full ids.** Bases first, then stage 4's results in the table's order, then stage 3's
trial commits (`git rev-parse`, in the receipt's clones). The two leg bases carry the
times of the source commits they were filtered from (`d9e7d568011b`: #296's,
`de756faf8797`: #299's); the split's is D's `execute` time.

| Short | Full commit id | Tree | Committer time (UTC, 2026-10-21) |
| --- | --- | --- | --- |
| `d9e7d568011b` (code base) | `d9e7d568011b339e8d4bb87f3f83f58ec653794a` | `8fe305c693f6a27176137b33dbc72e1d79d4ed13` | 12:53:15 |
| `de756faf8797` (spec base) | `de756faf8797ea4ee598bf2a9cee84f2b358fa67` | `83de869a4424ba00b8529ffc1dcadd7ab60435e0` | 14:07:40 |
| `92e4e4172779` (split) | `92e4e4172779a226a5e98efa6a3c671baa43ba79` | `9c079c8891d9edceef0789e3fed845ad8e25a1b5` | 16:25:30 |
| `4656dc81e620` (row 1) | `4656dc81e6201658e08f6deb0b3e3f402ad70e5a` | `6f4e72bf1856430215e1d3ec83da064cd0af8abe` | 16:27:09 |
| `8b06964f2fd8` (row 2) | `8b06964f2fd8ac7bc288648fb1228d43b713d14b` | `2aca2068dd4af108297eb12bab3512eca3240475` | 16:27:09 |
| `56142ed741f9` (row 3) | `56142ed741f9cb1d66c62d5d19b3ebf9620a500d` | `e3b3dc3923c92eded96011398b6e2978beeb44f4` | 16:27:10 |
| `f41ac906b8f7` (row 4) | `f41ac906b8f707fd8969e307b658d79aa3827f83` | `b576f694fc158af2494567367a04d73a9baf7f3a` | 16:27:10 |
| `6a36cc17ba0a` (row 5) | `6a36cc17ba0ae05db11d5e505ed49f348cef7045` | `c28136605fef00fee13f1206523f2b19cf61e2ad` | 16:27:11 |
| `d6e5764985b7` (row 6) | `d6e5764985b7ec129eb738cf5d2b0b8cc56a23d7` | `8c9ac180b5ff04b5c82e47b1594ea9c0ecba498f` | 16:27:11 |
| `6297ee9f2ab2` (row 7) | `6297ee9f2ab246428bb4d50fa12247dbe936cfa2` | `628e4003619139f3b05cd1be65fad8b296cadd07` | 16:27:11 |
| `2833b34a3448` (row 8) | `2833b34a3448ef44fe72cf4d824fe87be1d9b263` | `eb14c8dee0fabce0301bbca786312f7a84838c0e` | 16:27:12 |
| `c67b0e6838c2` (row 9) | `c67b0e6838c2c1ae25733df2c0b8316bb7e72452` | `7d86b12147423b49ba3f2f30df445845d1bcbbfc` | 16:27:13 |
| `e1a7ce6843b1` (stage 3, row 1) | `e1a7ce6843b1fa564e1f6d66e1f8968a897352c3` | as row 1 | 16:26:45 |
| `72b0632e2256` (stage 3, row 2) | `72b0632e2256e3d4e9fba62ebec0523833f32766` | as row 2 | 16:26:45 |
| `abca47d0fa98` (stage 3, row 4) | `abca47d0fa98351499d2b17ebe695c0c2fc30d5b` | as row 4 | 16:26:45 |
| `5891e9eba9a5` (stage 3, row 5) | `5891e9eba9a59edda97eed66df1712387f8c8914` | as row 5 | 16:26:45 |
| `0877993eef52` (stage 3, row 6) | `0877993eef5234e810bd943fef5946958631b90d` | as row 6 | 16:26:45 |

**Sources.** Paths here are relative to `work-20261021/`. The seven pins are in
`rehearsal-d/inputs/patches/SHA256SUMS` (`sha256sum -c`: 7 OK), and each equals the file
under `specs/004-migrate-to-triad/patches/` on main `33ce26d`. This record names the
bases, the candidate's tips and the two bumps; the ids of rows 1, 2, 5, 6 and 7, and every
tree and parent, come from the git repositories the private receipt keeps, read with
`git log`, `git rev-parse`, `git diff-tree` and `git patch-id` only:
`rehearsal-d/runD/cand-v0/w-code`, `w-spec` and `w-assembly` for stage 4 (their refs equal
the heads of the candidate's remotes under `rehearsal-d/runD/cand-v0/remotes/`) and
`rehearsal-d/runD/t006-1/code`, `spec` and `assembly` for stage 3. The logs under
`rehearsal-d/runD/` fix the order and the exits: `exits.txt` (the `c4-v0` lines),
`cand-v0/am-*.log`, `cand-v0/bump-spec.log` and `cand-v0/bump-code.log` (which print
"committed 2833b34a3448" and "committed c67b0e6838c2"), and `t006-1/*.check.log` and
`t006-1/*.am.log`. Each commit was matched to its patch by the subject its `am` log
prints, by the parent chain and by `git patch-id --stable`, which gives the patch's own
patch-id for all seven stage-4 commits and all five stage-3 commits. The review ids are
from the Gate C status draft (`gatec-status/GATE-C-STATUS-v2.md`, row 46 and Appendix A),
except 5471121210 (the installer record and the Gate B status note on main); and
6329313690, 6329982180, 6332076797, 6332521834, 6333755295, 6333819643, 6334668981
and 6334818560 (#186 comments newer than the draft: the re-checks and OKs of lanes
2 and 3). 6278378293, which row 46 also cites, is lane 1's landing comment on #266,
not a review. Each was read again with `gh api` on 2026-10-22 and says what it is
cited for. The reviewed heads carry D's bytes, by sha256 or by blob: `71b05cb` for
`code-0001` and `spec-0001`, `5162d62` for the other three #266 files, `076fa70`
for the exact-pin job and `b50c83c` for T007 v3.

**Gaps.**

- **D's record has no per-patch review table.** Its only review table, Reviewed bytes,
  covers the 13 scripts, and the one per-patch review id in it, #299's 6317075196, is
  cited for four NITs on the dated notes and not for the patch. The per-patch references
  come from the Gate C status draft and the Gate B status note, as above.
- **`t009-assembly-caps` is a code-leg patch, not an assembly-root one.** Its header says
  "Code-leg patch", D applied it in `w-code`, and `gate-ab-evidence-2026-10-09.md` on main
  (section 5) says "code leg". Only the caps it sets are the assembly root's.
- **The two bumps have no review of their own.** They are tool output, not patch files.
  Lane 3's "Stage 4's commits and the six end-of-D ref digests reproduce" (#186
  6327470307) covers them only as stage 4's commits, and it read `3845c53`; no later
  review re-read stage 4's commits until this record's fourth touch: the re-checks at
  `2f07c53` and the OKs at `d2bc30a` (6329313690, 6329982180, 6332076797, 6332521834)
  read the record's text and the post-D round's scripts. The re-checks of this record's
  fourth touch then read the appendix row by row, lane 3 also re-reading the bumps'
  logs, parents, diffs and trailers (lane 2, 6333755295; lane 3, 6333819643).
- **Every patch review ran on a base other than D's.** #192's on run C's legs and split
  (`73b04d6`, `593250d`, `69b8924`); #266's on lane 3's tree q4d, which is main `00d52ae`
  with #262 and #228's PRs 2 to 4; #299's on an empty-tree scratch repository and main's
  `tests.yml`; #196's on run C's split. D's stages 3 and 4 applied the patches to D's
  bases, and lane 3's re-check of the fourth touch replayed all seven on copies of
  them, each tree equal to stage 4's (6333819643; lane 2's replay agrees, 6334818560).
  Stage 3's `apply --check` and `am --3way` and stage 4's `am --3way` are each EXIT 0,
  and each commit's patch-id equals its patch's.
- **No green run of the whole `tests` job under row 2's `env`.** Lane 3's item 4 left it
  ("Not yet run: the whole `tests` job with the env. Rehearsal D's P3 job 4 covers it."),
  and P3's `standalone` job is RED in D for one case, #304 (P3, above). That job ran
  through `tests/run.sh` at a TMPDIR of 70, while the patched `tests` job runs plain
  `python3 -m pytest tests -q` (`tests.yml:157` at `56142ed741f9`), which #304's case does
  not reach. The legs' own CI comes after Gate C.
- **The cutover's ids are not predicted.** The split commit carries D's `execute` time
  (16:25:30Z), so it and the five assembly commits on it are D's ids; rows 1 to 4 carry
  stage 4's committer times (16:27:09Z to 16:27:10Z) and the rehearsal's committer, so all
  nine ids are D's. This table does not say that a real `execute` reproduces any id, and
  that was not tested.
- **Row 40's follow-up half is not refreshed.** Main's evidence for row 40 is run C's
  `gate-ab-evidence-2026-10-09.md` section 5 (`:448-537` at `33ce26d`): a patch table and
  a follow-up mapping of run C's 29 `follow_ups` (`adoption-plan.yaml:392–421` at
  `33ce26d`) to a patch, a PR, an owner or "deferred". The Gate B status note's row 40
  (`gate-b-status-2026-10-09.md:195`) cites it and says it "is refreshed once more at the
  final heads". This appendix refreshes the patch table only: D's plan has 42 follow-ups
  (Mapping), and run C's 29 are not mapped against them.
- **#266's review left three NITs that would change patch bytes, and none was applied.**
  Lane 3 calls them "worth fixing only if a patch is re-rolled for another reason" (PR
  #266 comment 6275785285), and lane 1 left the patches as they were, "as the review
  advised" (PR #266 comment 6278378293). D's pins are the unchanged bytes: for example,
  the re-cut's commit message still keeps the 2026-10-09 body above the dated paragraph,
  and `t009-assembly-caps.patch:66` still credits the 2026-10-08 entry with all
  twenty-four lines.
- **T008 has no patch, so it has no row.** Row 40 asks for every T006–T010 patch; T008 is
  the installer's coverage task, and its evidence is lane 2's matrix (row 27, under P5).
- **The review references are those of the patches, not of this table.** The table itself
  was reviewed at `167564c`: lane 2 verified all nine rows (#186 6333755295), and lane 3
  held it row by row and replayed all seven patches with `git am --3way` on copies of D's
  bases, with all seven trees equal to stage 4's (6333819643).
  Both lanes then passed `555bab1` (lane 2, 6334818560; lane 3, 6334668981).
