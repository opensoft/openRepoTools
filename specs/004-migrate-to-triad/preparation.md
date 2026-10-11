# Migration preparation evidence

**Initial observation:** October 4, 2026. The preservation and failed rehearsal
below are historical receipts. **October 6 update:** #97 and #121 have landed;
a candidate upstream fix and successful disposable current-main rehearsal are
recorded in [adopter-rehearsal.md](adopter-rehearsal.md). Gates A/B remain open.
Real conversion waits for the remaining baseline landings, a tested upstream
pin and refreshed execution approval. This evidence belongs to
[T001–T011](tasks.md); it is not another executable task list.

## Preservation evidence

Private backup ID: `prep-20261004T211123Z`. Exact locations, file lists,
configuration, indexes, binary patches and restore copies remain host-local,
outside the repository. No backup contents are published here.

- Source bundle: all 18 refs verified against a restored mirror and the live
  ref listing before/after capture. SHA256:
  `86213b096b6057a1d0fd64b2a950856a6aa8375f87641f49330d205635909c0e`.
- Dependency bundle: verified and restored the pinned standard commit.
  SHA256: `2549703215e77353129ebc4d73a5dc7f1f4fd07079b5d86cf259e91a662a20e4`.
- Six worktrees: copied tracked/untracked files and selected ignored workflow
  configuration, saved indexes and binary patches, verified restore-copy bytes
  and symlinks, and checked source HEAD/status/content stability during capture.
  Restored all six captured heads into independent Git clones, reconstructed
  the captured index entries, copied captured working/configuration bytes, and
  verified matching porcelain status, including #121's working edits. Preserved
  repository-local config/excludes separately; restoring the excludes was
  necessary to reproduce ignored workflow configuration. This is a restore
  rehearsal of the snapshots, not an owner-coordinated freeze or live rollback.
  Private Git restore summary SHA256:
  `550d1ce96c8a162c3371f95b53be188217f85fac6491e98e628ae307ea35b31e`.
- Installed files/settings/receipts: captured current configured/default and
  PATH locations in host and py-bench contexts. Host: 29 locations checked,
  27 present regular-file copies verified. Bench: 41 checked, 39 present copies
  verified. These are locations, not the installer artifact count. Additional
  profiles/workstations and actual installer rollback still need receipts.

| Captured worktree identity | HEAD | Restored files verified |
| --- | --- | ---: |
| main | `daed20957f2dd2f22cca24053bb5bc8636ff6b3f` | 130 |
| 001-separate-swap-ctx-handoff | `3c26041a4444a10bc240cb64a168ece4d9edf6c5` | 309 |
| 004-migrate-to-triad | `48934f8d4c662be6ed07ad1b7df96dec22028ab2` | 73 |
| feat/supervised-context-restart | `a9506724c1526a734b2c1b82990ffbb908c4daa4` | 81 |
| feat/claude-current | `11037f01a45a72fa3fc9a8a2b0e24a64cbf1ed12` | 63 |
| feat/crash-consistent-lane-worktree-recovery | `07fb3adb8b4ac1476c641685096f00f0d20593c6` | 74 |

All six were stable during their own capture. They are active observations;
heads differ from earlier local/remote snapshots and can change again.
Owner dispositions, retired-object preservation receipts and a final capture
at safe breakpoints remain required. This backup is local to this workstation.

Read-only GitHub lookups returned HTTP 404 for both proposed leg repository
names. That means they were not visible to the current credentials, not a
guarantee of name availability or creation permission. Recheck at Gate C;
public visibility remains a proposal requiring the final decision.

## Measured local rehearsal

Used main `daed20957f2dd2f22cca24053bb5bc8636ff6b3f` and unchanged standard
`39d5c986fcfac1a160474bfe91c5f1c37fccc72c`. A fresh single-branch source clone
had no linked worktrees. `git-filter-repo` 2.47.0 was installed into a private
venv for this rehearsal; existing bench/system installations were unchanged.
The package wheel SHA256 is
`2cd04929b9024e83e65db571cbe36aec65ead0cb5f9ec5abe42158654af5ad83`.

The standard's `check` passed. `execute --local-remote-dir ... --yes` used only
disposable local remotes. Network protocols were disabled except local file
transport; gh/curl shims refused network calls. The source clone and real main
remained at the recorded commit. No real repository, PR or lane was changed.

Execution returned **2** before an assembly split commit or final verification:

```text
git -c protocol.file.allow=always submodule add -q <local-spec-worktree> spec
fatal: please make sure that the .gitmodules file is in the working tree
```

Both extracted legs exist for diagnosis. Independent comparison of path,
mode and object ID accounts for all 64 original entries: 18 spec, 40 code and
six unchanged root entries in the candidate index; zero missing or duplicated
entries. This is partial extraction evidence, not the standard's completed
adoption report or a composed candidate.

| Temporary extracted leg | Commit | Kept commits |
| --- | --- | ---: |
| spec | `993d1e1d01c9ba28ecee003e518bc444cef7028b` | 25 |
| code | `ba5f25696ba24012731b356ddb91f10c5386a220` | 77 |

Code retains the original `.gitmodules`, dependency contract and gitlink at
the pinned SHA. Initializing that nested dependency through a local URL rewrite
passed. The pinned standard's own tree-digest helper recomputed
`a44c0165beb9d3b6ddfce46925bf04b8d19934d5327b5a304b5f3f11af699b02`,
matching the unchanged dependency contract. Full recursive assembly bootstrap
is blocked. The canonical
`tests/run.sh -k upstream_pin` remained in its serialization wait; the owned
waiting wrapper was stopped after 45 seconds. No pytest assertion ran and no
test pass is claimed. The preceding unfiltered waiting attempt also never ran
tests. Do not bypass the wrapper to obtain a pass.

See the [upstream reproduction](adopter-blocker.md) and
[installer design and compatibility matrix](installer-design.md).

## Resume after the PR landings

PRs #97/#121 are now merged; #168/#169/#174 and draft #172 remained open on
October 6. Their landing notifications trigger a fresh read of actual main
and owner state. Landed changes are accounted for through the new baseline;
remaining branch deltas and local edits still need dispositions. Existing
PR holds and review history are preserved until their owners settle them.

Regenerate the mapping using the standard rather than editing its source SHA.
Resolve the adopter defect through upstream review, a commit on upstream main
and the recomputed pin/gitlink update. Repeat into fresh local remotes, then
prepare and test follow-up patches against the successfully verified split.
Repeat preservation at coordinated breakpoints. Gates A/B and explicit Gate C
approval still precede real repositories, root landing and live lane rebinding.

No execution task is checked complete by this provisional evidence.
