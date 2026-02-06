<script lang="ts">
	import '../app.css';
	import { onMount } from 'svelte';
	import { initializeMetadata } from '$lib/stores/metadata';
	import { initializeUnifiedFilters } from '$lib/stores/unifiedFilters';

	let { children } = $props();

	onMount(() => {
		// Initialize metadata first, then unified filters
		initializeMetadata();
		
		// Small delay to ensure metadata is loaded before initializing filters
		setTimeout(() => {
			initializeUnifiedFilters();
		}, 100);
	});
</script>

<!-- Mobile redirect message -->
<div class="fixed inset-0 z-[9999] bg-gradient-to-br from-teal-900 via-teal-800 to-teal-900 flex items-center justify-center p-8 lg:hidden">
	<div class="text-center max-w-md">
		<div class="w-20 h-20 bg-teal-700/50 rounded-2xl flex items-center justify-center mx-auto mb-8">
			<svg class="w-10 h-10 text-teal-200" fill="none" stroke="currentColor" viewBox="0 0 24 24">
				<path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M9.75 17L9 20l-1 1h8l-1-1-.75-3M3 13h18M5 17h14a2 2 0 002-2V5a2 2 0 00-2-2H5a2 2 0 00-2 2v10a2 2 0 002 2z" />
			</svg>
		</div>
		<h1 class="text-3xl font-bold text-white mb-4">ECHO Dashboard</h1>
		<p class="text-teal-200 text-lg leading-relaxed mb-6">
			The ECHO Dashboard is designed for use on a full-size screen. Please visit this site on a desktop or laptop computer for the best experience.
		</p>
		<div class="bg-teal-700/30 border border-teal-600/50 rounded-xl p-4">
			<p class="text-teal-300 text-sm">
				Visit <strong class="text-white">echo.newamerica.org</strong> on your computer
			</p>
		</div>
	</div>
</div>

<!-- Main content (hidden on mobile via the overlay above) -->
{@render children()}
