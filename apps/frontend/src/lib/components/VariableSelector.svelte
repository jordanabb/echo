<script lang="ts">
	import { onMount } from 'svelte';
	import { indicatorsByTheme, initializeMetadata, type IndicatorMetadata } from '$lib/stores/metadata';
	import { 
		toggleIndicator, 
		clearIndicators, 
		selectedIndicatorCount,
		isIndicatorSelected 
	} from '$lib/stores/analysisFilters';
	import { 
		currentYears,
		toggleYear,
		setYears
	} from '$lib/stores/unifiedFilters';
	import Card from './Card.svelte';
	import Button from './Button.svelte';
	import YearSelector from './YearSelector.svelte';

	// Component props
	export let maxHeight = '400px';
	export let showSelectedCount = true;
	export let allowClearAll = true;

	// Local state
	let searchTerm = '';
	let expandedThemes: Set<string> = new Set();
	let searchInput: HTMLInputElement;

	// Reactive variables
	$: filteredIndicatorsByTheme = filterIndicatorsBySearch($indicatorsByTheme, searchTerm);
	$: hasSearchResults = Object.keys(filteredIndicatorsByTheme).length > 0;

	/**
	 * Filters indicators by search term
	 */
	function filterIndicatorsBySearch(
		indicatorsByTheme: Record<string, IndicatorMetadata[]>, 
		searchTerm: string
	): Record<string, IndicatorMetadata[]> {
		if (!searchTerm.trim()) {
			return indicatorsByTheme;
		}

		const filtered: Record<string, IndicatorMetadata[]> = {};
		const lowerSearchTerm = searchTerm.toLowerCase();

		Object.entries(indicatorsByTheme).forEach(([theme, indicators]) => {
			const matchingIndicators = indicators.filter(indicator =>
				indicator.name.toLowerCase().includes(lowerSearchTerm) ||
				indicator.description.toLowerCase().includes(lowerSearchTerm) ||
				indicator.id.toLowerCase().includes(lowerSearchTerm)
			);

			if (matchingIndicators.length > 0) {
				filtered[theme] = matchingIndicators;
			}
		});

		return filtered;
	}

	/**
	 * Toggles theme expansion
	 */
	function toggleTheme(theme: string): void {
		if (expandedThemes.has(theme)) {
			expandedThemes.delete(theme);
		} else {
			expandedThemes.add(theme);
		}
		expandedThemes = expandedThemes; // Trigger reactivity
	}

	/**
	 * Expands all themes
	 */
	function expandAllThemes(): void {
		expandedThemes = new Set(Object.keys(filteredIndicatorsByTheme));
	}

	/**
	 * Collapses all themes
	 */
	function collapseAllThemes(): void {
		expandedThemes = new Set();
	}

	/**
	 * Handles indicator selection
	 */
	function handleIndicatorToggle(indicatorId: string): void {
		toggleIndicator(indicatorId);
	}

	/**
	 * Handles clear all selection
	 */
	function handleClearAll(): void {
		clearIndicators();
	}

	/**
	 * Focuses search input
	 */
	function focusSearch(): void {
		if (searchInput) {
			searchInput.focus();
		}
	}

	/**
	 * Handles keyboard shortcuts
	 */
	function handleKeydown(event: KeyboardEvent): void {
		// Ctrl/Cmd + F to focus search
		if ((event.ctrlKey || event.metaKey) && event.key === 'f') {
			event.preventDefault();
			focusSearch();
		}
		// Escape to clear search
		if (event.key === 'Escape' && searchTerm) {
			searchTerm = '';
		}
	}

	/**
	 * Auto-expand themes when searching
	 */
	$: if (searchTerm.trim()) {
		expandAllThemes();
	}

	// Initialize metadata on mount
	onMount(() => {
		initializeMetadata();
	});
</script>

<svelte:window on:keydown={handleKeydown} />

<Card variant="default" padding="none">
	<div class="flex flex-col h-full">
		<!-- Header -->
		<div class="p-4 border-b border-neutral-200 bg-neutral-50 rounded-t-xl">
			<div class="flex items-center justify-between mb-3">
				<h3 class="text-lg font-semibold text-neutral-900">Select Variables</h3>
				{#if showSelectedCount}
					<div class="flex items-center gap-2">
						<span class="text-sm text-neutral-600">
							{$selectedIndicatorCount} selected
						</span>
						{#if allowClearAll && $selectedIndicatorCount > 0}
							<Button 
								variant="ghost" 
								size="sm" 
								on:click={handleClearAll}
								title="Clear all selections"
							>
								Clear All
							</Button>
						{/if}
					</div>
				{/if}
			</div>

			<!-- Search Bar -->
			<div class="relative">
				<div class="absolute inset-y-0 left-0 pl-3 flex items-center pointer-events-none">
					<svg class="h-4 w-4 text-neutral-400" fill="none" viewBox="0 0 24 24" stroke="currentColor">
						<path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M21 21l-6-6m2-5a7 7 0 11-14 0 7 7 0 0114 0z" />
					</svg>
				</div>
				<input
					bind:this={searchInput}
					bind:value={searchTerm}
					type="text"
					placeholder="Search variables... (Ctrl+F)"
					class="block w-full pl-10 pr-10 py-2 border border-neutral-300 rounded-lg text-sm placeholder-neutral-500 focus:outline-none focus:ring-2 focus:ring-primary-500 focus:border-primary-500 transition-colors"
				/>
				{#if searchTerm}
					<button
						on:click={() => searchTerm = ''}
						class="absolute inset-y-0 right-0 pr-3 flex items-center text-neutral-400 hover:text-neutral-600 transition-colors"
						title="Clear search"
					>
						<svg class="h-4 w-4" fill="none" viewBox="0 0 24 24" stroke="currentColor">
							<path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M6 18L18 6M6 6l12 12" />
						</svg>
					</button>
				{/if}
			</div>

			<!-- Year Selection -->
			<div class="mt-3">
				<YearSelector
					selectedYears={$currentYears}
					mode="inline"
					on:change={(event) => setYears(event.detail.selectedYears)}
				/>
			</div>

			<!-- Theme Controls -->
			{#if !searchTerm && Object.keys($indicatorsByTheme).length > 1}
				<div class="flex gap-2 mt-3">
					<Button variant="ghost" size="sm" on:click={expandAllThemes}>
						Expand All
					</Button>
					<Button variant="ghost" size="sm" on:click={collapseAllThemes}>
						Collapse All
					</Button>
				</div>
			{/if}
		</div>

		<!-- Content -->
		<div class="flex-1 overflow-y-auto" style="max-height: {maxHeight};">
			{#if hasSearchResults}
				<div class="p-4 space-y-4">
					{#each Object.entries(filteredIndicatorsByTheme) as [theme, indicators]}
						<div class="border border-neutral-200 rounded-lg overflow-hidden">
							<!-- Theme Header -->
							<button
								on:click={() => toggleTheme(theme)}
								class="w-full px-4 py-3 bg-neutral-50 hover:bg-neutral-100 border-b border-neutral-200 flex items-center justify-between text-left transition-colors"
							>
								<div class="flex items-center gap-2">
									<span class="font-medium text-neutral-900 capitalize">{theme}</span>
									<span class="text-xs text-neutral-500 bg-neutral-200 px-2 py-1 rounded-full">
										{indicators.length}
									</span>
								</div>
								<svg 
									class="h-4 w-4 text-neutral-600 transition-transform duration-200 {expandedThemes.has(theme) ? 'rotate-180' : ''}"
									fill="none" 
									viewBox="0 0 24 24" 
									stroke="currentColor"
								>
									<path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M19 9l-7 7-7-7" />
								</svg>
							</button>

							<!-- Theme Content -->
							{#if expandedThemes.has(theme)}
								<div class="divide-y divide-neutral-100">
									{#each indicators as indicator}
										{@const isSelected = $isIndicatorSelected(indicator.id)}
										<label class="flex items-start gap-3 p-4 hover:bg-neutral-50 cursor-pointer transition-colors">
											<input
												type="checkbox"
												checked={isSelected}
												on:change={() => handleIndicatorToggle(indicator.id)}
												class="mt-1 h-4 w-4 text-primary-600 border-neutral-300 rounded focus:ring-primary-500 focus:ring-2 transition-colors"
											/>
											<div class="flex-1 min-w-0">
												<div class="flex items-center gap-2 mb-1">
													<span class="font-medium text-neutral-900 text-sm">
														{indicator.name}
													</span>
													{#if isSelected}
														<svg class="h-4 w-4 text-primary-600" fill="currentColor" viewBox="0 0 20 20">
															<path fill-rule="evenodd" d="M16.707 5.293a1 1 0 010 1.414l-8 8a1 1 0 01-1.414 0l-4-4a1 1 0 011.414-1.414L8 12.586l7.293-7.293a1 1 0 011.414 0z" clip-rule="evenodd" />
														</svg>
													{/if}
												</div>
												<p class="text-xs text-neutral-600 mb-2">
													{indicator.description}
												</p>
												<div class="flex items-center gap-2 text-xs text-neutral-500">
													<span>ID: {indicator.id}</span>
													<span>•</span>
													<span>Years: {indicator.available_years.length}</span>
													<span>•</span>
													<span>{indicator.available_years[0]}-{indicator.available_years[indicator.available_years.length - 1]}</span>
												</div>
											</div>
										</label>
									{/each}
								</div>
							{/if}
						</div>
					{/each}
				</div>
			{:else if searchTerm}
				<!-- No Search Results -->
				<div class="p-8 text-center">
					<svg class="mx-auto h-12 w-12 text-neutral-400 mb-4" fill="none" viewBox="0 0 24 24" stroke="currentColor">
						<path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M21 21l-6-6m2-5a7 7 0 11-14 0 7 7 0 0114 0z" />
					</svg>
					<h3 class="text-sm font-medium text-neutral-900 mb-1">No variables found</h3>
					<p class="text-sm text-neutral-500">
						Try adjusting your search terms or browse by category.
					</p>
				</div>
			{:else}
				<!-- Loading State -->
				<div class="p-8 text-center">
					<div class="animate-spin rounded-full h-8 w-8 border-b-2 border-primary-600 mx-auto mb-4"></div>
					<p class="text-sm text-neutral-500">Loading variables...</p>
				</div>
			{/if}
		</div>

		<!-- Footer -->
		{#if $selectedIndicatorCount > 0 || $currentYears.length > 0}
			<div class="p-4 border-t border-neutral-200 bg-neutral-50 rounded-b-xl">
				<div class="text-sm text-neutral-600 space-y-1">
					{#if $selectedIndicatorCount > 0}
						<div>
							<strong>{$selectedIndicatorCount}</strong> variable{$selectedIndicatorCount === 1 ? '' : 's'} selected for analysis
						</div>
					{/if}
					{#if $currentYears.length > 0}
						<div>
							<strong>{$currentYears.length}</strong> year{$currentYears.length === 1 ? '' : 's'} selected: {$currentYears.sort((a, b) => a - b).join(', ')}
						</div>
					{/if}
				</div>
			</div>
		{/if}
	</div>
</Card>
