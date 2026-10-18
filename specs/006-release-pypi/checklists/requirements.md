# Specification Quality Checklist: Release tags, release branches and the `openrepotools` package on PyPI

**Purpose**: Validate specification completeness and quality before proceeding to planning
**Created**: 2026-10-17
**Feature**: [spec.md](../spec.md)

## Content Quality

- [x] No implementation details (languages, frameworks, APIs)
- [x] Focused on user value and business needs
- [x] Written for non-technical stakeholders
- [x] All mandatory sections completed

## Requirement Completeness

- [x] No [NEEDS CLARIFICATION] markers remain
- [x] Requirements are testable and unambiguous
- [x] Success criteria are measurable
- [x] Success criteria are technology-agnostic (no implementation details)
- [x] All acceptance scenarios are defined
- [x] Edge cases are identified
- [x] Scope is clearly bounded
- [x] Dependencies and assumptions identified

## Feature Readiness

- [x] All functional requirements have clear acceptance criteria
- [x] User scenarios cover primary flows
- [x] Feature meets measurable outcomes defined in Success Criteria
- [x] No implementation details leak into specification

## Notes

- Validated on 2026-10-17, in one iteration, against the governing OpenSpec
  change `release-tags-pypi`.
- **Named tools.** The spec names pipx, PyPI, bash, `tests.yml` and
  `release.yml`, because the governing change fixes them as the product's own
  surface. Brett Heap's words are "we will publish on pypi" and "look at the
  way we did this for openRepoShape". The `pypi-package` delta spec states
  its requirements in those terms. The spec leaves the module layout, the
  function names, the resolution algorithm and the step structure to
  plan.md. The content-quality items pass on that reading.
- **The readers.** They are Brett Heap and the lanes that build and release
  this toolset, so "non-technical" is read as "states outcomes, not code".
- **The technology in the success criteria.** SC-001 to SC-010 count
  outcomes: artifacts placed, facts printed, refusals, uploads. They name a
  tool only where the tool is the outcome, as with PyPI serving a version.
- **No `[NEEDS CLARIFICATION]`.** None remains. Brett Heap's choice of
  (a), (b) or (c) on workBenches, FR-047, is decided: spec.md's FR-047 says
  "decided: position (c)", and design.md's "Resolved by Brett Heap,
  2026-10-18", item 12, has his words "go with (c)" and
  opensoft/workBenches#165. It was never a blocker: it changes only when
  FR-045's README text may appear, and adds README's one-route sentence.
  The `release/*` ruleset choice and the v1.1.0 notes text are recorded as
  assumptions. The change already specifies both outcomes of the first, and
  the second is settled before the tag.
- **Coverage.** Every one of the delta specs' 25 requirements maps to a
  functional requirement: 17 in `pypi-package` and 8 in
  `release-tags-and-branches`. Their 49 scenarios are acceptance scenarios,
  edge cases or the exact text of a requirement. The spec adds no scope the
  proposal, design.md and clarifications.md do not hold.
- **Revised 2026-10-18** for the lead's rulings on the report at `335d226`.
  These were applied to the change's documents first, then to the spec:
  - FR-048, the repository guard;
  - FR-029's rehearsal rule, which the proposal and delta spec now state
    too;
  - pip's `/bin/sh` trampoline in FR-020;
  - a package-mode run's own release as the count line's source, in FR-019;
  - the wording of the unreadable-stamp clause and of the broken-stamp line;
  - the one term "venv-shaped";
  - "skipped" for the `pypi` job in an rc rehearsal;
  - the branch rehearsal's version, in FR-033.

  The delta specs gained two scenarios, a branch dispatch as a rehearsal and
  a final version in the wrong repository. Every item still passes.
- Items marked incomplete require spec updates before `/speckit.clarify` or `/speckit.plan`
