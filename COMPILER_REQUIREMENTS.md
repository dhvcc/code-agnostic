# Compiler Requirements

This is a handoff note for the backend/compiler work behind `code-agnostic` / `llm-sync`.

The main goal is simple: source config should fully express intent once, and the compiler should emit correct OpenCode/Codex/Cursor outputs without prompt duplication, silent capability loss, or conflict spam.

## Highest-priority bugs

## 1. Agent tool maps are not preserved reliably

Source intent is currently stronger than compiled output.

Concrete examples:

- Source: `agents/bugfix.md`
  - has:
    - `sentry_*: true`
    - `sailadv-sentry_*: true`
    - `sailadv-atlassian_*: false`
- Compiled: `~/.config/opencode/agents/bugfix.md`
  - tool map is dropped entirely
- Compiled: `~/.codex/agents/bugfix.toml`
  - equivalent tool controls are also absent

- Source: `agents/code-reviewer.md`
  - has:
    - `write: false`
    - `edit: false`
- Compiled: `~/.config/opencode/agents/code-reviewer.md`
  - kept `write: false`
  - dropped `edit: false`

Required fix:

- Preserve full frontmatter/maps for agent tool config.
- Support booleans and globbed tool names.
- Do not silently degrade mixed maps.
- If a target app cannot represent a rule, emit a compile warning or fail in strict mode.

## 2. `always_apply` / `alwaysApply` is not implemented

Concrete examples:

- `workspaces/sailadv/rules/efficiency-and-subagents.md`
- `workspaces/sailadv/rules/sailadv-stage-and-testing-guardrails.md`

Both are authored as always-on rules, but the current workaround is to duplicate their content into `workspaces/sailadv/AGENTS.md`.

Required fix:

- Implement `always_apply` / `alwaysApply` as a first-class source attribute.
- Respect target-specific behavior:
  - inject where the app supports always-on rules
  - fall back deterministically where it does not
- Avoid requiring the same rule text in both rule files and compiled `AGENTS.md`.

## 3. Generated artifact ownership/conflict handling is too noisy

`code-agnostic apply` currently reports a very large number of `conflict: non-managed path exists` results for compiled workspace artifacts.

This makes it harder to see real problems and makes the sync story feel fragile.

Required fix:

- Tighten ownership tracking for generated files.
- Distinguish clearly between:
  - managed generated file,
  - unmanaged file created by user,
  - previously generated but drifted file,
  - orphaned generated file after source removal.
- Add explicit resolution modes such as:
  - `strict`
  - `takeover`
  - `adopt`
  - `skip`

## 4. Source intent needs a target capability matrix

The compiler currently has to bridge different app capabilities, but this is not explicit enough.

Example:

- OpenCode MCP scoping is still more reliable via legacy `tools` glob gating than newer `permission` rules for some MCP cases.
- Source should express intent once; compiler should choose the correct target encoding.

Required fix:

- Maintain an explicit capability matrix per target app.
- Compile semantic intent, not raw field copying.
- Example semantic source intent:
  - `disable sentry globally`
  - `enable sentry only for bugfix agent`
- Compiler should emit the best supported target representation.

## 5. Canonical source paths must never be regenerated accidentally

Observed behavior:

- `workspaces/sailadv/skills/sailadv-mcp-playbook/SKILL.md` was removed from source.
- After `code-agnostic apply`, the file reappeared.

That suggests the compiler/source boundary is not strict enough.

Required fix:

- Define canonical source roots explicitly.
- Never recreate deleted source files from manifests, snapshots, or generated outputs.
- Limit write/remove operations to:
  - generated target roots, and
  - explicit state/manifest directories.
- Add a hard safety check that fails if apply would write into a canonical source path unless the command is an intentional source-generation mode.

## Feature requests

## 1. Source attributes to support

The source format should support these attributes directly:

- `alwaysApply`
- `targets`
- `profiles`
- `agents`
- `priority` or `order`
- `extends`
- `dedupeKey`
- `enabledWhen`
- `hidden`

Meaning:

- `targets`: emit only for selected apps
- `profiles`: apply to `global`, `commercial`, `sailadv`, etc.
- `agents`: bind rule/skill/tool policy to specific agents only
- `priority` / `order`: deterministic merge order
- `extends`: inherit base definitions instead of copy-pasting
- `dedupeKey`: intentionally collapse equivalent content
- `enabledWhen`: conditional compilation by app/workspace/profile
- `hidden`: for subagents that should be invokable programmatically but not shown prominently

## 2. Per-agent tool-policy compilation

Needed capabilities:

- global deny + agent allow
- agent deny + specialist agent allow
- glob-based tool selection
- MCP-family allow/deny rules
- target-specific encoding for OpenCode/Codex/Cursor

This is the key feature needed to keep Sentry only on `bugfix`, Atlassian only on planner-style agents, and noisy tools away from general agents.

## 3. Pass-through preservation for frontmatter maps

The compiler should not drop structured frontmatter unless it has a deliberate reason.

Required behavior:

- preserve unknown fields when safe
- preserve known nested maps fully
- warn on lossy transforms
- support strict mode that fails on lossy transforms

## 4. Generated-file provenance

Every generated file should carry machine-readable provenance in either metadata or manifest form.

Minimum needs:

- source path
- source checksum
- target path
- target app
- generation timestamp
- compiler version

This is needed for adoption, drift detection, and safe cleanup.

## 5. Manifest and doctor mode

Add two utilities:

- `code-agnostic apply --dry-run`
- `code-agnostic doctor`

`doctor` should detect:

- missing source paths
- broken compiled links
- duplicate instruction blocks
- lossy compiled agent configs
- orphaned generated files
- unsupported attributes for current targets
- stale target files vs source manifest

## 6. Dedupe and similarity linting

The compiler should help prevent prompt bloat.

Needed checks:

- detect near-duplicate rule/skill/AGENTS text
- warn when workspace skills duplicate global AGENTS principles
- warn when the same rule is duplicated in both `AGENTS.md` and always-on rule files

## 7. Secret reference support

Source configs should prefer secret references over inline tokens.

Needed support:

- env-backed values
- file-backed values
- app-specific interpolation when target syntax differs

This is partly hygiene and partly portability.

## Acceptance criteria

The compiler work is good enough when all of the following are true:

- Source `agents/bugfix.md` compiles to downstream configs with Sentry-only tool access preserved.
- Source `agents/code-reviewer.md` compiles without dropping `edit: false`.
- `alwaysApply` rules no longer require manual duplication into workspace `AGENTS.md`.
- `code-agnostic apply` output is dominated by meaningful changes, not walls of conflict noise.
- Lossy target transforms are surfaced explicitly instead of happening silently.
- One semantic source definition can compile correctly across OpenCode, Codex, and Cursor.

## Suggested implementation order

1. Preserve agent tool maps correctly
2. Implement `alwaysApply`
3. Add target capability matrix and semantic tool-policy compilation
4. Add provenance/manifest support
5. Add doctor/dry-run/lint flows
6. Add dedupe/similarity checks

## Notes

- Current setup now relies on source-only changes plus `code-agnostic apply`; downstream files should be treated as compiled artifacts.
- The biggest immediate practical blocker is tool-policy compilation, because that is what keeps MCP clutter out of the wrong agents.
