<script lang="ts">
	import { onMount } from 'svelte';
	import { base } from '$app/paths';

	let activeSection = $state('');
	let mobileOpen = $state(false);

	const links = [
		{ href: '#features', label: 'Features' },
		{ href: '#editors', label: 'Editors' },
		{ href: '#quickstart', label: 'Quick Start' },
		{ href: '#roadmap', label: 'Roadmap' }
	];

	onMount(() => {
		const observer = new IntersectionObserver(
			(entries) => {
				for (const entry of entries) {
					if (entry.isIntersecting) {
						activeSection = entry.target.id;
					}
				}
			},
			{ rootMargin: '-40% 0px -60% 0px' }
		);

		document.querySelectorAll('section[id]').forEach((el) => observer.observe(el));
		return () => observer.disconnect();
	});
</script>

<nav
	class="fixed top-0 left-0 right-0 z-50
		bg-bg/80 backdrop-blur-md border-b border-border/50"
>
	<div class="max-w-5xl mx-auto px-6 h-14 flex items-center justify-between">
		<a href="{base}/" class="font-mono text-sm tracking-tight text-text-muted hover:text-text transition-colors">
			<span class="text-accent">&#x276f;</span> code-agnostic
		</a>

		<!-- Desktop links -->
		<div class="hidden md:flex items-center gap-6">
			{#each links as link}
				<a
					href={link.href}
					class="text-sm transition-colors duration-150
						{activeSection === link.href.slice(1) ? 'text-accent' : 'text-text-dim hover:text-text-muted'}"
				>
					{link.label}
				</a>
			{/each}
			<a
				href="https://github.com/dhvcc/code-agnostic"
				target="_blank"
				rel="noopener noreferrer"
				class="text-sm text-text-dim hover:text-text-muted transition-colors"
			>
				GitHub
			</a>
		</div>

		<!-- Mobile hamburger -->
		<button
			class="md:hidden flex flex-col gap-1 p-2 cursor-pointer"
			onclick={() => (mobileOpen = !mobileOpen)}
			aria-label="Toggle menu"
		>
			<span class="block w-4 h-px bg-text-muted transition-transform duration-200
				{mobileOpen ? 'translate-y-[3px] rotate-45' : ''}"></span>
			<span class="block w-4 h-px bg-text-muted transition-opacity duration-200
				{mobileOpen ? 'opacity-0' : ''}"></span>
			<span class="block w-4 h-px bg-text-muted transition-transform duration-200
				{mobileOpen ? '-translate-y-[3px] -rotate-45' : ''}"></span>
		</button>
	</div>

	<!-- Mobile overlay -->
	{#if mobileOpen}
		<div class="md:hidden bg-bg/95 backdrop-blur-md border-b border-border">
			<div class="px-6 py-4 flex flex-col gap-3">
				{#each links as link}
					<a
						href={link.href}
						onclick={() => (mobileOpen = false)}
						class="text-sm text-text-muted hover:text-text transition-colors"
					>
						{link.label}
					</a>
				{/each}
				<a
					href="https://github.com/dhvcc/code-agnostic"
					target="_blank"
					rel="noopener noreferrer"
					class="text-sm text-text-muted hover:text-text transition-colors"
				>
					GitHub
				</a>
			</div>
		</div>
	{/if}
</nav>
