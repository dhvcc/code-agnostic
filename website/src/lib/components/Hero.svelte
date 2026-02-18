<script lang="ts">
	import CodeBlock from './CodeBlock.svelte';
</script>

<section id="hero" class="pt-32 pb-20 md:pt-40 md:pb-28">
	<div class="max-w-3xl mx-auto px-6">
		<div class="inline-flex items-center gap-2 px-3 py-1 rounded-full border border-accent/30 bg-accent-dim/20 mb-6 animate-fade-up">
			<span class="relative flex h-2 w-2">
				<span class="animate-ping absolute inline-flex h-full w-full rounded-full bg-accent/60"></span>
				<span class="relative inline-flex rounded-full h-2 w-2 bg-accent"></span>
			</span>
			<span class="font-mono text-xs text-accent">Beta</span>
			<span class="text-xs text-text-dim">&mdash; work in progress, CLI surface may change</span>
		</div>

		<h1
			class="font-display text-5xl md:text-7xl tracking-wide leading-[1.1] text-text
				animate-fade-up"
		>
			One config,<br />every AI editor.
		</h1>

		<p
			class="mt-6 text-lg md:text-xl text-text-muted leading-relaxed max-w-xl
				animate-fade-up [animation-delay:100ms]"
		>
			Keep MCP servers, rules, skills, and agents in a single
			hub&mdash;sync them into editor-specific layouts.
		</p>

		<div class="mt-10 max-w-md animate-fade-up [animation-delay:200ms]">
			<CodeBlock code="uv tool install code-agnostic" />
		</div>

		<p class="mt-4 text-sm text-text-dim animate-fade-up [animation-delay:300ms]">
			Or run without installing: <code class="font-mono text-text-muted">uvx code-agnostic</code>
		</p>
	</div>
</section>
