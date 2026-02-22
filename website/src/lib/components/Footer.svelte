<script lang="ts">
	const links = [
		{ href: 'https://github.com/dhvcc/code-agnostic', label: 'GitHub' },
		{ href: 'https://pypi.org/project/code-agnostic/', label: 'PyPI' },
		{ href: 'https://github.com/dhvcc/code-agnostic/blob/main/LICENSE', label: 'GPLv3' }
	];
</script>

<footer class="py-12 border-t border-border">
	<div class="max-w-5xl mx-auto px-6 text-center">
		<div class="flex items-center justify-center gap-6 mb-4">
			{#each links as link}
				<a
					href={link.href}
					target="_blank"
					rel="noopener noreferrer"
					class="text-sm text-text-dim hover:text-text-muted transition-colors"
				>
					{link.label}
				</a>
			{/each}
		</div>
		<p class="text-xs text-text-dim">
			Built for developers who use more than one AI editor.
		</p>
	</div>
</footer>
