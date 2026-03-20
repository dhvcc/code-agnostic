# Roadmap: strict compiler, no default symlinks

## Progress

- [x] Phase 0: compiler contract documented in repo and linked from `README.md`
- [ ] Phase 1: strict bundle loading and schema validation
- [ ] Phase 2: dedicated compiler package and capability evaluation
- [ ] Phase 3: generated artifact planning replaces default symlink planning
- [ ] Phase 4: transactional apply and rollback
- [ ] Phase 5: validation and lossiness CLI UX

Current progress inside Phase 1:

- [x] Added a new `code_agnostic.spec` package for strict canonical loading
- [x] Added local v1 schemas for rules, skills, agents, and MCP
- [x] Added test coverage for valid bundles, unknown keys, missing `prompt.md`, and invalid MCP server shapes
- [x] Wired rule bundle discovery into `RulesRepository`
- [x] Added YAML `mcp.base.yaml` loading through existing source repositories
- [x] Wired skill and agent bundle parsing into current planner/app flows
- [ ] Remove legacy symlink-first behavior for legacy source formats
- [ ] Wire bundle loading into import/migration flows

Current progress inside Phase 3:

- [x] Global app sync now generates skill files for legacy and bundle sources
- [x] Cursor global app sync now generates agent files for legacy and bundle sources
- [x] Default sync now generates workspace/root/repo artifacts instead of planning symlink actions

Current progress inside Phase 4:

- [x] Executor now rolls back applied file changes when a later action fails
- [x] Successful applies now persist per-root revision manifests and active revision pointers
- [x] Failed applies now restore the last successful revision from manifest snapshots when available
- [x] Removed the remaining ad hoc backup-file recovery helper in favor of manifest-backed rollback

Current progress inside Phase 5:

- [x] Added `code-agnostic validate` for global and workspace canonical source checks
- [x] Added `code-agnostic explain-lossiness`

## Handoff

Latest completed slice:

- removed the obsolete `.bak-*` helper after rollback moved to manifest-backed recovery
- kept utility coverage focused on behavior still used by the product surface
- full test suite was green after that slice: `uv run pytest`

Next slice I was about to implement:

- include richer manifest inputs, like source files, so revision restore has compiler context
- add a real restore command or internal primitive that can replay an active revision on demand

Why I did not start import/migration changes:

- importing agents directly into bundle directories is underspecified right now
- legacy canonical agents still use `agents/<name>.md`, while bundle agents use `agents/<name>/`
- changing import without a clear migration rule would create real file-vs-directory collisions for the same agent name
- that needs an explicit product decision before implementation

## Why this exists

The project already acts like a cross-app compatibility layer, but the contract is implicit and spread across code. That is why it still feels alpha:

- Canonical resources are loose markdown/YAML files with silent field dropping.
- Sync uses a mixed model: symlink where possible, compile where necessary.
- Rollback is backup-based, not transactional.
- App-specific behavior leaks into source files and undocumented quirks.
- There is no single compiler spec, capability matrix, or lossiness report.

The goal of this roadmap is to turn `code-agnostic` into a strict, documented compiler with one-way generated outputs and predictable cross-app behavior.

## Decisions

### 1. Default sync must stop using symlinks

This is a hard yes.

Symlinks are convenient for prototyping, but they break single ownership, make rollback awkward, and force planner/executor special cases. Generated files should be the default output for every app. Symlink mode can remain as an explicit dev/debug option if it still helps local iteration, but it must stop being the default sync primitive.

### 2. Do not move to JSON-only authoring

This is also a hard yes.

Prompt-heavy assets are bad to author as escaped JSON strings. We still want strict validation and editor help, so the source format should be:

- `meta.yaml`
- `prompt.md`

YAML gives us schema validation and editor tooling. Markdown keeps prompts readable. This is a better tradeoff than markdown frontmatter because frontmatter inside `.md` is much harder to validate and autocomplete reliably.

### 3. Unknown properties must fail validation

The compiler must only accept properties we explicitly support. Unknown keys, misplaced keys, and unsupported combinations must fail fast with a clear diagnostic. We should stop forwarding unknown fields into generated outputs.

### 4. The compiler should live in its own package inside this repo

Blunt answer: yes, separate it.

Do **not** create a separate repository or publish a standalone compiler package yet. That would add versioning and release overhead too early.

Do create a dedicated package inside this repo, for example:

```text
code_agnostic/compiler/
code_agnostic/spec/
docs/compiler/
```

Reason:

- current compile logic is scattered across `agents/`, `skills/`, `rules/`, and `apps/*/service.py`
- the compiler needs its own docs, capability matrix, diagnostics, and tests
- app packages should become thin emitters/adapters, not the place where canonical semantics live

## Current state to replace

Today the repo mixes linking and compilation:

- rules compile into `AGENTS.md` or `.mdc`
- Cursor syncs skills and agents as symlinks
- Codex and OpenCode symlink skills but compile agents
- workspace rules compile into `AGENTS.md` and then get linked into workspace roots
- executor applies actions sequentially and relies on ad hoc backups for some writes

Relevant code seams:

- [README.md](/Users/alexeyartishevsky/PycharmProjects/llm-sync/README.md)
- [code_agnostic/planner.py](/Users/alexeyartishevsky/PycharmProjects/llm-sync/code_agnostic/planner.py)
- [code_agnostic/executor.py](/Users/alexeyartishevsky/PycharmProjects/llm-sync/code_agnostic/executor.py)
- [code_agnostic/apps/cursor/service.py](/Users/alexeyartishevsky/PycharmProjects/llm-sync/code_agnostic/apps/cursor/service.py)
- [code_agnostic/apps/codex/service.py](/Users/alexeyartishevsky/PycharmProjects/llm-sync/code_agnostic/apps/codex/service.py)
- [code_agnostic/apps/opencode/service.py](/Users/alexeyartishevsky/PycharmProjects/llm-sync/code_agnostic/apps/opencode/service.py)

## Target end state

### Source of truth

Canonical resources become bundle directories:

```text
config/
  mcp.base.yaml
rules/
  python-style/
    meta.yaml
    prompt.md
skills/
  code-reviewer/
    meta.yaml
    prompt.md
agents/
  architect/
    meta.yaml
    prompt.md
```

Rules:

- `meta.yaml` is strict and schema-validated
- `prompt.md` is plain markdown only
- source files are app-agnostic unless a field is explicitly namespaced
- app-specific extensions live under `x-cursor`, `x-codex`, `x-opencode`

### Generated outputs

Generated files become the only normal sync result:

- Cursor: `.cursor/rules/*.mdc`, `.cursor/agents/*`, `.cursor/skills/*`, `mcp.json`
- Codex: `AGENTS.md`, `.codex/agents/*.toml`, `.agents/skills/*`, `config.toml`
- OpenCode: `AGENTS.md`, `.opencode/agents/*`, `.agents/skills/*`, app config JSON

No generated output should be a symlink by default.

### Compiler behavior

Compiler responsibilities:

- validate canonical input against a versioned spec
- reject unknown fields
- produce deterministic app outputs
- emit warnings for lossy mappings
- emit errors for unsupported required mappings
- generate a manifest with checksums for each applied revision
- support rollback to the previous successful revision

## Canonical spec

Use a versioned compiler spec from day one:

- `spec_version: v1`
- `kind: rule | skill | agent | mcp`
- namespaced vendor blocks only under `x-*`
- no unscoped vendor keys

Suggested package split:

```text
code_agnostic/spec/
  models.py
  loaders.py
  validators.py
  schemas/
    agent.v1.schema.json
    skill.v1.schema.json
    rule.v1.schema.json
    mcp.v1.schema.json

code_agnostic/compiler/
  diagnostics.py
  capabilities.py
  manifest.py
  planner.py
  staging.py
  transaction.py
  emitters/
    cursor.py
    codex.py
    opencode.py
```

JSON Schema is still fine here even though authoring is YAML. YAML editors can validate against published JSON Schemas.

## Capability docs we must ship

The compiler must have real docs, not just code. These docs should live under `docs/compiler/` and be linked from `README.md`.

Required docs:

- `docs/compiler/overview.md`
- `docs/compiler/skills.md`
- `docs/compiler/agents.md`
- `docs/compiler/rules.md`
- `docs/compiler/mcp.md`
- `docs/compiler/lossiness.md`

Each doc must answer:

- which canonical properties exist
- which are required vs optional
- which apps support them
- whether support is native, compiled, ignored, or rejected
- what diagnostics appear when a field cannot be represented

## Capability matrix format

Use one status per app/property cell:

- `native`: target supports it directly
- `compiled`: compiler rewrites it into target-native output
- `ignored`: compiler accepts it but intentionally omits it for that target, with warning if behavior changes
- `rejected`: compiler refuses the resource for that target

### Skills matrix

This table should exist in `docs/compiler/skills.md`:

| Property | Compiler | Cursor | Codex | OpenCode |
| --- | --- | --- | --- | --- |
| `name` | supported | compiled | compiled | compiled |
| `description` | supported | compiled | compiled | compiled |
| `tools.read` | supported | compiled | compiled | compiled |
| `tools.write` | supported | compiled | compiled | compiled |
| `tools.mcp` | supported | compiled | compiled | compiled |
| `prompt.md` body | supported | compiled | compiled | compiled |
| `x-cursor.*` | supported | native or compiled | ignored | ignored |
| `x-codex.*` | supported | ignored | native or compiled | ignored |
| `x-opencode.*` | supported | ignored | ignored | native or compiled |

### Agents matrix

This table should exist in `docs/compiler/agents.md`:

| Property | Compiler | Cursor | Codex | OpenCode |
| --- | --- | --- | --- | --- |
| `name` | supported | compiled | compiled | compiled |
| `description` | supported | compiled | compiled | compiled |
| `model` | supported | compiled | native | native |
| `reasoning_effort` | supported | ignored or compiled | native | native |
| `sandbox_mode` | supported | ignored | native | ignored |
| `nickname_candidates` | supported | ignored | native | ignored |
| `tools.read` | supported | compiled | rejected or ignored | compiled |
| `tools.write` | supported | compiled | rejected or ignored | compiled |
| `tools.mcp` | supported | compiled | rejected or ignored | compiled |
| `codex.mcp_servers` | supported | ignored | native | ignored |
| `codex.skills.config` | supported | ignored | native | ignored |
| `prompt.md` body | supported | compiled | compiled | compiled |

The Codex cells above need to be pinned to actual behavior during implementation. Do not guess. Document exactly what the target accepts.

### Rules matrix

This table should exist in `docs/compiler/rules.md`:

| Property | Compiler | Cursor | Codex | OpenCode |
| --- | --- | --- | --- | --- |
| `description` | supported | native | compiled | compiled |
| `globs` | supported | native | ignored | ignored |
| `always_apply` | supported | native | ignored | ignored |
| `prompt.md` body | supported | native | compiled | compiled |
| `x-cursor.*` | supported | native | ignored | ignored |

This makes the tradeoff explicit: `globs` and `always_apply` are Cursor-oriented semantics unless another app gains a real equivalent.

### MCP matrix

This table should exist in `docs/compiler/mcp.md`:

| Property | Compiler | Cursor | Codex | OpenCode |
| --- | --- | --- | --- | --- |
| `type` | supported | compiled | compiled | compiled |
| `command` | supported | native | native | native |
| `args` | supported | native | native | native |
| `url` | supported | native | native | native |
| `headers` | supported | native | compiled | native |
| `env` | supported | native | compiled | native |
| `auth.client_id` | supported | compiled | compiled | compiled |
| `auth.client_secret` | supported | compiled | compiled | compiled |
| `auth.scopes` | supported | compiled | compiled | compiled |
| `auth.token_endpoint` | supported | compiled | compiled | compiled |
| `timeout` | planned | document per app | document per app | document per app |

If a property is not modeled in the compiler, it does not belong in user source files.

## Transactional sync model

The new apply path should be staged and reversible:

1. Load and validate all canonical resources.
2. Compile every target artifact in memory.
3. Write artifacts into a staging directory.
4. Validate staged artifacts again where app schemas exist.
5. Write a revision manifest with checksums and target paths.
6. Atomically swap staged files into place.
7. Persist the successful revision as the active revision.
8. On failure, do not partially apply; either keep the previous revision or roll back to it.

Manifest should record:

- revision id
- timestamp
- source files included
- target files emitted
- checksums
- app target
- workspace target when relevant

Rollback should restore the last successful revision, not whichever files happened to get `.bak-*` copies.

## Migration plan

### Phase 0: lock the contract in docs

1. Define the canonical format and compiler package layout in docs.
   verify: docs merged, examples are unambiguous, and no open naming conflicts remain.
2. Add capability matrix docs for skills, agents, rules, and MCP.
   verify: every currently supported source property appears in one matrix.
3. Update `README.md` to describe generated outputs instead of symlink-first sync.
   verify: README no longer advertises symlink-based skills/agents as the core model.

### Phase 1: introduce strict spec loading

1. Add failing tests for bundle loading and schema validation.
   verify: invalid keys, unknown keys, and missing required fields fail.
2. Implement `meta.yaml` + `prompt.md` loaders for rules, skills, agents, and MCP.
   verify: valid fixtures round-trip into typed models.
3. Add migration readers for current markdown/frontmatter inputs.
   verify: legacy fixtures can still be imported or converted with no semantic loss for supported fields.

### Phase 2: separate compiler from app services

1. Add failing tests for capability evaluation and diagnostics.
   verify: each lossy mapping produces a deterministic warning or error.
2. Move canonical compile logic into `code_agnostic/compiler/`.
   verify: app services become thin wrappers that call the compiler.
3. Add explicit target capability definitions.
   verify: no target behavior depends on hidden `if` branches in parsers or services.

### Phase 3: replace symlink planning with generated artifacts

1. Add failing planner/executor tests that expect regular files, not symlinks.
   verify: current symlink code paths are covered by regression tests before removal.
2. Replace `SYMLINK`-driven plans with compiled file actions.
   verify: plan output lists generated files for skills, agents, rules, and workspace artifacts.
3. Keep optional symlink mode behind an explicit debug flag if still useful.
   verify: default path never emits symlink actions.

### Phase 4: transactional apply and rollback

1. Add failing tests for partial failure rollback.
   verify: a mid-apply failure leaves target files unchanged.
2. Implement staging, revision manifests, atomic swap, and rollback.
   verify: interrupted apply restores the last successful revision.
3. Replace ad hoc backup behavior.
   verify: backups are no longer the primary recovery mechanism.

### Phase 5: documentation and UX

1. Add `code-agnostic validate`.
   verify: validates canonical input without applying.
2. Add `code-agnostic explain-lossiness`.
   verify: shows which fields are ignored or rewritten for each target.
3. Add migration docs and examples.
   verify: a user can convert one sample rule, skill, agent, and MCP config without reading code.

## Test policy for every implementation PR

This project should not accept compiler work without tests first.

Rules:

- write failing tests before implementation
- reuse fixtures and `conftest.py` helpers
- prefer parametrized tests when behavior should stay aligned across apps
- add unit tests for parsing, validation, diagnostics, and emitters
- add planner/executor tests for generated output paths and transactional apply
- add e2e tests for one full sync per app family

Suggested new test modules:

- `tests/compiler/test_bundle_loaders.py`
- `tests/compiler/test_schema_validation.py`
- `tests/compiler/test_capability_matrix.py`
- `tests/compiler/test_diagnostics.py`
- `tests/test_transactional_executor.py`
- `tests/e2e/test_generated_sync_e2e.py`

Run tests with:

```bash
uv run pytest
```

During iteration, run the smallest relevant slice first, then the full suite before merge. Examples:

```bash
uv run pytest tests/compiler/test_schema_validation.py
uv run pytest tests/test_transactional_executor.py
uv run pytest tests/e2e/test_generated_sync_e2e.py
uv run pytest
```

## Success criteria

We are done when all of this is true:

- canonical resources use strict `meta.yaml` + `prompt.md` bundles
- unknown properties fail validation
- generated outputs are the default for every app and workspace flow
- apply is transactional and rollback works
- compiler behavior is documented by capability matrices
- lossiness is explicit and user-visible
- `README.md` matches reality
- tests cover validation, compilation, apply, rollback, and e2e sync

## Non-goals for this roadmap

Do not expand scope with new editor features while this is in flight.

Not part of this effort unless required to finish the compiler migration:

- new app targets
- speculative schema fields
- broad CLI redesign
- refactors unrelated to compiler boundaries
