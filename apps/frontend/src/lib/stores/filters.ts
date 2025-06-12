import { writable, derived, get, type Writable, type Readable } from 'svelte/store';
import { page } from '$app/stores';
import { goto } from '$app/navigation';
import { browser } from '$app/environment';
import { latestYear, indicators, geographies } from './metadata';

// Types for filter state
export interface FilterState {
	indicator: string | null;
	geoLevel: string | null;
	year: number | null;
}

// Default values - these will be applied when no URL parameters are present
const DEFAULT_FILTERS: FilterState = {
	indicator: 'total_population', // Default to total population
	geoLevel: 'county', // Default to US counties
	year: 2022 // Default to 2022
};

// Internal store for filter state
const filtersStore: Writable<FilterState> = writable({ ...DEFAULT_FILTERS });

// Store to track if filters have been initialized
const filtersInitialized: Writable<boolean> = writable(false);

/**
 * Parses URL search parameters into filter state
 */
function parseUrlParams(searchParams: URLSearchParams): FilterState {
	const indicator = searchParams.get('indicator');
	const geoLevel = searchParams.get('geoLevel') || searchParams.get('geo_level'); // Support both formats
	const yearParam = searchParams.get('year');
	const year = yearParam ? parseInt(yearParam, 10) : null;

	return {
		indicator,
		geoLevel,
		year: isNaN(year as number) ? null : year
	};
}

/**
 * Converts filter state to URL search parameters
 */
function filtersToUrlParams(filters: FilterState): URLSearchParams {
	const params = new URLSearchParams();
	
	if (filters.indicator) {
		params.set('indicator', filters.indicator);
	}
	
	if (filters.geoLevel) {
		params.set('geoLevel', filters.geoLevel);
	}
	
	if (filters.year) {
		params.set('year', filters.year.toString());
	}
	
	return params;
}

/**
 * Updates the URL with current filter state
 */
async function updateUrl(filters: FilterState, replaceState = false): Promise<void> {
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
	const $indicators = get(indicators);
	const $geographies = get(geographies);
	
	// Use the latest year if available
	const defaultYear = $latestYear || DEFAULT_FILTERS.year;
	
	// Validate that default indicator exists
	let defaultIndicator = DEFAULT_FILTERS.indicator;
	if ($indicators.length > 0 && !$indicators.find(ind => ind.id === defaultIndicator)) {
		defaultIndicator = $indicators[0].id;
	}
	
	// Validate that default geography level exists
	let defaultGeoLevel = DEFAULT_FILTERS.geoLevel;
	if (Object.keys($geographies).length > 0 && !$geographies[defaultGeoLevel as string]) {
		defaultGeoLevel = Object.keys($geographies)[0];
	}
	
	const defaultFilters: FilterState = {
		indicator: defaultIndicator,
		geoLevel: defaultGeoLevel,
		year: defaultYear
	};
	
	filtersStore.set(defaultFilters);
	updateUrl(defaultFilters, true); // Replace state for default application
}

/**
 * Initializes filters from URL or applies defaults
 */
function initializeFilters(): void {
	if (!browser) return;
	
	const $page = get(page);
	const urlFilters = parseUrlParams($page.url.searchParams);
	
	// Check if any filters are present in URL
	const hasUrlFilters = urlFilters.indicator || urlFilters.geoLevel || urlFilters.year;
	
	if (hasUrlFilters) {
		// Use URL filters, but fill in missing values with defaults
		const $latestYear = get(latestYear);
		const mergedFilters: FilterState = {
			indicator: urlFilters.indicator || DEFAULT_FILTERS.indicator,
			geoLevel: urlFilters.geoLevel || DEFAULT_FILTERS.geoLevel,
			year: urlFilters.year || $latestYear || DEFAULT_FILTERS.year
		};
		
		filtersStore.set(mergedFilters);
		
		// Update URL if we filled in any missing values
		if (!urlFilters.indicator || !urlFilters.geoLevel || !urlFilters.year) {
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
async function updateFilter(key: keyof FilterState, value: string | number | null): Promise<void> {
	const currentFilters = get(filtersStore);
	const newFilters = { ...currentFilters, [key]: value };
	
	filtersStore.set(newFilters);
	await updateUrl(newFilters);
}

/**
 * Updates multiple filters at once
 */
async function updateFilters(updates: Partial<FilterState>): Promise<void> {
	const currentFilters = get(filtersStore);
	const newFilters = { ...currentFilters, ...updates };
	
	filtersStore.set(newFilters);
	await updateUrl(newFilters);
}

/**
 * Resets filters to defaults
 */
async function resetFilters(): Promise<void> {
	applyDefaultFilters();
}

// Reactive store that automatically syncs with URL changes
const filters: Readable<FilterState> = derived(
	[filtersStore, page],
	([$filtersStore, $page]) => {
		// Only sync from URL if we're in the browser and filters are initialized
		if (browser && get(filtersInitialized)) {
			const urlFilters = parseUrlParams($page.url.searchParams);
			
			// Check if URL has changed from our current state
			const currentFilters = $filtersStore;
			const urlChanged = 
				urlFilters.indicator !== currentFilters.indicator ||
				urlFilters.geoLevel !== currentFilters.geoLevel ||
				urlFilters.year !== currentFilters.year;
			
			if (urlChanged) {
				// URL changed externally (e.g., browser back/forward), update our store
				const $latestYear = get(latestYear);
				const mergedFilters: FilterState = {
					indicator: urlFilters.indicator || DEFAULT_FILTERS.indicator,
					geoLevel: urlFilters.geoLevel || DEFAULT_FILTERS.geoLevel,
					year: urlFilters.year || $latestYear || DEFAULT_FILTERS.year
				};
				
				// Update store without triggering URL update (to avoid infinite loop)
				filtersStore.set(mergedFilters);
				return mergedFilters;
			}
		}
		
		return $filtersStore;
	}
);

// Derived stores for individual filter values
const currentIndicator: Readable<string | null> = derived(filters, ($filters) => $filters.indicator);
const currentGeoLevel: Readable<string | null> = derived(filters, ($filters) => $filters.geoLevel);
const currentYear: Readable<number | null> = derived(filters, ($filters) => $filters.year);

// Derived store for URL state
const currentUrl: Readable<string> = derived(filters, ($filters) => {
	if (!browser) return '';
	const params = filtersToUrlParams($filters);
	return `${window.location.pathname}?${params.toString()}`;
});

// Function to check if filters are valid
const areFiltersValid: Readable<boolean> = derived(
	[filters, indicators, geographies],
	([$filters, $indicators, $geographies]) => {
		if (!$filters.indicator || !$filters.geoLevel || !$filters.year) {
			return false;
		}
		
		// Check if indicator exists
		const indicatorExists = $indicators.some(ind => ind.id === $filters.indicator);
		if (!indicatorExists) return false;
		
		// Check if geography level exists
		const geoLevelExists = Object.keys($geographies).includes($filters.geoLevel);
		if (!geoLevelExists) return false;
		
		// Check if year is available for the indicator
		const indicator = $indicators.find(ind => ind.id === $filters.indicator);
		const yearAvailable = indicator?.available_years.includes($filters.year) || false;
		
		return yearAvailable;
	}
);

export {
	// Main filter store
	filters,
	filtersInitialized,
	
	// Individual filter stores
	currentIndicator,
	currentGeoLevel,
	currentYear,
	
	// Derived stores
	currentUrl,
	areFiltersValid,
	
	// Functions
	initializeFilters,
	updateFilter,
	updateFilters,
	resetFilters,
	applyDefaultFilters,
	
	// Constants
	DEFAULT_FILTERS
};
