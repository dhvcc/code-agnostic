export interface CompatibilityRow {
	feature: string;
	opencode: boolean;
	cursor: boolean;
	codex: boolean;
	claude: boolean;
	copilot: boolean;
}

export const compatibility: CompatibilityRow[] = [
	{ feature: 'MCP sync', opencode: true, cursor: true, codex: true, claude: true, copilot: true },
	{ feature: 'Rules sync', opencode: true, cursor: true, codex: true, claude: true, copilot: true },
	{ feature: 'Skills sync', opencode: true, cursor: true, codex: true, claude: true, copilot: true },
	{ feature: 'Agents sync', opencode: true, cursor: true, codex: true, claude: true, copilot: true },
	{ feature: 'Import existing config', opencode: true, cursor: true, codex: true, claude: true, copilot: true },
	{ feature: 'Interactive TUI import', opencode: true, cursor: true, codex: true, claude: true, copilot: true },
	{ feature: 'Workspace repo propagation', opencode: true, cursor: true, codex: true, claude: true, copilot: true },
	{
		feature: 'Shared workspace AGENTS.md into child repos',
		opencode: true,
		cursor: false,
		codex: true,
		claude: true,
		copilot: true
	}
];

export const footnote =
	'All five editors sync MCP, rules, skills, and agents, and receive repo-local workspace propagation. Rules compile to AGENTS.md (mirrored to CLAUDE.local.md for Claude Code). OpenCode includes the shared workspace AGENTS.md via instructions, Codex via a generated AGENTS.override.md, Claude via CLAUDE.local.md, and Copilot under .github/. Cursor loads AGENTS.md already present in the opened project, so code-agnostic does not copy the shared workspace file into child repos.';
