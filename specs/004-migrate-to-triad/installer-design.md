# Installer follow-up design and compatibility matrix

Prepared for [T007–T010](tasks.md), against main `daed20957f2dd2f22cca24053bb5bc8636ff6b3f`.
Implementation patches wait for successful standard split verification. PRs
#97/#121 can change payloads and tests; refresh this inventory after landing.

## One implementation, two entry contexts

Keep the current implementation in code. Add a small assembly `openRepoTools`
entry point that selects that implementation; preserve the documented raw and
gh installation one-liners. Installed `openRepoTools` remains the code
implementation so it runs independently of developer worktrees. The assembly
entry point must delegate all installation, merging, ownership and retirement
mechanics to it.

The root entry point alone is insufficient: subsequent installed `--install`,
`--skill` and WIP template operations currently fetch from the monorepo's
`REPO`/`REF`. Those code-side consumers need the same payload-source resolution.
Separate the selected assembly source from the resolved code payload source;
keep the existing public `OPENREPOTOOLS_REPO`/`OPENREPOTOOLS_REF` meanings.
Do not infer a code repository by appending `-code` to a fork name.

For an adopted remote, resolve the requested assembly ref once to an immutable
commit. Read `contracts/code-pin.yaml` at that commit, strictly validate the
code role, repository slug, commit, path and digest grammar, and confirm the
assembly gitlink agrees. Fetch the implementation and all its payloads from
that same code repository/commit. Moving branches cannot mix artifact versions.
A present malformed pin must refuse rather than fall back to the legacy layout.

For a legacy monorepo with no adoption manifest/pin, retain the established
owner/repository/ref override path. Distinguish an authoritative missing path
from authentication, transport and parse errors; those errors are refusals,
not evidence of a legacy repository. Forks use their selected assembly pin.
gh-first and curl fallback apply to the same resolved identities. Reuse jq
where needed; no new general YAML runtime dependency is justified by a fixed
pin grammar. Do not claim whole-tree digest validation from one downloaded
file: the composed validator checks the complete tree, while remote installation
must at least verify the gitlink and immutable identity it actually consumes.

For a local adopted checkout, require a consistent assembly/code pin and
materialized selected payload set, then copy those local bytes offline. An
explicit code feature checkout must remain a supported development context;
record its actual code identity without pretending it is the assembled pin.
Incomplete local payloads must refuse or fetch only from the established
matching source; arbitrary local siblings plus unrelated remote bytes must not
form a successful adopted install. Define this distinction in the implementation
and user-facing diagnostics before acceptance. Preserve normal legacy sibling
behavior where the legacy installer currently promises it.

## Code consumers that change

| Existing consumer | Required adjustment |
| --- | --- |
| `fetch_from_repo` | Use the resolved payload repository/immutable revision for code assets; retain transport fallback and useful refusal output. |
| `collect_commands`, `collect_skills` | Establish coherent local/remote source before collecting; preserve all-before-placement staging. |
| `wip_shape_ref` | Read/fetch code's `contracts/openreposhape-pin.yaml`, distinct from assembly's code pin. Preserve its existing upstream-standard role. |
| `wip_fetch_template_file` | Continue selecting the template from the upstream standard pinned by code; do not repoint templates to spec or assembly. |
| Root entry point | Resolve/select/delegate; forward arguments, exit status and signal/temporary-file cleanup. It adds no installer mechanics. |
| Installed receipts, settings/hook merge and retire functions | Preserve existing ownership, mode, target and refusal behavior; source routing must finish before placement. |

Current command/data payloads are the 15 names in `INSTALLABLES`, including
`claude-current` and `claude-restart-check`. Three skills and three command
files each have two destinations: 27 placed files plus two hook entries, 29
artifacts. Derive counts from the lists; source comments with historical counts
are not the contract. Hooks stay in the user's existing settings, preserving
unrelated entries. No machine-specific config enters a payload archive.

## Compatibility acceptance

All rows below are pending measured tests in fresh disposable homes/remotes.
They describe coverage for the existing executable tasks, not completion claims.

| Scenario | Required observation |
| --- | --- |
| Existing raw/gh one-liners | Root delegates to selected code implementation; same names, help and destinations. |
| Offline local legacy / adopted checkout | Legacy behavior retained; complete adopted payload copied without network and pinned identity checked. |
| Explicit local code feature | Intentional feature bytes selected coherently and actual identity recorded. |
| Installed reinstallation and skill-only operation | Works without the developer checkout and resolves the selected assembly/code source. |
| Legacy override / adopted fork | Existing overrides work; fork follows its actual code pin rather than a guessed repository. |
| Branch, tag, commit and slash-containing refs | Ref resolved once; every remote payload uses one immutable code identity. |
| Branch changes between downloads | No mixed versions; subsequent requests use the frozen identity. |
| Missing pin in valid legacy / partial adopted layout | Valid legacy permitted; adopted missing/malformed/mismatched pin refused. |
| Missing or malformed API response / authorization / transport failure | No silent legacy fallback; actionable refusal, no placed files. |
| Changed local gitlink / changed payload / incomplete local payload | Coherence decision enforced before staging/placement; no unrelated-source mix. |
| Missing command, skill, alias or failed settings merge | Existing all-before-placement guarantee holds; prior install remains unchanged. |
| Modes, ownership receipts and custom target paths | Same modes and computed targets; foreign files and unrelated hook entries preserved. |
| WIP init/template lookup | Code dependency pin selects upstream templates; workspace writer restrictions unchanged. |
| Missing nested dependency in standalone code | Existing documented test skips remain; composed acceptance requires complete dependencies. |
| Linux/macOS Bash 3.2 and Windows/WSL policies | Correct parses/platform gates; no new Bash features or PowerShell implementation. |

Tests and fixtures need explicit **code**, **spec**, **assembly** and
**dependency** roots. In particular, `tests/test_repo_hygiene.py` reads the root
README/install line and agent guidance, while `tests/test_upstream_pin.py`
reads code Git identity and the nested dependency. CI must supply the matching
contexts rather than delete those checks. Keep `tests/run.sh` as the serialized
test entry point, selecting with pytest filters such as `-k upstream_pin`.
The assembly exact-pin integration job must refuse absent required contexts.
