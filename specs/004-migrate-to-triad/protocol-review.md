# Migration protocol review — October 4, 2026

This refresh applies the adopted manual **Triad Feature Amendments** section
of the installed shared OpenSpec/Speckit workflow, including its
single-repository-to-triad migration instructions. Approval/extraction/history,
per-path verification and exact-pin mechanics remain governed by openRepoShape.
The consumer standard remains pinned at `39d5c986fcfac1a160474bfe91c5f1c37fccc72c`.

## Sources read

| Source identity | Snapshot SHA-256 |
| --- | --- |
| `$AGENT_PROTOCOL_ROOT/protocols/openspec-speckit-workflow.md` | `867b09a1329a2ba1c8005f2fbe43a4857f4eba7dd69c474c4e03d54bb2ecc20c` |
| `$AGENT_PROTOCOL_ROOT/protocols/project-agent-bootstrap.md` | `39341a7d0958e5efb9af5aa69de6e692d03129047cbcad48ad7f32bb8076ee28` |
| workBenches `docs/triad-feature-amendments.md` | `549d35974d42f474f2c7b2004e900b943c9a4543c479b97c541f47de1035f8d7` |
| workBenches `docs/triad-feature-amendment-templates.md` | `43647f4419dac8e28a3f428469ae27acd1444846736e9d388d967bb93c500a5f` |

The workBenches documents and governing
`openspec/changes/adopt-triad-feature-amendments/` were read from its working
branch, where they were uncommitted at inspection. These content digests identify
the reviewed drafts; they are not landed commit identities or distribution
evidence. The installed protocol records Brett Heap's October 4 adoption of
manual use. Schema, managed root routing, template distribution and upstream
placement automation remain pending in their owning repositories.

## Application to this migration

- Keep full proposals, archives, canonical specs/contracts and Speckit files
  in spec, including proposals authored on existing feature branches. Do not
  manufacture amendments for historical features.
- Put genuine bounded amendment records in the code feature folder
  `features/<NNN-feature>/openspec/`. Review them explicitly in the mapping
  until the upstream exception is qualified. No tracked amendment folders were
  observed in current main or retained feature heads.
- Preserve approved original repository/commit/path provenance and verify
  correspondence to extracted spec identities. Repair links/root selection;
  filtered hashes cannot be guessed or substituted for approval evidence.
- Update working Speckit instructions immediately for accepted bounded changes;
  record authority, requirements/tasks, evidence and dispositions manually.
  New runtime/capability/authority/external obligations use full governance.
- At the first amendment, create one spec reconciliation issue. Reconcile all
  net tested effects once at completion, linking landed code and evidence.
  Completed assembly advancement waits for matching reconciled spec/code pins.
  Archive only after implementation and assembly landing; explicitly select
  the full spec root and preserve inactive/archived history.

Implementation remains in [tasks.md](tasks.md); no external issue, schema,
protocol distribution, installation or migration was executed by this refresh.
