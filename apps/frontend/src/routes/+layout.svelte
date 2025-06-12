<script lang="ts">
	import '../app.css';
	import { onMount } from 'svelte';
	import { initializeMetadata } from '$lib/stores/metadata';
	import { initializeFilters } from '$lib/stores/filters';

	let { children } = $props();

	onMount(() => {
		// Initialize metadata first, then filters
		initializeMetadata();
		
		// Small delay to ensure metadata is loaded before initializing filters
		setTimeout(() => {
			initializeFilters();
		}, 100);
	});
</script>

{@render children()}
