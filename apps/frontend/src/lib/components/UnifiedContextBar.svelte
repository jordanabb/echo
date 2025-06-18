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
		initializeMetadata,
		type IndicatorMetadata
	} from '../stores/metadata';
	import { showVariableSelector } from '../stores/interactiveSteps';
	import { US_STATES, getStateNameByCode } from '../constants/states';

	// Component state
	let showAdvanced = false;
	let searchTerm = '';
	let expandedThemes: Set<string> = new Set();
	let modalElement: HTMLDivElement;
	let isVariableAreaHovered = false;
	let hasHoveredYearSelector = false;

	// Initialize stores on mount
	onMount(() => {
		initializeMetadata();
		initializeUnifiedFilters();
	});

	/**
	 * Handles ESC key press to close modal
	 */
	function handleKeydown(event: KeyboardEvent): void {
		if (event.key === 'Escape' && $showVariableSelector) {
			showVariableSelector.set(false);
		}
	}

	/**
	 * Handles clicking outside the modal to close it
	 */
	function handleModalClick(event: MouseEvent): void {
		if (event.target === modalElement) {
			showVariableSelector.set(false);
		}
	}

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
	 * Reset interaction tracking when modal opens/closes
	 */
	$: if ($showVariableSelector) {
		// Reset interaction tracking when modal opens
		hasHoveredYearSelector = false;
		isVariableAreaHovered = false;
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

	/**
	 * Checks if a variable is available for the selected years
	 */
	function isVariableAvailable(indicator: IndicatorMetadata): boolean {
		if ($currentYears.length === 0) return true; // No years selected, show all
		
		if ($currentYears.length === 1) {
			// Strict validation for single year - must be available for that specific year
			return indicator.available_years.includes($currentYears[0]);
		}
		
		// For multiple years, allow if available for ANY year
		return $currentYears.some(year => indicator.available_years.includes(year));
	}

	/**
	 * Gets availability message for a variable
	 */
	function getAvailabilityMessage(indicator: IndicatorMetadata): string {
		if ($currentYears.length === 1 && !indicator.available_years.includes($currentYears[0])) {
			return `Not available for ${$currentYears[0]}`;
		}
		return '';
	}

	/**
	 * Handles indicator toggle with availability check
	 */
	function handleIndicatorToggle(indicator: IndicatorMetadata): void {
		// Only allow toggle if variable is available
		if (isVariableAvailable(indicator)) {
			toggleIndicator(indicator.id);
		}
	}

	/**
	 * Handles label click for unavailable indicators
	 */
	function handleLabelClick(event: MouseEvent, indicator: IndicatorMetadata): void {
		if (!isVariableAvailable(indicator)) {
			// Prevent click propagation for unavailable indicators
			event.preventDefault();
			event.stopPropagation();
		}
	}

	/**
	 * Get theme-specific icon SVG path
	 */
	function getThemeIcon(theme: string): string {
		const themeKey = theme.toLowerCase();
		
		if (themeKey.includes('education') || themeKey.includes('school')) {
			return 'M12 14l9-5-9-5-9 5 9 5z M12 14l6.16-3.422a12.083 12.083 0 01.665 6.479A11.952 11.952 0 0012 20.055a11.952 11.952 0 00-6.824-2.998 12.078 12.078 0 01.665-6.479L12 14z';
		} else if (themeKey.includes('housing') || themeKey.includes('home')) {
			return 'M3 12l2-2m0 0l7-7 7 7M5 10v10a1 1 0 001 1h3m10-11l2 2m-2-2v10a1 1 0 01-1 1h-3m-6 0a1 1 0 001-1v-4a1 1 0 011-1h2a1 1 0 011 1v4a1 1 0 001 1m-6 0h6';
		} else if (themeKey.includes('economic') || themeKey.includes('income') || themeKey.includes('employment')) {
			return 'M12 8c-1.657 0-3 .895-3 2s1.343 2 3 2 3 .895 3 2-1.343 2-3 2m0-8c1.11 0 2.08.402 2.599 1M12 8V7m0 1v8m0 0v1m0-1c-1.11 0-2.08-.402-2.599-1';
		} else if (themeKey.includes('health') || themeKey.includes('medical')) {
			return 'M4.318 6.318a4.5 4.5 0 000 6.364L12 20.364l7.682-7.682a4.5 4.5 0 00-6.364-6.364L12 7.636l-1.318-1.318a4.5 4.5 0 00-6.364 0z';
		} else if (themeKey.includes('demographic') || themeKey.includes('population')) {
			return 'M17 20h5v-2a3 3 0 00-5.356-1.857M17 20H7m10 0v-2c0-.656-.126-1.283-.356-1.857M7 20H2v-2a3 3 0 015.356-1.857M7 20v-2c0-.656.126-1.283.356-1.857m0 0a5.002 5.002 0 019.288 0M15 7a3 3 0 11-6 0 3 3 0 016 0zm6 3a2 2 0 11-4 0 2 2 0 014 0zM7 10a2 2 0 11-4 0 2 2 0 014 0z';
		} else if (themeKey.includes('environment') || themeKey.includes('climate')) {
			return 'M3.055 11H5a2 2 0 012 2v1a2 2 0 002 2 2 2 0 012 2v2.945M8 3.935V5.5A2.5 2.5 0 0010.5 8h.5a2 2 0 012 2 2 2 0 104 0 2 2 0 012-2h1.064M15 20.488V18a2 2 0 012-2h3.064M21 12a9 9 0 11-18 0 9 9 0 0118 0z';
		} else if (themeKey.includes('transportation') || themeKey.includes('transit')) {
			return 'M8 17l4 4 4-4m-4-5v9m-6-9a6 6 0 1012 0v-3a6 6 0 10-12 0v3z';
		} else if (themeKey.includes('safety') || themeKey.includes('crime')) {
			return 'M9 12l2 2 4-4m5.618-4.016A11.955 11.955 0 0112 2.944a11.955 11.955 0 01-8.618 3.04A12.02 12.02 0 003 9c0 5.591 3.824 10.29 9 11.622 5.176-1.332 9-6.03 9-11.622 0-1.042-.133-2.052-.382-3.016z';
		} else {
			// Default icon for other themes
			return 'M7 7h.01M7 3h5c.512 0 1.024.195 1.414.586l7 7a2 2 0 010 2.828l-7 7a2 2 0 01-2.828 0l-7-7A1.994 1.994 0 013 12V7a4 4 0 014-4z';
		}
	}
</script>

<svelte:window on:keydown={handleKeydown} />

<!-- Unified Context Bar -->
<div class="bg-gradient-to-r from-white via-teal-50/30 to-white border-b border-teal-200/50 shadow-luxury backdrop-blur-sm sticky top-0 z-40">
	<div class="max-w-7xl mx-auto px-4 sm:px-6 lg:px-8">
		<!-- Main Context Bar -->
		<div class="flex items-center justify-between py-4">
			<!-- Left: Core Selections -->
			<div class="flex items-center space-x-6">
				<!-- Geography Level -->
				<div class="flex items-center space-x-3 group">
					<div class="flex items-center justify-center w-8 h-8 rounded-xl bg-gradient-to-br from-teal-100 to-teal-200 text-teal-700 shadow-elegant group-hover:shadow-luxury transition-all duration-300">
						<svg class="w-4 h-4" fill="none" stroke="currentColor" viewBox="0 0 24 24">
							<path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M17.657 16.657L13.414 20.9a1.998 1.998 0 01-2.827 0l-4.244-4.243a8 8 0 1111.314 0z"/>
							<path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M15 11a3 3 0 11-6 0 3 3 0 016 0z"/>
						</svg>
					</div>
					<select
						class="text-sm font-semibold bg-white/80 backdrop-blur-sm border border-teal-200/60 focus:ring-2 focus:ring-teal-500 focus:border-teal-500 rounded-xl px-4 py-2.5 cursor-pointer hover:bg-white hover:shadow-elegant transition-all duration-300 text-teal-800 min-w-[160px]"
						value={$currentGeoLevel || ''}
						on:change={handleGeoLevelChange}
					>
						<option value="" class="text-neutral-500">Select geography...</option>
						{#each geographyLevels as level}
							<option value={level} class="text-teal-800">{$geographies[level]?.name || level}</option>
						{/each}
					</select>
				</div>

				<!-- State Filter (Optional) -->
				{#if $currentGeoLevel}
					<div class="flex items-center space-x-3 group" transition:slide={{ duration: 300, easing: quintOut }}>
						<div class="flex items-center justify-center w-8 h-8 rounded-xl bg-gradient-to-br from-emerald-100 to-emerald-200 text-emerald-700 shadow-elegant group-hover:shadow-luxury transition-all duration-300">
							<svg class="w-4 h-4" fill="none" stroke="currentColor" viewBox="0 0 24 24">
								<path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M9 20l-5.447-2.724A1 1 0 013 16.382V5.618a1 1 0 011.447-.894L9 7m0 13l6-3m-6 3V7m6 10l4.553 2.276A1 1 0 0021 18.382V7.618a1 1 0 00-.553-.894L15 4m0 13V4m0 0L9 7"/>
							</svg>
						</div>
						<select
							class="text-sm font-semibold bg-white/80 backdrop-blur-sm border border-teal-200/60 focus:ring-2 focus:ring-teal-500 focus:border-teal-500 rounded-xl px-4 py-2.5 cursor-pointer hover:bg-white hover:shadow-elegant transition-all duration-300 text-teal-800 min-w-[140px]"
							value={$currentGeoFilter || ''}
							on:change={handleStateFilterChange}
						>
							<option value="" class="text-neutral-500">All States</option>
							{#each US_STATES as state}
								<option value={state.code} class="text-teal-800">{state.name}</option>
							{/each}
						</select>
					</div>
				{/if}

				<!-- Year -->
				<div class="flex items-center space-x-3 group relative">
					<div class="flex items-center justify-center w-8 h-8 rounded-xl bg-gradient-to-br from-teal-100 to-teal-200 text-teal-700 shadow-elegant group-hover:shadow-luxury transition-all duration-300">
						<svg class="w-4 h-4" fill="none" stroke="currentColor" viewBox="0 0 24 24">
							<path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M8 7V3m8 4V3m-9 8h10M5 21h14a2 2 0 002-2V7a2 2 0 00-2-2H5a2 2 0 002 2z"/>
						</svg>
					</div>
					<div class="bg-white/80 backdrop-blur-sm border border-teal-200/60 rounded-xl hover:bg-white hover:shadow-elegant transition-all duration-300 min-w-[140px]">
						<YearSelector
							selectedYears={$currentYears}
							mode="dropdown"
							placeholder="Select years..."
							on:change={(event) => setYears(event.detail.selectedYears)}
						/>
					</div>
				</div>

				<!-- Variables -->
				<div class="flex items-center space-x-3 group">
					<div class="flex items-center justify-center w-8 h-8 rounded-xl bg-gradient-to-br from-teal-100 to-teal-200 text-teal-700 shadow-elegant group-hover:shadow-luxury transition-all duration-300">
						<svg class="w-4 h-4" fill="none" stroke="currentColor" viewBox="0 0 24 24">
							<path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M9 19v-6a2 2 0 00-2-2H5a2 2 0 00-2 2v6a2 2 0 002 2h2a2 2 0 002-2zm0 0V9a2 2 0 012-2h2a2 2 0 012 2v10m-6 0a2 2 0 002 2h2a2 2 0 002-2m0 0V5a2 2 0 012-2h2a2 2 0 012 2v14a2 2 0 01-2 2h-2a2 2 0 01-2-2z"/>
						</svg>
					</div>
					<button
						class="text-sm font-semibold bg-white/80 backdrop-blur-sm border border-teal-200/60 focus:ring-2 focus:ring-teal-500 focus:border-teal-500 rounded-xl px-4 py-2.5 cursor-pointer hover:bg-white hover:shadow-elegant transition-all duration-300 text-left text-teal-800 min-w-[180px] flex items-center justify-between"
						on:click={() => $showVariableSelector = !$showVariableSelector}
					>
						<span class="truncate">{getVariableDisplayText()}</span>
						<svg class="w-4 h-4 ml-2 transition-transform duration-300 {$showVariableSelector ? 'rotate-180' : ''}" fill="none" stroke="currentColor" viewBox="0 0 24 24">
							<path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M19 9l-7 7-7-7" />
						</svg>
					</button>
				</div>
			</div>

			<!-- Right: Actions -->
			<div class="flex items-center space-x-3">
				<Button variant="ghost" size="sm" on:click={() => showAdvanced = !showAdvanced}>
					<svg class="w-4 h-4 mr-1.5" fill="none" stroke="currentColor" viewBox="0 0 24 24">
						<path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M12 6V4m0 2a2 2 0 100 4m0-4a2 2 0 110 4m-6 8a2 2 0 100-4m0 4a2 2 0 100 4m0-4v2m0-6V4m6 6v10m6-2a2 2 0 100-4m0 4a2 2 0 100 4m0-4v2m0-6V4"/>
					</svg>
					{showAdvanced ? 'Hide' : 'Show'} Advanced
				</Button>
				
				<Button variant="outline" size="sm" on:click={resetFilters}>
					<svg class="w-4 h-4 mr-1.5" fill="none" stroke="currentColor" viewBox="0 0 24 24">
						<path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M4 4v5h.582m15.356 2A8.001 8.001 0 004.582 9m0 0H9m11 11v-5h-.581m0 0a8.003 8.003 0 01-15.357-2m15.357 2H15"/>
					</svg>
					Reset
				</Button>
			</div>
		</div>

		<!-- Advanced Options -->
		{#if showAdvanced}
			<div class="border-t border-teal-200/50 py-6 bg-gradient-to-r from-teal-50/20 via-white/50 to-teal-50/20" transition:slide={{ duration: 300, easing: quintOut }}>
				<div class="grid grid-cols-1 md:grid-cols-3 gap-6">
					<!-- Primary Indicator (for single-variable views) -->
					<div class="space-y-3">
						<div class="flex items-center space-x-2">
							<div class="w-6 h-6 rounded-lg bg-gradient-to-br from-teal-100 to-teal-200 flex items-center justify-center">
								<svg class="w-3 h-3 text-teal-700" fill="none" stroke="currentColor" viewBox="0 0 24 24">
									<path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M13 10V3L4 14h7v7l9-11h-7z"/>
								</svg>
							</div>
							<label class="text-sm font-semibold text-teal-800">
								Primary Indicator (Maps)
							</label>
						</div>
						<select
							class="w-full text-sm font-medium bg-white/90 backdrop-blur-sm border border-teal-200/60 focus:ring-2 focus:ring-teal-500 focus:border-teal-500 rounded-xl px-4 py-2.5 cursor-pointer hover:bg-white hover:shadow-elegant transition-all duration-300 text-teal-800"
							value={$currentPrimaryIndicator || ''}
							on:change={handlePrimaryIndicatorChange}
						>
							<option value="" class="text-neutral-500">Select primary indicator...</option>
							{#each Object.entries($indicatorsByTheme) as [theme, themeIndicators]}
								<optgroup label={theme} class="font-semibold text-teal-700">
									{#each themeIndicators as indicator}
										<option value={indicator.id} class="text-teal-800 font-normal">{indicator.name}</option>
									{/each}
								</optgroup>
							{/each}
						</select>
					</div>

					<!-- Current State Summary -->
					<div class="space-y-3">
						<div class="flex items-center space-x-2">
							<div class="w-6 h-6 rounded-lg bg-gradient-to-br from-emerald-100 to-emerald-200 flex items-center justify-center">
								<svg class="w-3 h-3 text-emerald-700" fill="none" stroke="currentColor" viewBox="0 0 24 24">
									<path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M9 12l2 2 4-4m6 2a9 9 0 11-18 0 9 9 0 0118 0z"/>
								</svg>
							</div>
							<label class="text-sm font-semibold text-teal-800">
								Current Context
							</label>
						</div>
						<div class="bg-white/60 backdrop-blur-sm border border-teal-200/40 rounded-xl p-4 space-y-2">
							<div class="flex items-center justify-between text-xs">
								<span class="font-medium text-teal-700">Geography:</span>
								<span class="text-teal-800 font-semibold">{getGeoDisplayName($currentGeoLevel)}</span>
							</div>
							{#if $currentGeoFilter}
								<div class="flex items-center justify-between text-xs">
									<span class="font-medium text-teal-700">State:</span>
									<span class="text-teal-800 font-semibold">{getStateNameByCode($currentGeoFilter) || $currentGeoFilter}</span>
								</div>
							{/if}
							<div class="flex items-center justify-between text-xs">
								<span class="font-medium text-teal-700">Year:</span>
								<span class="text-teal-800 font-semibold">{$currentPrimaryYear || 'Not selected'}</span>
							</div>
							<div class="flex items-center justify-between text-xs">
								<span class="font-medium text-teal-700">Variables:</span>
								<span class="text-teal-800 font-semibold">{$selectedIndicatorCount} selected</span>
							</div>
						</div>
					</div>

					<!-- Quick Actions -->
					<div class="space-y-3">
						<div class="flex items-center space-x-2">
							<div class="w-6 h-6 rounded-lg bg-gradient-to-br from-teal-100 to-teal-200 flex items-center justify-center">
								<svg class="w-3 h-3 text-teal-700" fill="none" stroke="currentColor" viewBox="0 0 24 24">
									<path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M13 10V3L4 14h7v7l9-11h-7z"/>
								</svg>
							</div>
							<label class="text-sm font-semibold text-teal-800">
								Quick Actions
							</label>
						</div>
						<div class="flex flex-col space-y-2">
							{#if $selectedIndicatorCount > 0}
								<Button variant="ghost" size="sm" on:click={clearIndicators}>
									<svg class="w-4 h-4 mr-1.5" fill="none" stroke="currentColor" viewBox="0 0 24 24">
										<path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M19 7l-.867 12.142A2 2 0 0116.138 21H7.862a2 2 0 01-1.995-1.858L5 7m5 4v6m4-6v6m1-10V4a1 1 0 00-1-1h-4a1 1 0 00-1 1v3M4 7h16"/>
									</svg>
									Clear Variables
								</Button>
							{/if}
							<Button variant="ghost" size="sm" on:click={() => $showVariableSelector = true}>
								<svg class="w-4 h-4 mr-1.5" fill="none" stroke="currentColor" viewBox="0 0 24 24">
									<path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M12 6v6m0 0v6m0-6h6m-6 0H6"/>
								</svg>
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
	<div 
		bind:this={modalElement}
		on:click={handleModalClick}
		class="fixed inset-0 bg-gradient-to-br from-black/60 via-black/50 to-black/60 backdrop-blur-sm z-50 flex items-center justify-center p-4" 
		transition:slide={{ duration: 300 }}
	>
		<div class="bg-gradient-to-br from-white via-white to-teal-50/30 rounded-2xl shadow-floating border border-teal-200/30 max-w-4xl w-full max-h-[85vh] flex flex-col backdrop-blur-sm">
			<!-- Modal Header -->
			<div class="p-6 border-b border-teal-200/40 bg-gradient-to-r from-white via-teal-50/20 to-white rounded-t-2xl">
				<div class="flex items-center justify-between">
					<div class="flex items-center space-x-3">
						<div class="w-10 h-10 rounded-xl bg-gradient-to-br from-teal-100 to-teal-200 flex items-center justify-center shadow-elegant">
							<svg class="w-5 h-5 text-teal-700" fill="none" stroke="currentColor" viewBox="0 0 24 24">
								<path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M9 19v-6a2 2 0 00-2-2H5a2 2 0 00-2 2v6a2 2 0 002 2h2a2 2 0 002-2zm0 0V9a2 2 0 012-2h2a2 2 0 012 2v10m-6 0a2 2 0 002 2h2a2 2 0 002-2m0 0V5a2 2 0 012-2h2a2 2 0 012 2v14a2 2 0 01-2 2h-2a2 2 0 01-2-2z"/>
							</svg>
						</div>
						<div>
							<h2 class="text-xl font-bold text-teal-900">Select Variables</h2>
							<p class="text-sm text-teal-700 mt-0.5">Choose variables for analysis and visualization</p>
						</div>
					</div>
					<div class="flex items-center space-x-3">
						{#if $selectedIndicatorCount > 0}
							<div class="flex items-center space-x-2 bg-gradient-to-r from-teal-100 to-teal-200 text-teal-800 px-4 py-2 rounded-full shadow-elegant border border-teal-300/50">
								<div class="w-2 h-2 bg-teal-600 rounded-full animate-pulse"></div>
								<span class="text-sm font-semibold">
									{$selectedIndicatorCount} selected
								</span>
							</div>
							<Button variant="ghost" size="sm" on:click={clearIndicators}>
								<svg class="w-4 h-4 mr-1.5" fill="none" stroke="currentColor" viewBox="0 0 24 24">
									<path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M19 7l-.867 12.142A2 2 0 0116.138 21H7.862a2 2 0 01-1.995-1.858L5 7m5 4v6m4-6v6m1-10V4a1 1 0 00-1-1h-4a1 1 0 00-1 1v3M4 7h16"/>
								</svg>
								Clear All
							</Button>
						{/if}
						<button
							class="w-10 h-10 rounded-xl bg-white/80 backdrop-blur-sm border border-teal-200/60 text-teal-600 hover:text-teal-800 hover:bg-white hover:shadow-elegant transition-all duration-300 flex items-center justify-center"
							on:click={() => $showVariableSelector = false}
						>
							<svg class="w-5 h-5" fill="none" stroke="currentColor" viewBox="0 0 24 24">
								<path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M6 18L18 6M6 6l12 12" />
							</svg>
						</button>
					</div>
				</div>

				<!-- Year Selection -->
				<div 
					class="mt-6 p-4 bg-white/60 backdrop-blur-sm border border-teal-200/40 rounded-xl transition-all duration-300 ease-in-out overflow-hidden" 
					style="max-height: {hasHoveredYearSelector && isVariableAreaHovered ? '3rem' : '200px'};"
					on:mouseenter={() => hasHoveredYearSelector = true}
				>
					<YearSelector
						selectedYears={$currentYears}
						mode="inline"
						collapsed={hasHoveredYearSelector && isVariableAreaHovered}
						on:change={(event) => setYears(event.detail.selectedYears)}
					/>
				</div>


			</div>

			<!-- Modal Content -->
			<div 
				class="flex-1 overflow-y-auto p-6 bg-gradient-to-b from-white/50 to-teal-50/20" 
				on:mouseenter={() => isVariableAreaHovered = true}
				on:mouseleave={() => isVariableAreaHovered = false}
			>
				<!-- Search Bar -->
				<div class="mb-6 relative">
					<div class="absolute inset-y-0 left-0 pl-4 flex items-center pointer-events-none">
						<svg class="h-5 w-5 text-teal-500" fill="none" viewBox="0 0 24 24" stroke="currentColor">
							<path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M21 21l-6-6m2-5a7 7 0 11-14 0 7 7 0 0114 0z" />
						</svg>
					</div>
					<input
						bind:value={searchTerm}
						type="text"
						placeholder="Search variables..."
						class="block w-full pl-12 pr-12 py-3 bg-white/80 backdrop-blur-sm border border-teal-200/60 rounded-xl text-sm placeholder-teal-400 focus:outline-none focus:ring-2 focus:ring-teal-500 focus:border-teal-500 hover:bg-white hover:shadow-elegant transition-all duration-300 text-teal-800 font-medium"
					/>
					{#if searchTerm}
						<button
							on:click={() => searchTerm = ''}
							class="absolute inset-y-0 right-0 pr-4 flex items-center text-teal-400 hover:text-teal-600 transition-colors"
						>
							<svg class="h-5 w-5" fill="none" viewBox="0 0 24 24" stroke="currentColor">
								<path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M6 18L18 6M6 6l12 12" />
							</svg>
						</button>
					{/if}
				</div>

				{#if Object.keys(filteredIndicatorsByTheme).length > 0}
					<!-- Theme Controls -->
					{#if !searchTerm && Object.keys($indicatorsByTheme).length > 1}
						<div class="flex gap-2 mb-4">
							<button
								on:click={expandAllThemes}
								class="text-xs font-medium text-teal-700 bg-white/80 hover:bg-white border border-teal-200/60 hover:border-teal-300 rounded-lg px-2 py-1 transition-all duration-200 hover:shadow-sm"
							>
								<svg class="w-3 h-3 mr-1 inline" fill="none" stroke="currentColor" viewBox="0 0 24 24">
									<path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M4 8V4m0 0h4M4 4l5 5m11-1V4m0 0h-4m4 0l-5 5M4 16v4m0 0h4m-4 0l5-5m11 5l-5-5m5 5v-4m0 4h-4"/>
								</svg>
								Expand All
							</button>
							<button
								on:click={collapseAllThemes}
								class="text-xs font-medium text-teal-700 bg-white/80 hover:bg-white border border-teal-200/60 hover:border-teal-300 rounded-lg px-2 py-1 transition-all duration-200 hover:shadow-sm"
							>
								<svg class="w-3 h-3 mr-1 inline" fill="none" stroke="currentColor" viewBox="0 0 24 24">
									<path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M9 9l6 6m0 0l6-6m-6 6V3"/>
								</svg>
								Collapse All
							</button>
						</div>
					{/if}

					<div class="space-y-4">
						{#each Object.entries(filteredIndicatorsByTheme) as [theme, indicators]}
							<div class="bg-white/80 backdrop-blur-sm border border-teal-200/40 rounded-xl overflow-hidden shadow-elegant hover:shadow-luxury transition-all duration-300">
								<!-- Theme Header -->
								<button
									on:click={() => toggleTheme(theme)}
									class="w-full px-6 py-4 bg-gradient-to-r from-teal-50/60 to-emerald-50/60 hover:from-teal-100/60 hover:to-emerald-100/60 border-b border-teal-200/40 flex items-center justify-between text-left transition-all duration-300 group"
								>
									<div class="flex items-center gap-3">
										<div class="w-8 h-8 rounded-lg bg-gradient-to-br from-teal-100 to-teal-200 flex items-center justify-center shadow-elegant group-hover:shadow-luxury transition-all duration-300">
											<svg class="w-4 h-4 text-teal-700" fill="none" stroke="currentColor" viewBox="0 0 24 24">
												<path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="{getThemeIcon(theme)}"/>
											</svg>
										</div>
										<div>
											<span class="font-bold text-teal-900 capitalize text-base">{theme}</span>
											<div class="flex items-center gap-2 mt-0.5">
												<span class="text-xs font-semibold text-teal-700 bg-gradient-to-r from-teal-100 to-teal-200 px-2 py-1 rounded-full border border-teal-300/50">
													{indicators.length} variable{indicators.length === 1 ? '' : 's'}
												</span>
											</div>
										</div>
									</div>
									<svg 
										class="h-5 w-5 text-teal-600 transition-transform duration-300 {expandedThemes.has(theme) ? 'rotate-180' : ''}"
										fill="none" 
										viewBox="0 0 24 24" 
										stroke="currentColor"
									>
										<path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M19 9l-7 7-7-7" />
									</svg>
								</button>

								<!-- Theme Content -->
								{#if expandedThemes.has(theme)}
									<div class="divide-y divide-teal-100/50">
										{#each indicators as indicator}
											{@const isSelected = $currentSelectedIndicators.includes(indicator.id)}
											{@const isAvailable = isVariableAvailable(indicator)}
											{@const availabilityMessage = getAvailabilityMessage(indicator)}
											<label 
												class="flex items-start gap-4 p-5 transition-all duration-300 group {isAvailable ? 'hover:bg-gradient-to-r hover:from-teal-50/40 hover:to-emerald-50/40 cursor-pointer' : 'cursor-not-allowed opacity-50'}"
												title={availabilityMessage || undefined}
												on:click={(event) => handleLabelClick(event, indicator)}
											>
												<div class="relative mt-1">
													<input
														type="checkbox"
														checked={isSelected}
														disabled={!isAvailable}
														on:change={() => handleIndicatorToggle(indicator)}
														on:click|stopPropagation
														class="h-5 w-5 text-teal-600 border-2 border-teal-300 rounded-lg focus:ring-teal-500 focus:ring-2 transition-all duration-300 {isAvailable ? 'cursor-pointer' : 'cursor-not-allowed'}"
													/>
													{#if isSelected && isAvailable}
														<div class="absolute inset-0 flex items-center justify-center pointer-events-none">
															<svg class="h-3 w-3 text-white" fill="currentColor" viewBox="0 0 20 20">
																<path fill-rule="evenodd" d="M16.707 5.293a1 1 0 010 1.414l-8 8a1 1 0 01-1.414 0l-4-4a1 1 0 011.414-1.414L8 12.586l7.293-7.293a1 1 0 011.414 0z" clip-rule="evenodd" />
															</svg>
														</div>
													{/if}
												</div>
												<div class="flex-1 min-w-0">
													<div class="flex items-center gap-3 mb-2">
														<span class="font-semibold text-sm transition-colors {isAvailable ? 'text-teal-900 group-hover:text-teal-800' : 'text-teal-500'}">
															{indicator.name}
														</span>
														{#if isSelected && isAvailable}
															<div class="flex items-center gap-1 bg-gradient-to-r from-teal-100 to-teal-200 text-teal-800 px-2 py-1 rounded-full border border-teal-300/50">
																<svg class="h-3 w-3" fill="currentColor" viewBox="0 0 20 20">
																	<path fill-rule="evenodd" d="M16.707 5.293a1 1 0 010 1.414l-8 8a1 1 0 01-1.414 0l-4-4a1 1 0 011.414-1.414L8 12.586l7.293-7.293a1 1 0 011.414 0z" clip-rule="evenodd" />
																</svg>
																<span class="text-xs font-semibold">Selected</span>
															</div>
														{/if}
													</div>
													<p class="text-sm mb-3 leading-relaxed {isAvailable ? 'text-teal-700' : 'text-teal-400'}">
														{indicator.description}
													</p>
													<div class="flex flex-col gap-2">
														<div class="flex items-center gap-3 text-xs">
															<div class="flex items-center gap-1 bg-white/60 px-2 py-1 rounded-lg border {isAvailable ? 'text-teal-600 border-teal-200/40' : 'text-teal-400 border-teal-200/20'}">
																<svg class="w-3 h-3" fill="none" stroke="currentColor" viewBox="0 0 24 24">
																	<path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M7 7h.01M7 3h5c.512 0 1.024.195 1.414.586l7 7a2 2 0 010 2.828l-7 7a2 2 0 01-2.828 0l-7-7A1.994 1.994 0 013 12V7a4 4 0 014-4z"/>
																</svg>
																<span class="font-medium">ID: {indicator.id}</span>
															</div>
															<div class="flex items-center gap-1 bg-white/60 px-2 py-1 rounded-lg border {isAvailable ? 'text-teal-600 border-teal-200/40' : 'text-teal-400 border-teal-200/20'}">
																<svg class="w-3 h-3" fill="none" stroke="currentColor" viewBox="0 0 24 24">
																	<path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M8 7V3m8 4V3m-9 8h10M5 21h14a2 2 0 002-2V7a2 2 0 00-2-2H5a2 2 0 00-2 2v12a2 2 0 002 2z"/>
																</svg>
																<span class="font-medium">{indicator.available_years.length} years</span>
															</div>
															<div class="flex items-center gap-1 bg-white/60 px-2 py-1 rounded-lg border {isAvailable ? 'text-teal-600 border-teal-200/40' : 'text-teal-400 border-teal-200/20'}">
																<svg class="w-3 h-3" fill="none" stroke="currentColor" viewBox="0 0 24 24">
																	<path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M13 7h8m0 0v8m0-8l-8 8-4-4-6 6"/>
																</svg>
																<span class="font-medium">{indicator.available_years[0]}-{indicator.available_years[indicator.available_years.length - 1]}</span>
															</div>
														</div>
														{#if availabilityMessage}
															<div class="text-xs text-red-600 font-medium">
																{availabilityMessage}
															</div>
														{/if}
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
					<div class="text-center py-16">
						<div class="w-20 h-20 mx-auto mb-6 rounded-2xl bg-gradient-to-br from-teal-100 to-teal-200 flex items-center justify-center shadow-elegant">
							<svg class="w-10 h-10 text-teal-600" fill="none" viewBox="0 0 24 24" stroke="currentColor">
								<path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M21 21l-6-6m2-5a7 7 0 11-14 0 7 7 0 0114 0z" />
							</svg>
						</div>
						<h3 class="text-lg font-bold text-teal-900 mb-2">No variables found</h3>
						<p class="text-sm text-teal-700 max-w-md mx-auto">
							Try adjusting your search terms or browse by category to find the variables you need.
						</p>
					</div>
				{:else}
					<!-- Loading State -->
					<div class="text-center py-16">
						<div class="w-20 h-20 mx-auto mb-6 rounded-2xl bg-gradient-to-br from-teal-100 to-teal-200 flex items-center justify-center shadow-elegant">
							<div class="animate-spin rounded-full h-10 w-10 border-4 border-teal-300 border-t-teal-600"></div>
						</div>
						<h3 class="text-lg font-bold text-teal-900 mb-2">Loading variables...</h3>
						<p class="text-sm text-teal-700">Please wait while we fetch the available data variables.</p>
					</div>
				{/if}
			</div>

			<!-- Modal Footer -->
			<div class="p-6 border-t border-teal-200/40 bg-gradient-to-r from-white via-teal-50/20 to-white rounded-b-2xl">
				<div class="flex items-center justify-between">
					<div class="text-sm text-teal-700 space-y-1">
						{#if $selectedIndicatorCount > 0}
							<div class="flex items-center gap-2">
								<div class="w-3 h-3 bg-teal-600 rounded-full animate-pulse"></div>
								<span class="font-semibold">
									<strong class="text-teal-900">{$selectedIndicatorCount}</strong> variable{$selectedIndicatorCount === 1 ? '' : 's'} selected for analysis
								</span>
							</div>
						{:else}
							<div class="flex items-center gap-2">
								<div class="w-3 h-3 bg-neutral-400 rounded-full"></div>
								<span class="font-medium text-neutral-600">Select variables to enable analysis features</span>
							</div>
						{/if}
						{#if $currentYears.length > 0}
							<div class="flex items-center gap-2">
								<svg class="w-3 h-3 text-teal-600" fill="none" stroke="currentColor" viewBox="0 0 24 24">
									<path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M8 7V3m8 4V3m-9 8h10M5 21h14a2 2 0 002-2V7a2 2 0 00-2-2H5a2 2 0 00-2 2v12a2 2 0 002 2z"/>
								</svg>
								<span class="font-medium">
									<strong class="text-teal-900">{$currentYears.length}</strong> year{$currentYears.length === 1 ? '' : 's'} selected: {$currentYears.sort((a, b) => a - b).join(', ')}
								</span>
							</div>
						{/if}
					</div>
					<Button variant="primary" on:click={() => showVariableSelector.set(false)}>
						<svg class="w-4 h-4 mr-2" fill="none" stroke="currentColor" viewBox="0 0 24 24">
							<path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M5 13l4 4L19 7"/>
						</svg>
						Done
					</Button>
				</div>
			</div>
		</div>
	</div>
{/if}
