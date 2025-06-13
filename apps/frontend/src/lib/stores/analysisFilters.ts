import { writable, derived, get, type Writable, type Readable } from 'svelte/store';
import { indicators, type IndicatorMetadata } from './metadata';

// Types for analysis filter state
export interface AnalysisFilterState {
	indicatorIds: string[];
	geoLevel: string | null;
	years: number[];
}

// Default values for analysis filters
const DEFAULT_ANALYSIS_FILTERS: AnalysisFilterState = {
	indicatorIds: [],
	geoLevel: 'county',
	years: [2022]
};

// Internal store for analysis filter state
const analysisFiltersStore: Writable<AnalysisFilterState> = writable({ ...DEFAULT_ANALYSIS_FILTERS });

/**
 * Updates the selected indicator IDs
 */
function updateIndicatorIds(indicatorIds: string[]): void {
	const currentFilters = get(analysisFiltersStore);
	analysisFiltersStore.set({ ...currentFilters, indicatorIds });
}

/**
 * Adds an indicator to the selection
 */
function addIndicator(indicatorId: string): void {
	const currentFilters = get(analysisFiltersStore);
	if (!currentFilters.indicatorIds.includes(indicatorId)) {
		const newIndicatorIds = [...currentFilters.indicatorIds, indicatorId];
		analysisFiltersStore.set({ ...currentFilters, indicatorIds: newIndicatorIds });
	}
}

/**
 * Removes an indicator from the selection
 */
function removeIndicator(indicatorId: string): void {
	const currentFilters = get(analysisFiltersStore);
	const newIndicatorIds = currentFilters.indicatorIds.filter(id => id !== indicatorId);
	analysisFiltersStore.set({ ...currentFilters, indicatorIds: newIndicatorIds });
}

/**
 * Toggles an indicator in the selection
 */
function toggleIndicator(indicatorId: string): void {
	const currentFilters = get(analysisFiltersStore);
	if (currentFilters.indicatorIds.includes(indicatorId)) {
		removeIndicator(indicatorId);
	} else {
		addIndicator(indicatorId);
	}
}

/**
 * Updates the geography level
 */
function updateGeoLevel(geoLevel: string): void {
	const currentFilters = get(analysisFiltersStore);
	analysisFiltersStore.set({ ...currentFilters, geoLevel });
}

/**
 * Updates the selected years
 */
function updateYears(years: number[]): void {
	const currentFilters = get(analysisFiltersStore);
	analysisFiltersStore.set({ ...currentFilters, years });
}

/**
 * Clears all selected indicators
 */
function clearIndicators(): void {
	updateIndicatorIds([]);
}

/**
 * Resets all analysis filters to defaults
 */
function resetAnalysisFilters(): void {
	analysisFiltersStore.set({ ...DEFAULT_ANALYSIS_FILTERS });
}

// Derived store for selected indicators with metadata
const selectedIndicators: Readable<IndicatorMetadata[]> = derived(
	[analysisFiltersStore, indicators],
	([$analysisFilters, $indicators]) => {
		return $analysisFilters.indicatorIds
			.map(id => $indicators.find(indicator => indicator.id === id))
			.filter((indicator): indicator is IndicatorMetadata => indicator !== undefined);
	}
);

// Derived store for selected indicator count
const selectedIndicatorCount: Readable<number> = derived(
	analysisFiltersStore,
	($analysisFilters) => $analysisFilters.indicatorIds.length
);

// Derived store to check if an indicator is selected
const isIndicatorSelected = derived(analysisFiltersStore, ($analysisFilters) => 
	(indicatorId: string) => $analysisFilters.indicatorIds.includes(indicatorId)
);

// Derived store for available years across selected indicators
const availableYearsForSelection: Readable<number[]> = derived(
	selectedIndicators,
	($selectedIndicators) => {
		if ($selectedIndicators.length === 0) return [];
		
		// Find intersection of available years across all selected indicators
		const yearSets = $selectedIndicators.map(indicator => new Set(indicator.available_years));
		
		if (yearSets.length === 1) {
			return Array.from(yearSets[0]).sort((a, b) => b - a);
		}
		
		// Find intersection of all year sets
		const intersection = Array.from(yearSets[0]).filter(year =>
			yearSets.every(yearSet => yearSet.has(year))
		);
		
		return intersection.sort((a, b) => b - a);
	}
);

// Derived store to check if current selection is valid for analysis
const isAnalysisReady: Readable<boolean> = derived(
	[analysisFiltersStore, selectedIndicators],
	([$analysisFilters, $selectedIndicators]) => {
		return (
			$analysisFilters.indicatorIds.length > 0 &&
			$analysisFilters.geoLevel !== null &&
			$analysisFilters.years.length > 0 &&
			$selectedIndicators.length === $analysisFilters.indicatorIds.length // All selected IDs have valid metadata
		);
	}
);

export {
	// Main analysis filters store
	analysisFiltersStore as analysisFilters,
	
	// Derived stores
	selectedIndicators,
	selectedIndicatorCount,
	availableYearsForSelection,
	isAnalysisReady,
	
	// Functions
	updateIndicatorIds,
	addIndicator,
	removeIndicator,
	toggleIndicator,
	updateGeoLevel,
	updateYears,
	clearIndicators,
	resetAnalysisFilters,
	isIndicatorSelected,
	
	// Constants
	DEFAULT_ANALYSIS_FILTERS
};
