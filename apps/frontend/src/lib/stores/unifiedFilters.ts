import { writable, derived, get, type Writable, type Readable } from 'svelte/store';
import { page } from '$app/stores';
import { goto } from '$app/navigation';
import { browser } from '$app/environment';
import { latestYear, indicators, geographies, type IndicatorMetadata } from './metadata';

// Types for unified filter state
export interface UnifiedFilterState {
	// Geographic context (applies to all views)
	geoLevel: string | null;
	geoFilter: string[]; // selected state FIPS codes (empty = all states)
	
	// Temporal context
	years: number[]; // Support both single year and ranges
	primaryYear: number | null; // Main year for single-year views
	
	// Variable context
	primaryIndicator: string | null; // For map/single-variable views
	selectedIndicators: string[]; // For analysis/multi-variable views
	
	// View-specific overrides (optional)
	viewOverrides: {
		map?: Partial<UnifiedFilterState>;
		table?: Partial<UnifiedFilterState>;
		chart?: Partial<UnifiedFilterState>;
	};
}

// Default values
const DEFAULT_UNIFIED_FILTERS: UnifiedFilterState = {
	geoLevel: 'county',
	geoFilter: [],
	years: [2022],
	primaryYear: 2022,
	primaryIndicator: null, // No default indicator - only show selected variables
	selectedIndicators: [],
	viewOverrides: {}
};

// Internal store for unified filter state
const unifiedFiltersStore: Writable<UnifiedFilterState> = writable({ ...DEFAULT_UNIFIED_FILTERS });

// Store to track if filters have been initialized
const filtersInitialized: Writable<boolean> = writable(false);

/**
 * Parses URL search parameters into unified filter state
 */
function parseUrlParams(searchParams: URLSearchParams): Partial<UnifiedFilterState> {
	const geoLevel = searchParams.get('geoLevel') || searchParams.get('geo_level');
	const geoFilterParam = searchParams.get('geoFilter') || searchParams.get('geo_filter');
	const geoFilter = geoFilterParam ? geoFilterParam.split(',').filter(s => s) : [];
	const primaryIndicator = searchParams.get('indicator');
	const yearParam = searchParams.get('year');
	const yearsParam = searchParams.get('years');
	const indicatorsParam = searchParams.get('indicators');
	
	const primaryYear = yearParam ? parseInt(yearParam, 10) : null;
	const years = yearsParam ? yearsParam.split(',').map(y => parseInt(y, 10)).filter(y => !isNaN(y)) : [];
	const selectedIndicators = indicatorsParam ? indicatorsParam.split(',') : [];
	
	return {
		geoLevel,
		geoFilter,
		primaryIndicator,
		primaryYear: isNaN(primaryYear as number) ? null : primaryYear,
		years: years.length > 0 ? years : (primaryYear ? [primaryYear] : []),
		selectedIndicators
	};
}

/**
 * Converts unified filter state to URL search parameters
 */
function filtersToUrlParams(filters: UnifiedFilterState): URLSearchParams {
	const params = new URLSearchParams();
	
	if (filters.geoLevel) {
		params.set('geoLevel', filters.geoLevel);
	}
	
	if (filters.geoFilter.length > 0) {
		params.set('geoFilter', filters.geoFilter.join(','));
	}
	
	if (filters.primaryIndicator) {
		params.set('indicator', filters.primaryIndicator);
	}
	
	if (filters.primaryYear) {
		params.set('year', filters.primaryYear.toString());
	}
	
	if (filters.years.length > 1 || (filters.years.length === 1 && filters.years[0] !== filters.primaryYear)) {
		params.set('years', filters.years.join(','));
	}
	
	if (filters.selectedIndicators.length > 0) {
		params.set('indicators', filters.selectedIndicators.join(','));
	}
	
	return params;
}

/**
 * Updates the URL with current filter state
 */
async function updateUrl(filters: UnifiedFilterState, replaceState = false): Promise<void> {
	if (!browser) return;
	
	const params = filtersToUrlParams(filters);
	const url = `${window.location.pathname}?${params.toString()}`;
	
	try {
		await goto(url, { 
			replaceState,
			keepFocus: true,
			noScroll: true
		});
	} catch (error) {
		console.error('Error updating URL:', error);
	}
}

/**
 * Applies default filters and updates URL
 */
function applyDefaultFilters(): void {
	const $latestYear = get(latestYear);
	const $geographies = get(geographies);
	
	// Use the latest year if available
	const defaultYear = $latestYear || DEFAULT_UNIFIED_FILTERS.primaryYear!;
	
	// Validate that default geography level exists
	let defaultGeoLevel = DEFAULT_UNIFIED_FILTERS.geoLevel;
	if (Object.keys($geographies).length > 0 && !$geographies[defaultGeoLevel as string]) {
		defaultGeoLevel = Object.keys($geographies)[0];
	}
	
	const defaultFilters: UnifiedFilterState = {
		...DEFAULT_UNIFIED_FILTERS,
		geoLevel: defaultGeoLevel,
		primaryIndicator: null, // No default indicator
		primaryYear: defaultYear,
		years: [defaultYear]
	};
	
	unifiedFiltersStore.set(defaultFilters);
	updateUrl(defaultFilters, true);
}

/**
 * Initializes filters from URL or applies defaults
 */
function initializeUnifiedFilters(): void {
	if (!browser) return;
	
	const $page = get(page);
	const urlFilters = parseUrlParams($page.url.searchParams);
	
	// Check if any filters are present in URL
	const hasUrlFilters = Object.values(urlFilters).some(value => 
		value !== null && value !== undefined && 
		(Array.isArray(value) ? value.length > 0 : true)
	);
	
	if (hasUrlFilters) {
		// Use URL filters, but fill in missing values with defaults
		const $latestYear = get(latestYear);
		const mergedFilters: UnifiedFilterState = {
			...DEFAULT_UNIFIED_FILTERS,
			...urlFilters,
			geoLevel: urlFilters.geoLevel || DEFAULT_UNIFIED_FILTERS.geoLevel,
			primaryIndicator: urlFilters.primaryIndicator || DEFAULT_UNIFIED_FILTERS.primaryIndicator,
			primaryYear: urlFilters.primaryYear || $latestYear || DEFAULT_UNIFIED_FILTERS.primaryYear,
			years: urlFilters.years && urlFilters.years.length > 0 ? urlFilters.years : [$latestYear || DEFAULT_UNIFIED_FILTERS.primaryYear!],
			selectedIndicators: urlFilters.selectedIndicators || []
		};
		
		unifiedFiltersStore.set(mergedFilters);
		
		// Update URL if we filled in any missing values
		if (!urlFilters.geoLevel || !urlFilters.primaryIndicator || !urlFilters.primaryYear) {
			updateUrl(mergedFilters, true);
		}
	} else {
		// No URL filters, apply defaults
		applyDefaultFilters();
	}
	
	filtersInitialized.set(true);
}

/**
 * Updates a specific filter and the URL
 */
async function updateFilter(key: keyof UnifiedFilterState, value: any): Promise<void> {
	const currentFilters = get(unifiedFiltersStore);
	const newFilters = { ...currentFilters, [key]: value };
	
	// Special handling for year updates
	if (key === 'primaryYear' && value) {
		newFilters.years = [value];
	}
	
	unifiedFiltersStore.set(newFilters);
	await updateUrl(newFilters);
}

/**
 * Updates multiple filters at once
 */
async function updateFilters(updates: Partial<UnifiedFilterState>): Promise<void> {
	const currentFilters = get(unifiedFiltersStore);
	const newFilters = { ...currentFilters, ...updates };
	
	// Special handling for year updates
	if (updates.primaryYear && !updates.years) {
		newFilters.years = [updates.primaryYear];
	}
	
	unifiedFiltersStore.set(newFilters);
	await updateUrl(newFilters);
}

/**
 * Adds an indicator to the selection
 */
async function addIndicator(indicatorId: string): Promise<void> {
	const currentFilters = get(unifiedFiltersStore);
	if (!currentFilters.selectedIndicators.includes(indicatorId)) {
		const newSelectedIndicators = [...currentFilters.selectedIndicators, indicatorId];
		await updateFilter('selectedIndicators', newSelectedIndicators);
	}
}

/**
 * Removes an indicator from the selection
 */
async function removeIndicator(indicatorId: string): Promise<void> {
	const currentFilters = get(unifiedFiltersStore);
	const newSelectedIndicators = currentFilters.selectedIndicators.filter(id => id !== indicatorId);
	await updateFilter('selectedIndicators', newSelectedIndicators);
}

/**
 * Toggles an indicator in the selection
 */
async function toggleIndicator(indicatorId: string): Promise<void> {
	const currentFilters = get(unifiedFiltersStore);
	if (currentFilters.selectedIndicators.includes(indicatorId)) {
		await removeIndicator(indicatorId);
	} else {
		await addIndicator(indicatorId);
	}
}

/**
 * Clears all selected indicators
 */
async function clearIndicators(): Promise<void> {
	await updateFilter('selectedIndicators', []);
}

/**
 * Adds a year to the selection
 */
async function addYear(year: number): Promise<void> {
	const currentFilters = get(unifiedFiltersStore);
	if (!currentFilters.years.includes(year)) {
		const newYears = [...currentFilters.years, year].sort((a, b) => a - b);
		await updateFilter('years', newYears);
		
		// Update primary year if not set or if this is the only year
		if (!currentFilters.primaryYear || newYears.length === 1) {
			await updateFilter('primaryYear', year);
		}
	}
}

/**
 * Removes a year from the selection
 */
async function removeYear(year: number): Promise<void> {
	const currentFilters = get(unifiedFiltersStore);
	const newYears = currentFilters.years.filter(y => y !== year);
	
	// Ensure at least one year is always selected
	if (newYears.length === 0) {
		const $latestYear = get(latestYear);
		const fallbackYear = $latestYear || DEFAULT_UNIFIED_FILTERS.primaryYear!;
		await updateFilters({
			years: [fallbackYear],
			primaryYear: fallbackYear
		});
	} else {
		await updateFilter('years', newYears);
		
		// Update primary year if the removed year was the primary year
		if (currentFilters.primaryYear === year) {
			const newPrimaryYear = Math.max(...newYears);
			await updateFilter('primaryYear', newPrimaryYear);
		}
	}
}

/**
 * Toggles a year in the selection
 */
async function toggleYear(year: number): Promise<void> {
	const currentFilters = get(unifiedFiltersStore);
	if (currentFilters.years.includes(year)) {
		await removeYear(year);
	} else {
		await addYear(year);
	}
}

/**
 * Sets the years array directly
 */
async function setYears(years: number[]): Promise<void> {
	// Ensure at least one year is provided
	if (years.length === 0) {
		const $latestYear = get(latestYear);
		years = [$latestYear || DEFAULT_UNIFIED_FILTERS.primaryYear!];
	}
	
	const sortedYears = [...years].sort((a, b) => a - b);
	const primaryYear = Math.max(...sortedYears);
	
	await updateFilters({
		years: sortedYears,
		primaryYear: primaryYear
	});
}

/**
 * Clears all years and sets to default
 */
async function clearYears(): Promise<void> {
	const $latestYear = get(latestYear);
	const defaultYear = $latestYear || DEFAULT_UNIFIED_FILTERS.primaryYear!;
	
	await updateFilters({
		years: [defaultYear],
		primaryYear: defaultYear
	});
}

/**
 * Resets filters to defaults
 */
async function resetFilters(): Promise<void> {
	applyDefaultFilters();
}

// Main unified filters store with URL synchronization
const unifiedFilters: Readable<UnifiedFilterState> = derived(
	[unifiedFiltersStore, page],
	([$unifiedFiltersStore, $page]) => {
		// Only sync from URL if we're in the browser and filters are initialized
		if (browser && get(filtersInitialized)) {
			const urlFilters = parseUrlParams($page.url.searchParams);
			
			// Check if URL has changed from our current state
			const currentFilters = $unifiedFiltersStore;
			const urlChanged = 
				urlFilters.geoLevel !== currentFilters.geoLevel ||
				urlFilters.primaryIndicator !== currentFilters.primaryIndicator ||
				urlFilters.primaryYear !== currentFilters.primaryYear ||
				JSON.stringify(urlFilters.selectedIndicators) !== JSON.stringify(currentFilters.selectedIndicators);
			
			if (urlChanged) {
				// URL changed externally, update our store
				const $latestYear = get(latestYear);
				const mergedFilters: UnifiedFilterState = {
					...currentFilters,
					...urlFilters,
					geoLevel: urlFilters.geoLevel || currentFilters.geoLevel,
					primaryIndicator: urlFilters.primaryIndicator || currentFilters.primaryIndicator,
					primaryYear: urlFilters.primaryYear || $latestYear || currentFilters.primaryYear,
					years: urlFilters.years && urlFilters.years.length > 0 ? urlFilters.years : currentFilters.years,
					selectedIndicators: urlFilters.selectedIndicators || []
				};
				
				unifiedFiltersStore.set(mergedFilters);
				return mergedFilters;
			}
		}
		
		return $unifiedFiltersStore;
	}
);

// Derived stores for individual filter values
const currentGeoLevel: Readable<string | null> = derived(unifiedFilters, ($filters) => $filters.geoLevel);
const currentGeoFilter: Readable<string[]> = derived(unifiedFilters, ($filters) => $filters.geoFilter);
const currentPrimaryIndicator: Readable<string | null> = derived(unifiedFilters, ($filters) => $filters.primaryIndicator);
const currentPrimaryYear: Readable<number | null> = derived(unifiedFilters, ($filters) => $filters.primaryYear);
const currentYears: Readable<number[]> = derived(unifiedFilters, ($filters) => $filters.years);
const currentSelectedIndicators: Readable<string[]> = derived(unifiedFilters, ($filters) => $filters.selectedIndicators);

// Map-specific display stores (separate from selection arrays)
const currentMapDisplayYear: Readable<number | null> = derived(
	[currentYears, currentPrimaryYear],
	([$years, $primaryYear]) => {
		// Use the most recent year from selected years, fallback to primary year
		if ($years.length > 0) {
			return Math.max(...$years);
		}
		return $primaryYear;
	}
);

const currentMapDisplayIndicator: Readable<string | null> = derived(
	[currentPrimaryIndicator, currentSelectedIndicators],
	([$primaryIndicator, $selectedIndicators]) => {
		// Use primary indicator if available, otherwise use first selected indicator
		if ($primaryIndicator) {
			return $primaryIndicator;
		} else if ($selectedIndicators && $selectedIndicators.length > 0) {
			return $selectedIndicators[0];
		}
		return null;
	}
);

// Derived store for selected indicators with metadata
const selectedIndicatorsWithMetadata: Readable<IndicatorMetadata[]> = derived(
	[currentSelectedIndicators, indicators],
	([$selectedIndicators, $indicators]) => {
		return $selectedIndicators
			.map(id => $indicators.find(indicator => indicator.id === id))
			.filter((indicator): indicator is IndicatorMetadata => indicator !== undefined);
	}
);

// Derived store for selected indicator count
const selectedIndicatorCount: Readable<number> = derived(
	currentSelectedIndicators,
	($selectedIndicators) => $selectedIndicators.length
);

// Derived store to check if an indicator is selected
const isIndicatorSelected = derived(currentSelectedIndicators, ($selectedIndicators) => 
	(indicatorId: string) => $selectedIndicators.includes(indicatorId)
);

// Derived store for URL state
const currentUrl: Readable<string> = derived(unifiedFilters, ($filters) => {
	if (!browser) return '';
	const params = filtersToUrlParams($filters);
	return `${window.location.pathname}?${params.toString()}`;
});

// Function to check if filters are valid
const areFiltersValid: Readable<boolean> = derived(
	[unifiedFilters, indicators, geographies, currentMapDisplayIndicator],
	([$filters, $indicators, $geographies, $mapDisplayIndicator]) => {
		if (!$filters.geoLevel || !$filters.primaryYear) {
			return false;
		}
		
		// Check if geography level exists
		const geoLevelExists = Object.keys($geographies).includes($filters.geoLevel);
		if (!geoLevelExists) return false;
		
		// Check if the indicator that will be displayed on the map is valid
		const indicatorToValidate = $mapDisplayIndicator || $filters.primaryIndicator;
		if (indicatorToValidate) {
			const indicatorExists = $indicators.some(ind => ind.id === indicatorToValidate);
			if (!indicatorExists) return false;
			
			// Check if year is available for the indicator
			const indicator = $indicators.find(ind => ind.id === indicatorToValidate);
			const yearAvailable = indicator?.available_years.includes($filters.primaryYear) || false;
			if (!yearAvailable) return false;
		}
		
		return true;
	}
);

// Check if analysis is ready (has selected indicators)
const isAnalysisReady: Readable<boolean> = derived(
	[unifiedFilters, selectedIndicatorsWithMetadata],
	([$filters, $selectedIndicators]) => {
		return (
			$filters.selectedIndicators.length > 0 &&
			$filters.geoLevel !== null &&
			$filters.years.length > 0 &&
			$selectedIndicators.length === $filters.selectedIndicators.length
		);
	}
);

// Generate plain English description of current selection
const currentSelectionDescription: Readable<string> = derived(
	[unifiedFilters, selectedIndicatorsWithMetadata, geographies, indicators],
	([$filters, $selectedIndicators, $geographies, $indicators]) => {
		// Helper function to get geography display name
		const getGeoDisplayName = (geoLevel: string | null): string => {
			if (!geoLevel) return 'areas';
			const geoData = $geographies[geoLevel];
			if (!geoData) return geoLevel;
			
			// Convert to plural and lowercase for natural language
			let name = geoData.name.toLowerCase();
			if (name.endsWith('y')) {
				name = name.slice(0, -1) + 'ies';
			} else if (!name.endsWith('s')) {
				name = name + 's';
			}
			return name;
		};

		// Helper function to get indicator display name
		const getIndicatorDisplayName = (indicatorId: string): string => {
			const indicator = $indicators.find(ind => ind.id === indicatorId);
			return indicator ? indicator.name.toLowerCase() : indicatorId.replace(/_/g, ' ');
		};

		// Build the description
		let description = '';

		// Geography part
		const geoName = getGeoDisplayName($filters.geoLevel);
		
		// Variable part
		if ($filters.primaryIndicator && $selectedIndicators.length === 0) {
			// Single indicator view (map)
			const indicatorName = getIndicatorDisplayName($filters.primaryIndicator);
			description = `${geoName} by ${indicatorName}`;
		} else if ($selectedIndicators.length === 1) {
			// Single selected indicator
			const indicatorName = $selectedIndicators[0].name.toLowerCase();
			description = `${geoName} by ${indicatorName}`;
		} else if ($selectedIndicators.length === 2) {
			// Two indicators
			const indicator1 = $selectedIndicators[0].name.toLowerCase();
			const indicator2 = $selectedIndicators[1].name.toLowerCase();
			description = `${geoName} by ${indicator1} and ${indicator2}`;
		} else if ($selectedIndicators.length > 2) {
			// Multiple indicators
			const firstIndicator = $selectedIndicators[0].name.toLowerCase();
			const remainingCount = $selectedIndicators.length - 1;
			description = `${geoName} by ${firstIndicator} and ${remainingCount} other indicator${remainingCount === 1 ? '' : 's'}`;
		} else {
			// No indicators selected
			description = `${geoName}`;
		}

		// Year part
		if ($filters.years.length === 1) {
			description += ` in ${$filters.years[0]}`;
		} else if ($filters.years.length === 2) {
			const sortedYears = [...$filters.years].sort((a, b) => a - b);
			description += ` in ${sortedYears[0]} and ${sortedYears[1]}`;
		} else if ($filters.years.length > 2) {
			const sortedYears = [...$filters.years].sort((a, b) => a - b);
			const yearRange = `${sortedYears[0]}-${sortedYears[sortedYears.length - 1]}`;
			description += ` from ${yearRange}`;
		}

		// Capitalize first letter
		return description.charAt(0).toUpperCase() + description.slice(1);
	}
);

export {
	// Main unified filters store
	unifiedFilters,
	filtersInitialized,
	
	// Individual filter stores
	currentGeoLevel,
	currentGeoFilter,
	currentPrimaryIndicator,
	currentPrimaryYear,
	currentYears,
	currentSelectedIndicators,
	
	// Map-specific display stores
	currentMapDisplayYear,
	currentMapDisplayIndicator,
	
	// Derived stores
	selectedIndicatorsWithMetadata,
	selectedIndicatorCount,
	isIndicatorSelected,
	currentUrl,
	areFiltersValid,
	isAnalysisReady,
	currentSelectionDescription,
	
	// Functions
	initializeUnifiedFilters,
	updateFilter,
	updateFilters,
	addIndicator,
	removeIndicator,
	toggleIndicator,
	clearIndicators,
	addYear,
	removeYear,
	toggleYear,
	setYears,
	clearYears,
	resetFilters,
	applyDefaultFilters,
	
	// Constants
	DEFAULT_UNIFIED_FILTERS
};
