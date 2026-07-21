export interface RoadmapItem {
	label: string;
	done: boolean;
}

export const roadmap: RoadmapItem[] = [
	{ label: 'Plan/apply/status sync engine', done: true },
	{ label: 'MCP server sync across editors', done: true },
	{ label: 'Skills and agents sync', done: true },
	{ label: 'Workspace propagation into git repos', done: true },
	{ label: 'Import from existing editor configs', done: true },
	{ label: 'Consistent CLI with named flags and aliases', done: true },
	{ label: 'MCP add/remove/list commands', done: true },
	{ label: 'Rules system with YAML frontmatter and per-editor compilation', done: true },
	{ label: 'Cross-compilation for skills and agents', done: true },
	{ label: 'Per-workspace git-exclude customization', done: true },
	{ label: 'Interactive TUI for import selection', done: true },
	{ label: 'Claude Code support', done: true },
	{ label: 'GitHub Copilot support', done: true },
	{ label: 'Planner integration for cross-compiled skills and agents', done: true },
	{ label: 'Ownership-aware cleanup (prune only what we wrote)', done: true },
	{ label: 'rules/skills/agents add commands', done: false },
	{ label: 'Shell auto-complete', done: false },
	{ label: 'Full TUI mode', done: false }
];
