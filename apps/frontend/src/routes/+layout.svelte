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

<!-- Main content -->
{@render children()}
