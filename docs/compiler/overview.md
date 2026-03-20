# Compiler overview

`code-agnostic` is moving from a mixed symlink/compiler sync model to a strict compiler with generated outputs.

## Goals

- one canonical source format
- strict validation with no silent field dropping
- deterministic per-app outputs
- explicit lossiness diagnostics
- transactional apply and rollback

## Canonical source format

Canonical resources should be bundle directories:

```text
rules/python-style/
  meta.yaml
  prompt.md

skills/code-reviewer/
  meta.yaml
  prompt.md

agents/architect/
  meta.yaml
  prompt.md
```

Rules:

- `meta.yaml` is schema-validated
- `prompt.md` contains instruction text only
- canonical bundle files can declare `$schema` to get editor validation from published schema URLs
- app-specific data is allowed only inside `x-cursor`, `x-codex`, or `x-opencode`
- matching `x-*` blocks can override shared fields for that app and can carry app-native passthrough keys
- unknown top-level keys fail validation

## Schema URLs

Compiler-owned source syntax is backed by publishable JSON Schemas in `code_agnostic/spec/schemas/`.

- canonical rule bundle meta: `https://raw.githubusercontent.com/dhvcc/code-agnostic/main/code_agnostic/spec/schemas/rule.v1.schema.json`
- canonical skill bundle meta: `https://raw.githubusercontent.com/dhvcc/code-agnostic/main/code_agnostic/spec/schemas/skill.v1.schema.json`
- canonical agent bundle meta: `https://raw.githubusercontent.com/dhvcc/code-agnostic/main/code_agnostic/spec/schemas/agent.v1.schema.json`
- canonical MCP bundle: `https://raw.githubusercontent.com/dhvcc/code-agnostic/main/code_agnostic/spec/schemas/mcp.v1.schema.json`
- legacy/common `config/mcp.base.json`: `https://raw.githubusercontent.com/dhvcc/code-agnostic/main/code_agnostic/spec/schemas/mcp.base.schema.json`

Example:

```yaml
$schema: https://raw.githubusercontent.com/dhvcc/code-agnostic/main/code_agnostic/spec/schemas/agent.v1.schema.json
spec_version: v1
kind: agent
name: reviewer
```

## Target outputs

- Cursor: generated rules, agents, skills, and MCP config
- Codex: generated `AGENTS.md`, subagents, skills, and MCP config
- OpenCode: generated `AGENTS.md`, agents, skills, and MCP config

Generated artifacts are the default target. Symlink mode is debug-only if retained at all.

## Status vocabulary

Every property in the capability docs uses one of these states:

- `native`: target supports the property directly
- `compiled`: compiler rewrites it into a target-specific representation
- `ignored`: compiler accepts it but omits it for that target
- `rejected`: compiler refuses the resource for that target

## Required docs

- [skills.md](/Users/alexeyartishevsky/PycharmProjects/llm-sync/docs/compiler/skills.md)
- [agents.md](/Users/alexeyartishevsky/PycharmProjects/llm-sync/docs/compiler/agents.md)
- [rules.md](/Users/alexeyartishevsky/PycharmProjects/llm-sync/docs/compiler/rules.md)
- [mcp.md](/Users/alexeyartishevsky/PycharmProjects/llm-sync/docs/compiler/mcp.md)
- [lossiness.md](/Users/alexeyartishevsky/PycharmProjects/llm-sync/docs/compiler/lossiness.md)
