<script lang="ts">
	import CopyButton from './CopyButton.svelte';

	let { code, copyable = true }: { code: string; copyable?: boolean } = $props();
</script>

<div class="relative group">
	<pre
		class="bg-code-bg border border-border rounded-lg px-5 py-4 overflow-x-auto
			font-mono text-sm leading-relaxed text-text-muted"
	><code>{code}</code></pre>
	{#if copyable}
		<div class="absolute top-2 right-2 opacity-0 group-hover:opacity-100 transition-opacity duration-150">
			<CopyButton text={code} />
		</div>
	{/if}
</div>
