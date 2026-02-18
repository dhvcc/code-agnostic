<script lang="ts">
	import { roadmap } from '$lib/data/roadmap';
</script>

<section id="roadmap" class="py-20 md:py-28 bg-surface">
	<div class="max-w-3xl mx-auto px-6">
		<h2 class="font-display text-3xl md:text-4xl tracking-wide text-text mb-12">
			Roadmap
		</h2>

		<ul class="space-y-3">
			{#each roadmap as item}
				<li class="flex items-start gap-3">
					{#if item.done}
						<span
							class="mt-0.5 flex-shrink-0 w-5 h-5 rounded-full bg-accent/15
								flex items-center justify-center"
						>
							<svg class="w-3 h-3 text-accent" fill="none" viewBox="0 0 24 24" stroke="currentColor" stroke-width="3">
								<path stroke-linecap="round" stroke-linejoin="round" d="M5 13l4 4L19 7" />
							</svg>
						</span>
						<span class="text-sm text-text-muted">{item.label}</span>
					{:else}
						<span
							class="mt-0.5 flex-shrink-0 w-5 h-5 rounded-full border border-border"
						></span>
						<span class="text-sm text-text-dim">{item.label}</span>
					{/if}
				</li>
			{/each}
		</ul>
	</div>
</section>
