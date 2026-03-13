export interface CompatibilityRow {
	feature: string;
	opencode: boolean;
	cursor: boolean;
	codex: boolean;
}

export const compatibility: CompatibilityRow[] = [
	{ feature: 'MCP sync', opencode: true, cursor: true, codex: true },
	{ feature: 'Rules sync', opencode: true, cursor: true, codex: true },
	{ feature: 'Skills sync', opencode: true, cursor: true, codex: true },
	{ feature: 'Agents sync', opencode: true, cursor: true, codex: true },
	{ feature: 'Workspace root AGENTS.md link', opencode: true, cursor: true, codex: true },
	{ feature: 'Native repo config include for workspace AGENTS.md', opencode: true, cursor: false, codex: false },
	{ feature: 'Repo/subdir gets shared workspace AGENTS.md today', opencode: true, cursor: false, codex: false },
	{ feature: 'Root-level AGENTS.md discovery only', opencode: false, cursor: true, codex: true },
	{ feature: 'Workspace propagation', opencode: true, cursor: false, codex: true },
	{ feature: 'Import from', opencode: true, cursor: true, codex: true },
	{ feature: 'Interactive TUI', opencode: true, cursor: true, codex: true }
];

export const footnote =
	'OpenCode includes the shared workspace AGENTS.md through instructions. Cursor is documented around root-level AGENTS.md, and Codex documents AGENTS.md discovery without a native extra-file include, so repo/subdir sessions do not reliably inherit the shared workspace file today.';
