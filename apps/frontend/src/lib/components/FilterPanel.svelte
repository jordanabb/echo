<script lang="ts">
	import { onMount } from 'svelte';
	import { derived } from 'svelte/store';
	import Card from './Card.svelte';
	import Button from './Button.svelte';
	import { 
		indicators, 
		geographies, 
		indicatorsByTheme, 
		allAvailableYears,
		getAvailableYearsForIndicator,
		metadataLoading,
		metadataError,
		initializeMetadata
	} from '../stores/metadata';
	import { 
		filters, 
		updateFilter, 
		updateFilters, 
		resetFilters, 
		areFiltersValid,
		initializeFilters
	} from '../stores/filters';

	// Component state
	let selectedState: string | null = null;
	let selectedCounty: string | null = null;
	let showAdvanced = false;

	// Initialize stores on mount
	onMount(() => {
		initializeMetadata();
		initializeFilters();
	});

	// Reactive computations for cascading logic
	$: currentIndicator = $filters.indicator;
	$: currentGeoLevel = $filters.geoLevel;
	$: currentYear = $filters.year;

	// Available years for the selected indicator, or all years if no indicator selected
	$: availableYears = currentIndicator 
		? getAvailableYearsForIndicator(currentIndicator) 
		: $allAvailableYears;
	
	// Check if current year is valid for selected indicator
	$: isCurrentYearValid = currentYear && availableYears.includes(currentYear);

	// Geography-specific logic
	$: requiresStateCounty = currentGeoLevel === 'tract' || currentGeoLevel === 'census_tract';
	$: geographyLevels = Object.keys($geographies);

	// Validation states
	$: isIndicatorValid = currentIndicator && $indicators.some(ind => ind.id === currentIndicator);
	$: isGeoLevelValid = currentGeoLevel && geographyLevels.includes(currentGeoLevel);
	$: isYearValid = currentYear && isCurrentYearValid;
	$: isLocationValid = !requiresStateCounty || (selectedState && selectedCounty);

	// Load button state
	$: canLoad = $areFiltersValid && isLocationValid && !$metadataLoading;

	// Helper functions
	function handleIndicatorChange(event: Event) {
		const target = event.target as HTMLSelectElement;
		const indicatorId = target.value || null;
		
		if (indicatorId) {
			const availableYearsForIndicator = getAvailableYearsForIndicator(indicatorId);
			// If current year is not available for new indicator, select the latest available year
			const newYear = availableYearsForIndicator.includes(currentYear || 0) 
				? currentYear 
				: availableYearsForIndicator[0] || null;
			
			updateFilters({
				indicator: indicatorId,
				year: newYear
			});
		} else {
			updateFilter('indicator', null);
		}
	}

	function handleGeoLevelChange(event: Event) {
		const target = event.target as HTMLSelectElement;
		const geoLevel = target.value || null;
		
		// Reset location selections when geography level changes
		selectedState = null;
		selectedCounty = null;
		
		updateFilter('geoLevel', geoLevel);
	}

	function handleYearChange(event: Event) {
		const target = event.target as HTMLSelectElement;
		const year = target.value ? parseInt(target.value) : null;
		updateFilter('year', year);
	}

	function handleStateChange(event: Event) {
		const target = event.target as HTMLSelectElement;
		selectedState = target.value || null;
		selectedCounty = null; // Reset county when state changes
	}

	function handleCountyChange(event: Event) {
		const target = event.target as HTMLSelectElement;
		selectedCounty = target.value || null;
	}

	function handleReset() {
		selectedState = null;
		selectedCounty = null;
		resetFilters();
	}

	function handleLoad() {
		if (canLoad) {
			// Emit custom event that parent components can listen to
			const event = new CustomEvent('load-data', {
				detail: {
					indicator: currentIndicator,
					geoLevel: currentGeoLevel,
					year: currentYear,
					state: selectedState,
					county: selectedCounty
				}
			});
			document.dispatchEvent(event);
		}
	}

	// Mock data for states and counties (in real app, this would come from API)
	const mockStates = [
		{ id: 'CA', name: 'California' },
		{ id: 'TX', name: 'Texas' },
		{ id: 'FL', name: 'Florida' },
		{ id: 'NY', name: 'New York' },
		{ id: 'PA', name: 'Pennsylvania' }
	];

	const mockCounties = {
		'CA': [
			{ id: 'los-angeles', name: 'Los Angeles County' },
			{ id: 'san-francisco', name: 'San Francisco County' },
			{ id: 'orange', name: 'Orange County' }
		],
		'TX': [
			{ id: 'harris', name: 'Harris County' },
			{ id: 'dallas', name: 'Dallas County' },
			{ id: 'travis', name: 'Travis County' }
		],
		'FL': [
			{ id: 'miami-dade', name: 'Miami-Dade County' },
			{ id: 'broward', name: 'Broward County' },
			{ id: 'orange-fl', name: 'Orange County' }
		],
		'NY': [
			{ id: 'new-york', name: 'New York County' },
			{ id: 'kings', name: 'Kings County' },
			{ id: 'queens', name: 'Queens County' }
		],
		'PA': [
			{ id: 'philadelphia', name: 'Philadelphia County' },
			{ id: 'allegheny', name: 'Allegheny County' },
			{ id: 'montgomery', name: 'Montgomery County' }
		]
	};

	$: availableCounties = selectedState ? mockCounties[selectedState as keyof typeof mockCounties] || [] : [];
</script>

<Card variant="elevated" padding="lg">
	<div class="space-y-6">
		<!-- Header -->
		<div class="flex items-center justify-between">
			<div>
				<h2 class="text-2xl font-bold text-neutral-900 font-display">Data Filters</h2>
				<p class="text-sm text-neutral-600 mt-1">Configure your data selection</p>
			</div>
			<div class="flex items-center space-x-2">
				<Button variant="ghost" size="sm" on:click={handleReset}>
					Reset
				</Button>
				<button
					class="text-sm text-primary-600 hover:text-primary-700 transition-colors"
					on:click={() => showAdvanced = !showAdvanced}
				>
					{showAdvanced ? 'Hide' : 'Show'} Advanced
				</button>
			</div>
		</div>

		{#if $metadataError}
			<div class="bg-error-50 border border-error-200 rounded-lg p-4">
				<div class="flex items-center">
					<svg class="w-5 h-5 text-error-600 mr-2" fill="currentColor" viewBox="0 0 20 20">
						<path fill-rule="evenodd" d="M10 18a8 8 0 100-16 8 8 0 000 16zM8.707 7.293a1 1 0 00-1.414 1.414L8.586 10l-1.293 1.293a1 1 0 101.414 1.414L10 11.414l1.293 1.293a1 1 0 001.414-1.414L11.414 10l1.293-1.293a1 1 0 00-1.414-1.414L10 8.586 8.707 7.293z" clip-rule="evenodd" />
					</svg>
					<span class="text-error-800 text-sm font-medium">Error loading metadata: {$metadataError}</span>
				</div>
			</div>
		{/if}

		<!-- Main Filters -->
		<div class="grid grid-cols-1 md:grid-cols-3 gap-4">
			<!-- Indicator Selection -->
			<div class="space-y-2">
				<label for="indicator" class="block text-sm font-medium text-neutral-700">
					Indicator
					<span class="text-error-500">*</span>
				</label>
				<div class="relative">
					<select
						id="indicator"
						class="w-full px-3 py-2 border border-neutral-300 rounded-lg focus:ring-2 focus:ring-primary-500 focus:border-primary-500 transition-colors"
						class:border-error-300={!isIndicatorValid && currentIndicator}
						class:ring-error-500={!isIndicatorValid && currentIndicator}
						value={currentIndicator || ''}
						on:change={handleIndicatorChange}
						disabled={$metadataLoading}
					>
						<option value="">Select an indicator...</option>
						{#each Object.entries($indicatorsByTheme) as [theme, themeIndicators]}
							<optgroup label={theme}>
								{#each themeIndicators as indicator}
									<option value={indicator.id}>{indicator.name}</option>
								{/each}
							</optgroup>
						{/each}
					</select>
					{#if $metadataLoading}
						<div class="absolute right-3 top-1/2 transform -translate-y-1/2">
							<svg class="animate-spin h-4 w-4 text-neutral-400" fill="none" viewBox="0 0 24 24">
								<circle class="opacity-25" cx="12" cy="12" r="10" stroke="currentColor" stroke-width="4"></circle>
								<path class="opacity-75" fill="currentColor" d="M4 12a8 8 0 018-8V0C5.373 0 0 5.373 0 12h4zm2 5.291A7.962 7.962 0 014 12H0c0 3.042 1.135 5.824 3 7.938l3-2.647z"></path>
							</svg>
						</div>
					{/if}
				</div>
				{#if currentIndicator && $indicators.find(ind => ind.id === currentIndicator)}
					<p class="text-xs text-neutral-600">
						{$indicators.find(ind => ind.id === currentIndicator)?.description}
					</p>
				{/if}
			</div>

			<!-- Geography Level Selection -->
			<div class="space-y-2">
				<label for="geoLevel" class="block text-sm font-medium text-neutral-700">
					Geography Level
					<span class="text-error-500">*</span>
				</label>
				<select
					id="geoLevel"
					class="w-full px-3 py-2 border border-neutral-300 rounded-lg focus:ring-2 focus:ring-primary-500 focus:border-primary-500 transition-colors"
					class:border-error-300={!isGeoLevelValid && currentGeoLevel}
					value={currentGeoLevel || ''}
					on:change={handleGeoLevelChange}
					disabled={$metadataLoading}
				>
					<option value="">Select geographic unit...</option>
					{#each geographyLevels as level}
						<option value={level}>{$geographies[level]?.name || level}</option>
					{/each}
				</select>
				{#if requiresStateCounty}
					<p class="text-xs text-warning-600 flex items-center">
						<svg class="w-3 h-3 mr-1" fill="currentColor" viewBox="0 0 20 20">
							<path fill-rule="evenodd" d="M8.257 3.099c.765-1.36 2.722-1.36 3.486 0l5.58 9.92c.75 1.334-.213 2.98-1.742 2.98H4.42c-1.53 0-2.493-1.646-1.743-2.98l5.58-9.92zM11 13a1 1 0 11-2 0 1 1 0 012 0zm-1-8a1 1 0 00-1 1v3a1 1 0 002 0V6a1 1 0 00-1-1z" clip-rule="evenodd" />
						</svg>
						Requires state and county selection
					</p>
				{/if}
			</div>

			<!-- Year Selection -->
			<div class="space-y-2">
				<label for="year" class="block text-sm font-medium text-neutral-700">
					Year
					<span class="text-error-500">*</span>
				</label>
				<select
					id="year"
					class="w-full px-3 py-2 border border-neutral-300 rounded-lg focus:ring-2 focus:ring-primary-500 focus:border-primary-500 transition-colors"
					class:border-error-300={!isYearValid && currentYear}
					value={currentYear || ''}
					on:change={handleYearChange}
					disabled={$metadataLoading}
				>
					<option value="">Select year...</option>
					{#each availableYears as year}
						<option value={year}>{year}</option>
					{/each}
				</select>
				{#if currentIndicator && availableYears.length === 0}
					<p class="text-xs text-neutral-500">No years available for selected indicator</p>
				{:else if currentIndicator && availableYears.length > 0}
					<p class="text-xs text-neutral-600">
						{availableYears.length} year{availableYears.length !== 1 ? 's' : ''} available
					</p>
				{/if}
			</div>
		</div>

		<!-- Location Selection (for Census Tracts) -->
		{#if requiresStateCounty}
			<div class="border-t border-neutral-200 pt-4">
				<h3 class="text-lg font-semibold text-neutral-900 mb-3">Location Selection</h3>
				<div class="grid grid-cols-1 md:grid-cols-2 gap-4">
					<!-- State Selection -->
					<div class="space-y-2">
						<label for="state" class="block text-sm font-medium text-neutral-700">
							State
							<span class="text-error-500">*</span>
						</label>
						<select
							id="state"
							class="w-full px-3 py-2 border border-neutral-300 rounded-lg focus:ring-2 focus:ring-primary-500 focus:border-primary-500 transition-colors"
							value={selectedState || ''}
							on:change={handleStateChange}
						>
							<option value="">Select a state...</option>
							{#each mockStates as state}
								<option value={state.id}>{state.name}</option>
							{/each}
						</select>
					</div>

					<!-- County Selection -->
					<div class="space-y-2">
						<label for="county" class="block text-sm font-medium text-neutral-700">
							County
							<span class="text-error-500">*</span>
						</label>
						<select
							id="county"
							class="w-full px-3 py-2 border border-neutral-300 rounded-lg focus:ring-2 focus:ring-primary-500 focus:border-primary-500 transition-colors"
							class:opacity-50={!selectedState}
							class:cursor-not-allowed={!selectedState}
							value={selectedCounty || ''}
							on:change={handleCountyChange}
							disabled={!selectedState}
						>
							<option value="">Select a county...</option>
							{#each availableCounties as county}
								<option value={county.id}>{county.name}</option>
							{/each}
						</select>
						{#if !selectedState}
							<p class="text-xs text-neutral-500">Select a state first</p>
						{/if}
					</div>
				</div>
			</div>
		{/if}

		<!-- Advanced Options -->
		{#if showAdvanced}
			<div class="border-t border-neutral-200 pt-4 space-y-4">
				<h3 class="text-lg font-semibold text-neutral-900">Advanced Options</h3>
				
				<!-- Filter Status -->
				<div class="bg-neutral-50 rounded-lg p-4">
					<h4 class="text-sm font-medium text-neutral-700 mb-2">Filter Status</h4>
					<div class="space-y-2 text-sm">
						<div class="flex items-center justify-between">
							<span>Indicator:</span>
							<span class="flex items-center">
								{#if isIndicatorValid}
									<svg class="w-4 h-4 text-success-600 mr-1" fill="currentColor" viewBox="0 0 20 20">
										<path fill-rule="evenodd" d="M16.707 5.293a1 1 0 010 1.414l-8 8a1 1 0 01-1.414 0l-4-4a1 1 0 011.414-1.414L8 12.586l7.293-7.293a1 1 0 011.414 0z" clip-rule="evenodd" />
									</svg>
									Valid
								{:else}
									<svg class="w-4 h-4 text-error-600 mr-1" fill="currentColor" viewBox="0 0 20 20">
										<path fill-rule="evenodd" d="M4.293 4.293a1 1 0 011.414 0L10 8.586l4.293-4.293a1 1 0 111.414 1.414L11.414 10l4.293 4.293a1 1 0 01-1.414 1.414L10 11.414l-4.293 4.293a1 1 0 01-1.414-1.414L8.586 10 4.293 5.707a1 1 0 010-1.414z" clip-rule="evenodd" />
									</svg>
									Required
								{/if}
							</span>
						</div>
						<div class="flex items-center justify-between">
							<span>Geography:</span>
							<span class="flex items-center">
								{#if isGeoLevelValid}
									<svg class="w-4 h-4 text-success-600 mr-1" fill="currentColor" viewBox="0 0 20 20">
										<path fill-rule="evenodd" d="M16.707 5.293a1 1 0 010 1.414l-8 8a1 1 0 01-1.414 0l-4-4a1 1 0 011.414-1.414L8 12.586l7.293-7.293a1 1 0 011.414 0z" clip-rule="evenodd" />
									</svg>
									Valid
								{:else}
									<svg class="w-4 h-4 text-error-600 mr-1" fill="currentColor" viewBox="0 0 20 20">
										<path fill-rule="evenodd" d="M4.293 4.293a1 1 0 011.414 0L10 8.586l4.293-4.293a1 1 0 111.414 1.414L11.414 10l4.293 4.293a1 1 0 01-1.414 1.414L10 11.414l-4.293 4.293a1 1 0 01-1.414-1.414L8.586 10 4.293 5.707a1 1 0 010-1.414z" clip-rule="evenodd" />
									</svg>
									Required
								{/if}
							</span>
						</div>
						<div class="flex items-center justify-between">
							<span>Year:</span>
							<span class="flex items-center">
								{#if isYearValid}
									<svg class="w-4 h-4 text-success-600 mr-1" fill="currentColor" viewBox="0 0 20 20">
										<path fill-rule="evenodd" d="M16.707 5.293a1 1 0 010 1.414l-8 8a1 1 0 01-1.414 0l-4-4a1 1 0 011.414-1.414L8 12.586l7.293-7.293a1 1 0 011.414 0z" clip-rule="evenodd" />
									</svg>
									Valid
								{:else}
									<svg class="w-4 h-4 text-error-600 mr-1" fill="currentColor" viewBox="0 0 20 20">
										<path fill-rule="evenodd" d="M4.293 4.293a1 1 0 011.414 0L10 8.586l4.293-4.293a1 1 0 111.414 1.414L11.414 10l4.293 4.293a1 1 0 01-1.414 1.414L10 11.414l-4.293 4.293a1 1 0 01-1.414-1.414L8.586 10 4.293 5.707a1 1 0 010-1.414z" clip-rule="evenodd" />
									</svg>
									Required
								{/if}
							</span>
						</div>
						{#if requiresStateCounty}
							<div class="flex items-center justify-between">
								<span>Location:</span>
								<span class="flex items-center">
									{#if isLocationValid}
										<svg class="w-4 h-4 text-success-600 mr-1" fill="currentColor" viewBox="0 0 20 20">
											<path fill-rule="evenodd" d="M16.707 5.293a1 1 0 010 1.414l-8 8a1 1 0 01-1.414 0l-4-4a1 1 0 011.414-1.414L8 12.586l7.293-7.293a1 1 0 011.414 0z" clip-rule="evenodd" />
										</svg>
										Valid
									{:else}
										<svg class="w-4 h-4 text-error-600 mr-1" fill="currentColor" viewBox="0 0 20 20">
											<path fill-rule="evenodd" d="M4.293 4.293a1 1 0 011.414 0L10 8.586l4.293-4.293a1 1 0 111.414 1.414L11.414 10l4.293 4.293a1 1 0 01-1.414 1.414L10 11.414l-4.293 4.293a1 1 0 01-1.414-1.414L8.586 10 4.293 5.707a1 1 0 010-1.414z" clip-rule="evenodd" />
										</svg>
										Required
									{/if}
								</span>
							</div>
						{/if}
					</div>
				</div>
			</div>
		{/if}

		<!-- Load Button -->
		<div class="flex items-center justify-between pt-4 border-t border-neutral-200">
			<div class="text-sm text-neutral-600">
				{#if canLoad}
					<span class="text-success-600 font-medium">Ready to load data</span>
				{:else if $metadataLoading}
					<span class="text-warning-600">Loading metadata...</span>
				{:else}
					<span class="text-error-600">Please complete all required fields</span>
				{/if}
			</div>
			<Button
				variant="primary"
				size="lg"
				disabled={!canLoad}
				loading={$metadataLoading}
				on:click={handleLoad}
			>
				{#if $metadataLoading}
					Loading...
				{:else}
					Load Data
				{/if}
			</Button>
		</div>
	</div>
</Card>
