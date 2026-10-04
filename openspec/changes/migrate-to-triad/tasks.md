# Governance and Speckit handoff

The sole executable list is [004-migrate-to-triad/tasks.md](../../../specs/004-migrate-to-triad/tasks.md).
This checklist tracks governance, not duplicate implementation tasks.

## 1. Proposal and handoff

- [x] 1.1 Record the migration proposal, design, capability requirements,
  preliminary adoption mapping and sole linked Speckit feature; verify all
  artifacts exist and planning validation is recorded.
- [ ] 1.2 Approve the frozen source/standard revisions, repository visibility,
  final path mapping, follow-ups and active-work dispositions after Gates A/B;
  verify #97/#121 have landed, their content is accounted for through the
  refreshed baseline, and approval explicitly names the actual execution plan.

## 2. Migration evidence and closure

- [ ] 2.1 Accept exact assembled-head, preservation, feature-transition and
  rollback evidence from Speckit Gates C–E; verify required CI and ownership
  boundaries without enabling unrelated experimental runtime features.
- [ ] 2.2 Accept final tested spec reconciliation, amendment dispositions and
  approved-baseline correspondence; verify matched spec/code landings before
  completed assembly advancement. Close reconciliation after spec landing.
- [ ] 2.3 Archive only after the adopted assembly and selected leg pins land
  and continued work is accounted for; verify root delivery and recorded
  old-PR/worktree dispositions before closure.
