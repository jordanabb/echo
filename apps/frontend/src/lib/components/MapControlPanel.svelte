<script lang="ts">
	import { createEventDispatcher } from 'svelte';
	import { 
		currentYears,
		currentSelectedIndicators,
		currentMapDisplayYear,
		currentMapDisplayIndicator,
		selectedIndicatorsWithMetadata
	} from '$lib/stores/unifiedFilters';
	import type { IndicatorMetadata } from '$lib/stores/metadata';

	// Event dispatcher for control changes
	const dispatch = createEventDispatcher<{
		yearChange: { year: number };
		indicatorChange: { indicatorId: string };
		saveMap: void;
	}>();

	// Local state for current display values
	export let displayYear: number | null = null;
	export let displayIndicator: string | null = null;

	// Reactive variables
	$: showYearControls = $currentYears.length > 1;
	$: showIndicatorControls = $currentSelectedIndicators.length > 1;
	$: shouldShow = showYearControls || showIndicatorControls;

	/**
	 * Checks if a variable is available for the current display year
	 */
	function isVariableAvailableForDisplayYear(indicator: IndicatorMetadata): boolean {
		if (!displayYear) return true;
		return indicator.available_years.includes(displayYear);
	}

	/**
	 * Handles year selection
	 */
	function selectYear(year: number): void {
		dispatch('yearChange', { year });
	}

	/**
	 * Handles indicator selection
	 */
	function selectIndicator(indicatorId: string): void {
		dispatch('indicatorChange', { indicatorId });
	}

	/**
	 * Gets indicator display name
	 */
	function getIndicatorDisplayName(indicatorId: string): string {
		const indicator = $selectedIndicatorsWithMetadata.find(ind => ind.id === indicatorId);
		return indicator ? indicator.name : indicatorId.replace(/_/g, ' ').replace(/\b\w/g, l => l.toUpperCase());
	}

	/**
	 * Truncates long indicator names for display
	 */
	function truncateIndicatorName(name: string, maxLength: number = 20): string {
		if (name.length <= maxLength) return name;
		return name.substring(0, maxLength - 3) + '...';
	}

	/**
	 * Handles save map action
	 */
	function handleSaveMap(): void {
		dispatch('saveMap');
	}
</script>

<!-- Always show the control panel if there are controls or we want to show the save button -->
<div class="absolute top-4 right-4 z-20 bg-white bg-opacity-90 backdrop-blur-sm rounded-lg shadow-lg border border-gray-200 p-2">
	<!-- Save Map Button -->
	<div class="mb-2">
		<button
			class="w-full px-3 py-2 text-xs font-medium bg-teal-600 text-white rounded border border-teal-600 hover:bg-teal-700 transition-colors flex items-center justify-center gap-1"
			on:click={handleSaveMap}
			title="Save current map view as PNG"
		>
			<svg class="w-3 h-3" fill="none" stroke="currentColor" viewBox="0 0 24 24">
				<path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M12 10v6m0 0l-3-3m3 3l3-3m2 8H7a2 2 0 01-2-2V5a2 2 0 012-2h5.586a1 1 0 01.707.293l5.414 5.414a1 1 0 01.293.707V19a2 2 0 01-2 2z" />
			</svg>
			Save Map
		</button>
	</div>

	{#if shouldShow}
		<!-- Year Controls -->
		{#if showYearControls}
			<div class="mb-2">
				<label class="block text-xs font-medium text-gray-700 mb-1">
					Year
				</label>
				<div class="flex flex-wrap gap-1">
					{#each $currentYears.sort((a, b) => a - b) as year}
						<button
							class="px-2 py-1 text-xs rounded border transition-colors {displayYear === year ? 'bg-teal-600 text-white border-teal-600' : 'bg-white text-gray-700 border-gray-300 hover:bg-gray-50'}"
							on:click={() => selectYear(year)}
							title="Show data for {year}"
						>
							{year}
						</button>
					{/each}
				</div>
			</div>
		{/if}

		<!-- Indicator Controls -->
		{#if showIndicatorControls}
			<div>
				<label class="block text-xs font-medium text-gray-700 mb-1">
					Variable
				</label>
				<div class="space-y-1">
					{#each $currentSelectedIndicators as indicatorId}
						{@const indicator = $selectedIndicatorsWithMetadata.find(ind => ind.id === indicatorId)}
						{@const isActive = displayIndicator === indicatorId}
						{@const displayName = getIndicatorDisplayName(indicatorId)}
						{@const isAvailable = indicator ? isVariableAvailableForDisplayYear(indicator) : true}
						<button
							class="block px-2 py-1 text-xs rounded border text-left transition-colors whitespace-nowrap relative {isActive && isAvailable ? 'bg-teal-600 text-white border-teal-600' : isAvailable ? 'bg-white text-gray-700 border-gray-300 hover:bg-gray-50' : 'bg-gray-100 text-gray-400 border-gray-200 cursor-not-allowed opacity-60'}"
							on:click={() => isAvailable && selectIndicator(indicatorId)}
							title={isAvailable ? displayName : `${displayName} - Not available for ${displayYear}`}
							disabled={!isAvailable}
						>
							<span class="flex items-center gap-1">
								{truncateIndicatorName(displayName, 25)}
								{#if !isAvailable}
									<svg class="w-3 h-3 text-gray-400" fill="none" stroke="currentColor" viewBox="0 0 24 24">
										<path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M12 8v4m0 4h.01M21 12a9 9 0 11-18 0 9 9 0 0118 0z" />
									</svg>
								{/if}
							</span>
						</button>
					{/each}
				</div>
			</div>
		{/if}
	{/if}
</div>
