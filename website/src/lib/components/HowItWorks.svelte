<section id="how-it-works" class="py-20 md:py-28 bg-surface">
	<div class="max-w-5xl mx-auto px-6">
		<h2 class="font-display text-3xl md:text-4xl tracking-wide text-text mb-12">
			How it works
		</h2>

		<div class="grid md:grid-cols-2 gap-8 md:gap-12 items-start">
			<!-- Hub: source of truth -->
			<div>
				<p class="text-xs font-mono text-accent uppercase tracking-widest mb-4">
					Source of truth
				</p>
				<pre
					class="bg-code-bg border border-border rounded-xl px-5 py-5
						font-mono text-sm leading-relaxed text-text-muted overflow-x-auto"
><code><span class="text-accent">~/.config/code-agnostic/</span>
├── config/
│   └── mcp.base.json
├── rules/
│   └── python-style.md
├── skills/
│   └── code-reviewer/SKILL.md
└── agents/
    └── architect.md</code></pre>
			</div>

			<!-- Targets -->
			<div>
				<p class="text-xs font-mono text-text-dim uppercase tracking-widest mb-4">
					Compiled & synced
				</p>
				<div class="space-y-3">
					{#each [
						{ name: 'OpenCode', path: '~/.config/opencode/', detail: 'opencode.json + skills/ + agents/' },
						{ name: 'Cursor', path: '~/.cursor/', detail: '.mdc rules + skills/ + agents/' },
						{ name: 'Codex', path: '~/.codex/', detail: 'config.toml + skills/' }
					] as target}
						<div class="border border-border rounded-lg px-4 py-3 bg-bg/50">
							<div class="font-mono text-sm text-text">{target.name}</div>
							<div class="font-mono text-xs text-text-dim mt-0.5">{target.path}</div>
							<div class="text-xs text-text-dim mt-1">{target.detail}</div>
						</div>
					{/each}
				</div>

				<div class="mt-6 flex items-center gap-2 text-text-dim">
					<span class="font-mono text-xs">Each resource is cross-compiled to the target editor's native format.</span>
				</div>
			</div>
		</div>
	</div>
</section>
