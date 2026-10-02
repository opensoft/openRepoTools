# Separate Swap, Context Clear, and Handoff — Brainstorm

Status: brainstorm
Kind: architecture
Summary: Give account changes, context resets, and work transfers distinct operations and preservation contracts.
Topics: lane-session-operations, command-semantics, ctx, semantic-handoff, profile-switch
Repository context: openRepoTools command contracts with workBenches profile launchers
Captured: 2026-09-16

## Possible feats

- **Three explicit operations** — Make an account switch reuse native session history, a context reset create fresh context, and a handoff explain work to another reader.

## Focus

The current `/swap` command invokes the handoff skill. Amendment 17 deliberately made swap and handoff one act. The user now requests a different contract, beginning with Claude. This document captures that requested direction; it does not amend the protocol by itself.

## Proposed model

| Operation | Purpose | Conversation | Preservation | Default account behavior |
| --- | --- | --- | --- | --- |
| `swap` | Continue work using another login account | Resume the exact saved coordinator and supported worker conversations | Native transcripts and a mechanical operation record | Explicitly selected, already authenticated target profile |
| `ctx` | Recover context capacity | Start a fresh coordinator conversation | A deliberate semantic context checkpoint plus worker inventory | Keep the account unless a separate account change is requested |
| `handoff` | Transfer understanding and responsibility | Recipient may use a different session, agent, person, or machine | Human-readable state, obligations, writer ownership, and resume instructions | No implied profile selection or automatic restart |

An account profile selects credentials. A lane is stable work identity. A transcript is conversation identity. A process is a running instance. Those four identities must remain distinguishable in records and user messages.

`swap` does not reduce the resumed conversation's context usage. `ctx` does not replenish account quota. A cross-agent move belongs to handoff until an independently specified migration mechanism exists.

## Interfaces and boundaries

Proposed primary surface: `lane swap <lane> --profile <profile>`. A terminal hotkey can invoke it outside the model. These are proposed interfaces, not commands shipped today. A retained `/swap` requires proven interception before model dispatch; a prompt-backed skill cannot meet a zero-model-call contract merely by invoking shell code.

`/ctx` and `/handoff` may use model work because they preserve meaning across a change in context or reader. They can share deterministic restart/storage primitives with swap without sharing its semantic workflow.

## Alternatives and tensions

Keeping all three as aliases is compatible with current instructions but retains the token and latency cost the user wants to remove. Changing aliases immediately would leave older clients following conflicting protocol instructions. A versioned migration must name the change and retire the alias relationship deliberately.

## Open questions

- Can the installed Claude frontend intercept `/swap` without sending a model request, or should the first release expose only terminal and hotkey entry points?
- Which protocol amendment and installer release establish the new meanings together?

## Relationships

- [External supervisor](lane-session-operations-external-supervisor.md)
- [Claude-first synthesis](lane-session-operations-synthesis-claude-first.md)
