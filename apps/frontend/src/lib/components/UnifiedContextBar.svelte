<script lang="ts">
	import { onMount } from 'svelte';
	import { slide } from 'svelte/transition';
	import { quintOut } from 'svelte/easing';
	import Button from './Button.svelte';
	import YearSelector from './YearSelector.svelte';
	import { 
		unifiedFilters,
		currentGeoLevel,
		currentGeoFilter,
		currentPrimaryYear,
		currentYears,
		currentPrimaryIndicator,
		currentSelectedIndicators,
		selectedIndicatorCount,
		selectedIndicatorsWithMetadata,
		updateFilter,
		updateFilters,
		resetFilters,
		toggleIndicator,
		clearIndicators,
		setYears,
		initializeUnifiedFilters
	} from '../stores/unifiedFilters';
	import { 
		indicators, 
		geographies, 
		indicatorsByTheme,
		allAvailableYears,
		getAvailableYearsForIndicator,
		initializeMetadata
	} from '../stores/metadata';
	import { showVariableSelector } from '../stores/interactiveSteps';
	import { US_STATES, getStateNameByCode } from '../constants/states';

	// Component state
	let showAdvanced = false;
	let searchTerm = '';
	let expandedThemes: Set<string> = new Set();

	// Initialize stores on mount
	onMount(() => {
		initializeMetadata();
		initializeUnifiedFilters();
	});

	// Reactive computations
	$: availableYears = $currentPrimaryIndicator 
		? getAvailableYearsForIndicator($currentPrimaryIndicator) 
		: $allAvailableYears;

	$: geographyLevels = Object.keys($geographies);

	$: filteredIndicatorsByTheme = filterIndicatorsBySearch($indicatorsByTheme, searchTerm);

	/**
	 * Filters indicators by search term
	 */
	function filterIndicatorsBySearch(
		indicatorsByTheme: Record<string, any[]>, 
		searchTerm: string
	): Record<string, any[]> {
		if (!searchTerm.trim()) {
			return indicatorsByTheme;
		}

		const filtered: Record<string, any[]> = {};
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
	 * Handles geography level change
	 */
	function handleGeoLevelChange(event: Event) {
		const target = event.target as HTMLSelectElement;
		const geoLevel = target.value || null;
		// Clear state filter when geography level changes
		updateFilters({
			geoLevel: geoLevel,
			geoFilter: null
		});
	}

	/**
	 * Handles state filter change
	 */
	function handleStateFilterChange(event: Event) {
		const target = event.target as HTMLSelectElement;
		const stateCode = target.value || null;
		updateFilter('geoFilter', stateCode);
	}

	/**
	 * Handles primary year change
	 */
	function handleYearChange(event: Event) {
		const target = event.target as HTMLSelectElement;
		const year = target.value ? parseInt(target.value) : null;
		updateFilter('primaryYear', year);
	}

	/**
	 * Handles primary indicator change
	 */
	function handlePrimaryIndicatorChange(event: Event) {
		const target = event.target as HTMLSelectElement;
		const indicatorId = target.value || null;
		
		if (indicatorId) {
			const availableYearsForIndicator = getAvailableYearsForIndicator(indicatorId);
			const newYear = availableYearsForIndicator.includes($currentPrimaryYear || 0) 
				? $currentPrimaryYear 
				: availableYearsForIndicator[0] || null;
			
			updateFilters({
				primaryIndicator: indicatorId,
				primaryYear: newYear
			});
		} else {
			updateFilter('primaryIndicator', null);
		}
	}

	/**
	 * Toggles theme expansion in variable selector
	 */
	function toggleTheme(theme: string): void {
		if (expandedThemes.has(theme)) {
			expandedThemes.delete(theme);
		} else {
			expandedThemes.add(theme);
		}
		expandedThemes = expandedThemes;
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
	 * Auto-expand themes when searching
	 */
	$: if (searchTerm.trim()) {
		expandAllThemes();
	}

	/**
	 * Get display text for selected variables
	 */
	function getVariableDisplayText(): string {
		if ($selectedIndicatorCount === 0) {
			return $currentPrimaryIndicator 
				? $indicators.find(ind => ind.id === $currentPrimaryIndicator)?.name || 'Unknown'
				: 'Select variables';
		}
		
		if ($selectedIndicatorCount === 1) {
			return $selectedIndicatorsWithMetadata[0]?.name || 'Unknown';
		}
		
		const firstName = $selectedIndicatorsWithMetadata[0]?.name || 'Unknown';
		return `${firstName} (+${$selectedIndicatorCount - 1} more)`;
	}

	/**
	 * Get geography display name
	 */
	function getGeoDisplayName(geoLevel: string | null): string {
		if (!geoLevel) return 'Select geography';
		return $geographies[geoLevel]?.name || geoLevel;
	}
</script>

<!-- Unified Context Bar -->
<div class="bg-white border-b border-neutral-200 shadow-sm sticky top-0 z-40">
	<div class="max-w-7xl mx-auto px-4 sm:px-6 lg:px-8">
		<!-- Main Context Bar -->
		<div class="flex items-center justify-between py-3">
			<!-- Left: Core Selections -->
			<div class="flex items-center space-x-4">
				<!-- Geography Level -->
				<div class="flex items-center space-x-2">
					<span class="text-2xl">📍</span>
					<select
						class="text-sm font-medium bg-transparent border-none focus:ring-2 focus:ring-primary-500 rounded px-2 py-1 cursor-pointer hover:bg-neutral-50 transition-colors"
						value={$currentGeoLevel || ''}
						on:change={handleGeoLevelChange}
					>
						<option value="">Select geography...</option>
						{#each geographyLevels as level}
							<option value={level}>{$geographies[level]?.name || level}</option>
						{/each}
					</select>
				</div>

				<!-- State Filter (Optional) -->
				{#if $currentGeoLevel}
					<div class="flex items-center space-x-2">
						<span class="text-2xl">🗺️</span>
						<select
							class="text-sm font-medium bg-transparent border-none focus:ring-2 focus:ring-primary-500 rounded px-2 py-1 cursor-pointer hover:bg-neutral-50 transition-colors"
							value={$currentGeoFilter || ''}
							on:change={handleStateFilterChange}
						>
							<option value="">All States</option>
							{#each US_STATES as state}
								<option value={state.code}>{state.name}</option>
							{/each}
						</select>
					</div>
				{/if}

				<!-- Year -->
				<div class="flex items-center space-x-2">
					<span class="text-2xl">📅</span>
					<YearSelector
						selectedYears={$currentYears}
						mode="dropdown"
						placeholder="Select years..."
						on:change={(event) => setYears(event.detail.selectedYears)}
					/>
				</div>

				<!-- Variables -->
				<div class="flex items-center space-x-2">
					<span class="text-2xl">📊</span>
					<button
						class="text-sm font-medium bg-transparent border-none focus:ring-2 focus:ring-primary-500 rounded px-2 py-1 cursor-pointer hover:bg-neutral-50 transition-colors text-left"
						on:click={() => $showVariableSelector = !$showVariableSelector}
					>
						{getVariableDisplayText()}
						<svg class="inline-block w-4 h-4 ml-1 transition-transform {$showVariableSelector ? 'rotate-180' : ''}" fill="none" stroke="currentColor" viewBox="0 0 24 24">
							<path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M19 9l-7 7-7-7" />
						</svg>
					</button>
				</div>
			</div>

			<!-- Right: Actions -->
			<div class="flex items-center space-x-2">
				{#if $selectedIndicatorCount > 0}
					<span class="text-xs text-neutral-600 bg-primary-100 px-2 py-1 rounded-full">
						{$selectedIndicatorCount} selected
					</span>
				{/if}
				
				<Button variant="ghost" size="sm" on:click={() => showAdvanced = !showAdvanced}>
					{showAdvanced ? 'Hide' : 'Show'} Advanced
				</Button>
				
				<Button variant="ghost" size="sm" on:click={resetFilters}>
					Reset
				</Button>
			</div>
		</div>

		<!-- Advanced Options -->
		{#if showAdvanced}
			<div class="border-t border-neutral-200 py-3" transition:slide={{ duration: 200, easing: quintOut }}>
				<div class="grid grid-cols-1 md:grid-cols-3 gap-4">
					<!-- Primary Indicator (for single-variable views) -->
					<div>
						<label class="block text-xs font-medium text-neutral-700 mb-1">
							Primary Indicator (Maps)
						</label>
						<select
							class="w-full text-sm border border-neutral-300 rounded px-2 py-1 focus:ring-2 focus:ring-primary-500 focus:border-primary-500"
							value={$currentPrimaryIndicator || ''}
							on:change={handlePrimaryIndicatorChange}
						>
							<option value="">Select primary indicator...</option>
							{#each Object.entries($indicatorsByTheme) as [theme, themeIndicators]}
								<optgroup label={theme}>
									{#each themeIndicators as indicator}
										<option value={indicator.id}>{indicator.name}</option>
									{/each}
								</optgroup>
							{/each}
						</select>
					</div>

					<!-- Current State Summary -->
					<div>
						<label class="block text-xs font-medium text-neutral-700 mb-1">
							Current Context
						</label>
						<div class="text-xs text-neutral-600 space-y-1">
							<div><strong>Geography:</strong> {getGeoDisplayName($currentGeoLevel)}</div>
							{#if $currentGeoFilter}
								<div><strong>State:</strong> {getStateNameByCode($currentGeoFilter) || $currentGeoFilter}</div>
							{/if}
							<div><strong>Year:</strong> {$currentPrimaryYear || 'Not selected'}</div>
							<div><strong>Variables:</strong> {$selectedIndicatorCount} selected</div>
						</div>
					</div>

					<!-- Quick Actions -->
					<div>
						<label class="block text-xs font-medium text-neutral-700 mb-1">
							Quick Actions
						</label>
						<div class="flex space-x-2">
							{#if $selectedIndicatorCount > 0}
								<Button variant="ghost" size="sm" on:click={clearIndicators}>
									Clear Variables
								</Button>
							{/if}
							<Button variant="ghost" size="sm" on:click={() => $showVariableSelector = true}>
								Select Variables
							</Button>
						</div>
					</div>
				</div>
			</div>
		{/if}
	</div>
</div>

<!-- Variable Selector Modal -->
{#if $showVariableSelector}
	<div class="fixed inset-0 bg-black bg-opacity-50 z-50 flex items-center justify-center p-4" transition:slide={{ duration: 200 }}>
		<div class="bg-white rounded-xl shadow-2xl max-w-4xl w-full max-h-[80vh] flex flex-col">
			<!-- Modal Header -->
			<div class="p-6 border-b border-neutral-200">
				<div class="flex items-center justify-between">
					<div>
						<h2 class="text-xl font-semibold text-neutral-900">Select Variables</h2>
						<p class="text-sm text-neutral-600 mt-1">Choose variables for analysis and visualization</p>
					</div>
					<div class="flex items-center space-x-2">
						{#if $selectedIndicatorCount > 0}
							<span class="text-sm text-neutral-600 bg-primary-100 px-3 py-1 rounded-full">
								{$selectedIndicatorCount} selected
							</span>
							<Button variant="ghost" size="sm" on:click={clearIndicators}>
								Clear All
							</Button>
						{/if}
						<button
							class="text-neutral-400 hover:text-neutral-600 transition-colors"
							on:click={() => $showVariableSelector = false}
						>
							<svg class="w-6 h-6" fill="none" stroke="currentColor" viewBox="0 0 24 24">
								<path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M6 18L18 6M6 6l12 12" />
							</svg>
						</button>
					</div>
				</div>

				<!-- Search Bar -->
				<div class="mt-4 relative">
					<div class="absolute inset-y-0 left-0 pl-3 flex items-center pointer-events-none">
						<svg class="h-4 w-4 text-neutral-400" fill="none" viewBox="0 0 24 24" stroke="currentColor">
							<path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M21 21l-6-6m2-5a7 7 0 11-14 0 7 7 0 0114 0z" />
						</svg>
					</div>
					<input
						bind:value={searchTerm}
						type="text"
						placeholder="Search variables..."
						class="block w-full pl-10 pr-10 py-2 border border-neutral-300 rounded-lg text-sm placeholder-neutral-500 focus:outline-none focus:ring-2 focus:ring-primary-500 focus:border-primary-500"
					/>
					{#if searchTerm}
						<button
							on:click={() => searchTerm = ''}
							class="absolute inset-y-0 right-0 pr-3 flex items-center text-neutral-400 hover:text-neutral-600"
						>
							<svg class="h-4 w-4" fill="none" viewBox="0 0 24 24" stroke="currentColor">
								<path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M6 18L18 6M6 6l12 12" />
							</svg>
						</button>
					{/if}
				</div>

				<!-- Year Selection -->
				<div class="mt-4">
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

			<!-- Modal Content -->
			<div class="flex-1 overflow-y-auto p-6">
				{#if Object.keys(filteredIndicatorsByTheme).length > 0}
					<div class="space-y-4">
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
											{@const isSelected = $currentSelectedIndicators.includes(indicator.id)}
											<label class="flex items-start gap-3 p-4 hover:bg-neutral-50 cursor-pointer transition-colors">
												<input
													type="checkbox"
													checked={isSelected}
													on:change={() => toggleIndicator(indicator.id)}
													class="mt-1 h-4 w-4 text-primary-600 border-neutral-300 rounded focus:ring-primary-500 focus:ring-2"
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
					<div class="text-center py-12">
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
					<div class="text-center py-12">
						<div class="animate-spin rounded-full h-8 w-8 border-b-2 border-primary-600 mx-auto mb-4"></div>
						<p class="text-sm text-neutral-500">Loading variables...</p>
					</div>
				{/if}
			</div>

			<!-- Modal Footer -->
			<div class="p-6 border-t border-neutral-200 bg-neutral-50">
				<div class="flex items-center justify-between">
					<div class="text-sm text-neutral-600 space-y-1">
						{#if $selectedIndicatorCount > 0}
							<div>
								<strong>{$selectedIndicatorCount}</strong> variable{$selectedIndicatorCount === 1 ? '' : 's'} selected for analysis
							</div>
						{:else}
							<div>Select variables to enable analysis features</div>
						{/if}
						{#if $currentYears.length > 0}
							<div>
								<strong>{$currentYears.length}</strong> year{$currentYears.length === 1 ? '' : 's'} selected: {$currentYears.sort((a, b) => a - b).join(', ')}
							</div>
						{/if}
					</div>
					<Button variant="primary" on:click={() => showVariableSelector.set(false)}>
						Done
					</Button>
				</div>
			</div>
		</div>
	</div>
{/if}
