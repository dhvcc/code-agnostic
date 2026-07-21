<script lang="ts">
	import { compatibility, footnote } from '$lib/data/compatibility';

	const editors = [
		{ key: 'opencode', label: 'OpenCode' },
		{ key: 'cursor', label: 'Cursor' },
		{ key: 'codex', label: 'Codex' },
		{ key: 'claude', label: 'Claude Code' },
		{ key: 'copilot', label: 'Copilot' }
	] as const;
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
						{#each editors as editor}
							<th class="text-center py-3 px-4 text-accent font-medium">{editor.label}</th>
						{/each}
					</tr>
				</thead>
				<tbody>
					{#each compatibility as row}
						<tr class="border-b border-border/50">
							<td class="py-3 pr-6 text-text-muted">{row.feature}</td>
							{#each editors as editor}
								<td class="py-3 px-4 text-center">
									{#if row[editor.key]}
										<span class="text-accent">&#x2713;</span>
									{:else}
										<span class="text-text-dim">&mdash;</span>
									{/if}
								</td>
							{/each}
						</tr>
					{/each}
				</tbody>
			</table>
		</div>

		<p class="mt-6 text-xs text-text-dim">{footnote}</p>
	</div>
</section>
