<script lang="ts">
	let { title, description, snippet }:
		{ title: string; description: string; snippet?: string } = $props();
</script>

<div
	class="rounded-xl border border-border bg-surface p-6
		hover:border-border-hover transition-colors duration-200"
>
	<h3 class="font-sans text-base font-medium text-text mb-2">{title}</h3>
	<p class="text-sm text-text-muted leading-relaxed">{description}</p>
	{#if snippet}
		<pre
			class="mt-4 bg-code-bg border border-border rounded-lg px-4 py-3 overflow-x-auto
				font-mono text-xs leading-relaxed text-text-dim"
		><code>{snippet}</code></pre>
	{/if}
</div>
