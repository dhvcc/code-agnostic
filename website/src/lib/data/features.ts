export interface Feature {
	title: string;
	description: string;
	snippet?: string;
}

export const features: Feature[] = [
	{
		title: 'Sync engine',
		description: 'Plan-then-apply workflow. Preview every change before it touches disk.',
		snippet: 'code-agnostic plan\ncode-agnostic apply'
	},
	{
		title: 'MCP management',
		description: 'Add, remove, and list MCP servers without editing JSON by hand.',
		snippet: 'code-agnostic mcp add github \\\n  --command npx \\\n  --env GITHUB_TOKEN'
	},
	{
		title: 'Rules with metadata',
		description: 'YAML frontmatter in markdown. Cross-compiled per editor — .mdc for Cursor, AGENTS.md for OpenCode/Codex.'
	},
	{
		title: 'Skills & agents',
		description: 'Canonical YAML frontmatter format. Each editor gets a compiled version in its native layout.'
	},
	{
		title: 'Workspaces',
		description:
			'Register workspace directories. Repos inside get rules, skills, and agents propagated as symlinks for OpenCode and Codex. Cursor workspace propagation is intentionally disabled to avoid duplicate MCP initialization in multi-root workspaces.',
		snippet: 'code-agnostic workspaces add \\\n  --name myproject \\\n  --path ~/code/myproject'
	},
	{
		title: 'Git exclude',
		description: 'Prevent synced paths from polluting git status. Managed per-workspace with customizable patterns.'
	},
	{
		title: 'Import',
		description: 'Migrate existing config from any supported editor into the hub. Conflict resolution built in.',
		snippet: 'code-agnostic import apply -a codex'
	},
	{
		title: 'Interactive TUI',
		description: 'Textual-based selector for cherry-picking individual items during import.',
		snippet: 'code-agnostic import plan -a codex -i'
	},
	{
		title: 'Docker isolation',
		description: 'Run in a container and only mount the paths you want to expose from your host filesystem.',
		snippet:
			'docker run --rm -it \\\n  -v "$(pwd):/workspace" \\\n  -w /workspace \\\n  ghcr.io/dhvcc/code-agnostic:latest plan'
	}
];
