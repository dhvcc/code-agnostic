<script lang="ts">
	import { copyToClipboard } from '$lib/utils/copy';

	let { text }: { text: string } = $props();
	let copied = $state(false);

	async function handleCopy() {
		const ok = await copyToClipboard(text);
		if (ok) {
			copied = true;
			setTimeout(() => (copied = false), 1500);
		}
	}
</script>

<button
	onclick={handleCopy}
	class="group relative flex items-center justify-center w-8 h-8 rounded-md
		text-text-dim hover:text-text-muted hover:bg-white/5
		transition-colors duration-150 cursor-pointer"
	aria-label="Copy to clipboard"
>
	{#if copied}
		<svg class="w-4 h-4 text-success" fill="none" viewBox="0 0 24 24" stroke="currentColor" stroke-width="2">
			<path stroke-linecap="round" stroke-linejoin="round" d="M5 13l4 4L19 7" />
		</svg>
	{:else}
		<svg class="w-4 h-4" fill="none" viewBox="0 0 24 24" stroke="currentColor" stroke-width="2">
			<rect x="9" y="9" width="13" height="13" rx="2" ry="2" />
			<path d="M5 15H4a2 2 0 01-2-2V4a2 2 0 012-2h9a2 2 0 012 2v1" />
		</svg>
	{/if}
</button>
