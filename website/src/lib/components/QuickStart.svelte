<script lang="ts">
	import CodeBlock from './CodeBlock.svelte';

	const steps = [
		{
			num: '01',
			title: 'Import existing config',
			description: 'Pull in MCP servers, skills, and agents from an editor you already use.',
			code: 'code-agnostic import plan -a codex\ncode-agnostic import apply -a codex'
		},
		{
			num: '02',
			title: 'Enable target editors',
			description: 'Choose which editors to sync to. Apps start disabled by default.',
			code: 'code-agnostic apps enable -a cursor\ncode-agnostic apps enable -a opencode'
		},
		{
			num: '03',
			title: 'Preview and apply',
			description: 'Dry-run first, then apply. Every change is shown before it touches disk.',
			code: 'code-agnostic plan\ncode-agnostic apply'
		}
	];
</script>

<section id="quickstart" class="py-20 md:py-28">
	<div class="max-w-3xl mx-auto px-6">
		<h2 class="font-display text-3xl md:text-4xl tracking-wide text-text mb-12">
			Get started
		</h2>

		<div class="space-y-10">
			{#each steps as step}
				<div class="border-l-2 border-accent/40 pl-6">
					<div class="flex items-baseline gap-3 mb-2">
						<span class="font-mono text-xs text-accent">{step.num}</span>
						<h3 class="text-base font-medium text-text">{step.title}</h3>
					</div>
					<p class="text-sm text-text-muted mb-4">{step.description}</p>
					<CodeBlock code={step.code} />
				</div>
			{/each}
		</div>
	</div>
</section>
