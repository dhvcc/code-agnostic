# Generated artifact ownership

`code-agnostic` compiles a canonical source tree into app-native files. Those
target files are generated artifacts, and ownership must be a compiler policy,
not an app-specific helper choice.

## Problem

Generated files currently get conflict behavior from whichever planning helper a
call site chooses. That allowed two instruction-overlay files to drift:

- Claude `CLAUDE.local.md` uses owned-only behavior.
- Codex `AGENTS.override.md` used normal compiled-text behavior.

Those files represent the same concept: repo-local instruction overlays generated
from workspace rules. They must have the same ownership rules.

The same risk exists for generated skills and agents when target apps use folders
that users also edit directly, such as `.claude`, `.agents`, `.codex`, `.cursor`,
or `.opencode`.

## Ownership model

Every generated output should be represented as a generated artifact before it is
converted into an executor action.

Initial policy values:

- `OWNED_ONLY`: create missing paths, update paths recorded in `.sync-state.json`,
  and conflict on unmanaged files, directories, or symlinks.
- `MANAGED_REPLACE`: legacy managed-output behavior for paths that are already
  known to the sync state or are being migrated from old symlink outputs.
- `MERGE_NATIVE_CONFIG`: native app config files where unmanaged keys are
  intentionally preserved, such as `~/.claude.json` and app MCP config files.

The planner owns this policy. App services should render app-native payloads and
target paths, but should not decide whether an unmanaged target file can be
overwritten.

## Rules

- Generated repo/workspace files are owned-only by default.
- A path is owned only when it is recorded in `.sync-state.json` for the current
  scope, or when it is under a managed legacy ancestor recorded in sync state.
- Existing unmanaged regular files, directories, and symlinks are conflicts.
- Executor write handlers must treat `CONFLICT` as no-op.
- Stale cleanup removes only managed paths from sync state.
- Git exclude entries should be derived from generated artifact declarations when
  possible, so planner behavior and local git hygiene cannot drift.

## Current implementation path

1. Introduce a root generated-artifact primitive and planner.
2. Migrate Codex `AGENTS.override.md` and Claude `CLAUDE.local.md` to the same
   `OWNED_ONLY` instruction-overlay behavior.
3. Route compiled skill/agent planning through the same primitive so Claude does
   not need a private owned-planning loop.
4. Move git-exclude path computation toward generated artifact declarations.
5. Update status to compare expected generated artifacts instead of re-deriving
   app-specific paths independently.

## Compatibility

This intentionally tightens behavior for unmanaged existing generated paths. For
example, an unmanaged `AGENTS.override.md` should become a conflict instead of
being overwritten. Existing files already recorded in `.sync-state.json` continue
to update normally.
