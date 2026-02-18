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
	{ feature: 'Agents sync', opencode: true, cursor: true, codex: false },
	{ feature: 'Workspace propagation', opencode: true, cursor: true, codex: true },
	{ feature: 'Import from', opencode: true, cursor: true, codex: true },
	{ feature: 'Interactive TUI', opencode: true, cursor: true, codex: true }
];

export const footnote = 'Codex does not support agents natively.';
