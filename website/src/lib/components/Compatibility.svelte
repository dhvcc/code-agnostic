<script lang="ts">
	import { compatibility, footnote } from '$lib/data/compatibility';
</script>

<section id="editors" class="py-20 md:py-28 bg-surface">
	<div class="max-w-4xl mx-auto px-6">
		<h2 class="font-display text-3xl md:text-4xl tracking-wide text-text mb-12">
			Editor support
		</h2>

		<div class="overflow-x-auto">
			<table class="w-full font-mono text-sm">
				<thead>
					<tr class="border-b border-accent/30">
						<th class="text-left py-3 pr-6 text-text-muted font-medium">Feature</th>
						<th class="text-center py-3 px-4 text-accent font-medium">OpenCode</th>
						<th class="text-center py-3 px-4 text-accent font-medium">Cursor</th>
						<th class="text-center py-3 px-4 text-accent font-medium">Codex</th>
					</tr>
				</thead>
				<tbody>
					{#each compatibility as row}
						<tr class="border-b border-border/50">
							<td class="py-3 pr-6 text-text-muted">{row.feature}</td>
							<td class="py-3 px-4 text-center">
								{#if row.opencode}
									<span class="text-accent">&#x2713;</span>
								{:else}
									<span class="text-text-dim">&mdash;</span>
								{/if}
							</td>
							<td class="py-3 px-4 text-center">
								{#if row.cursor}
									<span class="text-accent">&#x2713;</span>
								{:else}
									<span class="text-text-dim">&mdash;</span>
								{/if}
							</td>
							<td class="py-3 px-4 text-center">
								{#if row.codex}
									<span class="text-accent">&#x2713;</span>
								{:else}
									<span class="text-text-dim">&mdash;</span>
								{/if}
							</td>
						</tr>
					{/each}
				</tbody>
			</table>
		</div>

		<p class="mt-6 text-xs text-text-dim">{footnote}</p>
	</div>
</section>
