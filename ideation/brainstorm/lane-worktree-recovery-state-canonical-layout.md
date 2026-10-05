# Canonical Lane-Owned Worktree Layout — Brainstorm

Status: brainstorm
Kind: architecture
Summary: Give each lane a derivable worktree root beneath its home repository while keeping the coordinator in the canonical base checkout.
Topics: lane-worktree-recovery-state, canonical-worktree-layout, lane-directory, worktree-ownership
Repository context: openRepoTools lane orchestration, with openRepoShape and Speckit worktree-layout compatibility as a boundary
Captured: 2026-09-15

## Possible feats

- **Derivable lane root** — Resolve every lane-owned worktree without relying on a historical absolute path.
- **Coordinator-base invariant** — Require the lane coordinator to launch from its home repository's canonical base checkout.

## Focus

This document isolates where a lane and its worktrees live. Today `dir` is the exact directory from which a coordinator was launched; it can be a base checkout or a feature worktree, and legacy lanes may not record it at all. That makes recovery depend on historical paths and leaves the relationship between one coordinator and several writer worktrees implicit.

## Proposed model

Resolve a lane's stable repository identity from `home owner/repo` and `estate`. On each workstation, resolve that identity to the canonical base checkout. The coordinator always launches there. Lane-owned writer worktrees occupy a deterministic root derived from that checkout, conceptually:

```text
<home-base-parent>/worktrees/<canonical-lane>/
├── lane-state.yaml
├── tree-state/
│   └── <tree>.yaml
└── trees/
    └── <tree>/
```

The exact path must remain compatible with the estate's `project.yaml`, `SPECKIT_GIT_WORKTREE_ROOT`, and openRepoShape's feature-first worktree contract. A naive `..` calculation is insufficient for a three-leg estate. The invariant is derivability from repository identity and shape, not this illustrative spelling.

State files live beside the Git worktrees rather than inside them. That avoids making a checkout dirty, accidentally committing orchestration metadata, and losing the only record when a worktree directory disappears.

One lane may own many worktrees, but its coordinator has one launch directory. Each worktree receives a stable tree identifier and records its own repository, role, branch, HEAD, upstream, writer, and lifecycle state.

## Interfaces and boundaries

The layout consumes canonical lane name, `home`, `estate`, and shape configuration. It emits derivable paths and sidecar locations. It does not decide whether work is safe, whether a writer is live, or whether a missing worktree can be rebuilt.

Existing governed Speckit feature paths remain authoritative. Lane ownership may need to be an index over those paths rather than a second physical layout when moving them would violate the shape contract.

## Alternatives and tensions

- Keeping the coordinator in whichever worktree it last used preserves current flexibility but makes the lane's identity depend on mutable feature state.
- Putting `.lane-state` inside each worktree makes discovery local but dirties or disappears with the checkout unless special exclusion rules are reliable everywhere.
- Recording absolute paths is easy on one workstation but is not portable between host, container, and another workstation.
- Organizing physical worktrees by lane makes discovery simple; organizing them by feature preserves the existing Speckit contract. A sidecar lane index may reconcile both.

## Open questions

- Is the coordinator base the estate root, the lane's `home` repository checkout, or a declared coordination leg?
- Should lane-owned scratch worktrees and governed Speckit feature worktrees use different physical roots?
- What stable identifier names a writer tree when the branch is renamed?
- Is the sidecar local-only, workspace-replicated, or split between both?

## Relationships

The lifecycle written beneath this layout is defined in [Crash-Consistent Lane Lifecycle](lane-worktree-recovery-state-crash-consistent-lifecycle.md). Resume reconciles the layout against Git and processes as described in [Resume-Time Worktree Reconciliation](lane-worktree-recovery-state-resume-reconciliation.md).
