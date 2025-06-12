import { writable, derived, type Writable, type Readable } from 'svelte/store';

// Types for the metadata structure
export interface IndicatorMetadata {
	id: string;
	name: string;
	theme: string;
	description: string;
	available_years: number[];
}

export interface GeographyLevel {
	name: string;
	sublevels: string[];
}

export interface MetadataResponse {
	indicators: IndicatorMetadata[];
	geographies: Record<string, GeographyLevel>;
}

// Store for the raw metadata response
const metadataStore: Writable<MetadataResponse | null> = writable(null);

// Store for loading state
const metadataLoading: Writable<boolean> = writable(false);

// Store for error state
const metadataError: Writable<string | null> = writable(null);

/**
 * Fetches metadata from the API endpoint
 */
async function fetchMetadata(): Promise<void> {
	metadataLoading.set(true);
	metadataError.set(null);
	
	try {
		const response = await fetch('/api/metadata');
		
		if (!response.ok) {
			throw new Error(`Failed to fetch metadata: ${response.status} ${response.statusText}`);
		}
		
		const data: MetadataResponse = await response.json();
		metadataStore.set(data);
	} catch (error) {
		console.error('Error fetching metadata:', error);
		const errorMessage = error instanceof Error ? error.message : 'Unknown error occurred';
		metadataError.set(errorMessage);
	} finally {
		metadataLoading.set(false);
	}
}

// Derived stores for easy access to specific parts of metadata
const indicators: Readable<IndicatorMetadata[]> = derived(metadataStore, ($metadata) => {
	return $metadata?.indicators || [];
});

const geographies: Readable<Record<string, GeographyLevel>> = derived(metadataStore, ($metadata) => {
	return $metadata?.geographies || {};
});

// Derived store to get indicators grouped by theme
const indicatorsByTheme: Readable<Record<string, IndicatorMetadata[]>> = derived(indicators, ($indicators) => {
	const grouped: Record<string, IndicatorMetadata[]> = {};
	$indicators.forEach((indicator: IndicatorMetadata) => {
		if (!grouped[indicator.theme]) {
			grouped[indicator.theme] = [];
		}
		grouped[indicator.theme].push(indicator);
	});
	return grouped;
});

// Derived store to get all available years across all indicators
const allAvailableYears: Readable<number[]> = derived(indicators, ($indicators) => {
	const years = new Set<number>();
	$indicators.forEach((indicator: IndicatorMetadata) => {
		indicator.available_years.forEach((year: number) => years.add(year));
	});
	return Array.from(years).sort((a, b) => b - a); // Sort descending (newest first)
});

// Derived store to get the latest year available
const latestYear: Readable<number | null> = derived(allAvailableYears, ($years) => {
	return $years.length > 0 ? $years[0] : null;
});

// Function to get indicator by ID
function getIndicatorById(id: string): IndicatorMetadata | null {
	let indicator: IndicatorMetadata | null = null;
	const unsubscribe = indicators.subscribe(($indicators) => {
		indicator = $indicators.find((ind: IndicatorMetadata) => ind.id === id) || null;
	});
	unsubscribe();
	return indicator;
}

// Function to get available years for a specific indicator
function getAvailableYearsForIndicator(indicatorId: string): number[] {
	const indicator = getIndicatorById(indicatorId);
	return indicator ? indicator.available_years : [];
}

// Initialize metadata fetch on module load
let initialized = false;

function initializeMetadata(): void {
	if (!initialized) {
		initialized = true;
		fetchMetadata();
	}
}

export {
	// Core stores
	metadataStore as metadata,
	metadataLoading,
	metadataError,
	
	// Derived stores
	indicators,
	geographies,
	indicatorsByTheme,
	allAvailableYears,
	latestYear,
	
	// Functions
	fetchMetadata,
	getIndicatorById,
	getAvailableYearsForIndicator,
	initializeMetadata
};
