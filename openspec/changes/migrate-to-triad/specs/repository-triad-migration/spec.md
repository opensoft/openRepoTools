# Repository triad migration

## Purpose

Convert the existing openRepoTools repository to a pinned assembly/spec/code
project while preserving history, unfinished work and supported installation.

## ADDED Requirements

### Requirement: Adoption preserves source identity and accounts for content

The migration SHALL retain the existing repository name, identity and full
published history. It SHALL freeze a reviewed source commit and account for
each tracked source path by blob or gitlink identity in exactly one leg/root,
or an explicitly approved drop. It SHALL refuse stale/unresolved mappings and
SHALL NOT force-push the original history or weaken verification to pass.

#### Scenario: Source changes after plan generation
- **WHEN** the default-branch commit differs from the reviewed adoption plan
- **THEN** execution SHALL require regenerated mapping/checks and renewed
  approval of the actual baseline before creating real repositories.

#### Scenario: Existing nested dependency is extracted
- **WHEN** the code leg receives the mounted standard dependency
- **THEN** its registration, exact gitlink and coupled pin SHALL remain valid
  and SHALL be demonstrated by local rehearsal and recursive bootstrap.

### Requirement: Active work is preserved before cutover

The migration SHALL inventory open PRs, all branches/worktrees, detached work,
dirty/untracked files and local workflow configuration. It SHALL preserve
their contents and recovery evidence before cutover, including work absent
from the default branch. Each continued feature SHALL have a reviewed
old-to-new mapping and validated spec/code/root changes before rebinding.
Original worktrees and installed tools SHALL remain available until acceptance.

#### Scenario: Swap feature has uncommitted proposal and code work
- **WHEN** source main is extracted without those feature changes
- **THEN** the migration SHALL retain complete original feature contents and
  migrate the reviewed delta separately, preserving feature identity and roles
- **AND** absence from the extracted main SHALL NOT imply abandonment.

### Requirement: Installation retains the public interface and one revision

Existing one-line installation, command names, payload destinations/modes,
skills/hooks/receipts and supported fork/ref/local invocation SHALL remain
usable. An adopted assembly entry point SHALL resolve one immutable code
revision for the complete installation. Missing/inconsistent pin evidence
SHALL refuse before partial installation. Installed tools SHALL function
without a developer assembly checkout.

#### Scenario: Assembly code main advances independently
- **WHEN** the operator installs from a selected assembly revision
- **THEN** every payload SHALL come from that revision's selected code commit
  rather than whichever code main tip exists at request time.

#### Scenario: Offline checkout installation
- **WHEN** a complete local adopted checkout is used without network access
- **THEN** installation SHALL use its verified local payload and preserve the
  existing all-or-none installation and refusal behavior.

### Requirement: Project workflow operates across the pinned legs

The assembly SHALL own project workflow and its manifest/pins; product
OpenSpec/Speckit artifacts SHALL live in spec, implementation in code.
Continued features SHALL use paired leg worktrees with preserved feature IDs.
Delivery SHALL land leg changes and select them through a root pin bump.
CI SHALL test the exact composed state without silently skipping required
cross-leg tests. The standard dependency SHALL remain unedited in place.

#### Scenario: Implementation and specification land separately
- **WHEN** new leg commits are ready for project delivery
- **THEN** root gitlinks, pin records and workflow commit references SHALL move
  together through the established pin-bump procedure and integration checks.

### Requirement: Execution and cutover require reviewable evidence

Real execution SHALL require an explicit approved plan, visibility, baseline,
mapping and follow-ups. A local bare-remote rehearsal, preservation receipts,
compatibility checks and required platform/CI checks SHALL precede cutover.
Execution SHALL use a clean isolated source clone without linked worktrees.
Failed verification SHALL retain the source/work and stop landing; rollback
SHALL restore a reviewed prior state without destructive history rewriting.

#### Scenario: Preparation is complete but approval is absent
- **WHEN** mapping and planning validation have passed without execution approval
- **THEN** the migration SHALL remain a plan and SHALL create no real leg
  repositories, move no lanes and change no installed tools.
