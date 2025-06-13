import { writable, derived, type Writable, type Readable } from 'svelte/store';
import { currentGeoLevel, currentSelectedIndicators, selectedIndicatorCount } from './unifiedFilters';

// Types for view selection
export type ViewType = 'map' | 'table' | 'chart';

// Store for variable selector modal state (shared between UnifiedContextBar and Step 2)
export const showVariableSelector: Writable<boolean> = writable(false);

// Store for selected view type
export const selectedView: Writable<ViewType | null> = writable(null);

// Derived store to check if all steps are completed
export const allStepsCompleted: Readable<boolean> = derived(
	[currentGeoLevel, selectedIndicatorCount, selectedView],
	([$currentGeoLevel, $selectedIndicatorCount, $selectedView]) => {
		return (
			$currentGeoLevel !== null &&
			$selectedIndicatorCount > 0 &&
			$selectedView !== null
		);
	}
);

// Derived store to check individual step completion
export const stepCompletion: Readable<{
	step1: boolean;
	step2: boolean;
	step3: boolean;
}> = derived(
	[currentGeoLevel, selectedIndicatorCount, selectedView],
	([$currentGeoLevel, $selectedIndicatorCount, $selectedView]) => ({
		step1: $currentGeoLevel !== null,
		step2: $selectedIndicatorCount > 0,
		step3: $selectedView !== null
	})
);

// Function to navigate to the appropriate section based on selected view
export function navigateToView(view: ViewType): void {
	switch (view) {
		case 'map':
			const mapSection = document.getElementById('map-section');
			if (mapSection) {
				mapSection.scrollIntoView({ behavior: 'smooth' });
			}
			break;
		case 'table':
		case 'chart':
			const analysisSection = document.getElementById('analysis-section');
			if (analysisSection) {
				analysisSection.scrollIntoView({ behavior: 'smooth' });
			}
			// Set the appropriate tab in AnalysisPane
			// This will be handled by the AnalysisPane component
			break;
	}
}

// Function to handle view selection and auto-navigation
export function selectView(view: ViewType): void {
	selectedView.set(view);
	
	// Auto-navigate if all steps are completed
	setTimeout(() => {
		navigateToView(view);
	}, 300); // Small delay for smooth UX
}
