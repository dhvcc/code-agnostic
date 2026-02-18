<script lang="ts">
	import FeatureCard from './FeatureCard.svelte';
	import { features } from '$lib/data/features';
</script>

<section id="features" class="py-20 md:py-28">
	<div class="max-w-5xl mx-auto px-6">
		<h2 class="font-display text-3xl md:text-4xl tracking-wide text-text mb-12">
			Features
		</h2>

		<div class="grid md:grid-cols-2 gap-4">
			{#each features as feature}
				<FeatureCard
					title={feature.title}
					description={feature.description}
					snippet={feature.snippet}
				/>
			{/each}
		</div>
	</div>
</section>
