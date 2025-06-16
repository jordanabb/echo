<script lang="ts">
	import { createEventDispatcher } from 'svelte';
	import { 
		currentYears,
		currentSelectedIndicators,
		currentMapDisplayYear,
		currentMapDisplayIndicator,
		selectedIndicatorsWithMetadata
	} from '$lib/stores/unifiedFilters';

	// Event dispatcher for control changes
	const dispatch = createEventDispatcher<{
		yearChange: { year: number };
		indicatorChange: { indicatorId: string };
	}>();

	// Local state for current display values
	export let displayYear: number | null = null;
	export let displayIndicator: string | null = null;

	// Reactive variables
	$: showYearControls = $currentYears.length > 1;
	$: showIndicatorControls = $currentSelectedIndicators.length > 1;
	$: shouldShow = showYearControls || showIndicatorControls;

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
</script>

{#if shouldShow}
	<div class="absolute top-4 right-4 z-20 bg-white bg-opacity-90 backdrop-blur-sm rounded-lg shadow-lg border border-gray-200 p-2">
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
						{@const isActive = displayIndicator === indicatorId}
						{@const displayName = getIndicatorDisplayName(indicatorId)}
						<button
							class="block px-2 py-1 text-xs rounded border text-left transition-colors whitespace-nowrap {isActive ? 'bg-teal-600 text-white border-teal-600' : 'bg-white text-gray-700 border-gray-300 hover:bg-gray-50'}"
							on:click={() => selectIndicator(indicatorId)}
							title={displayName}
						>
							{truncateIndicatorName(displayName, 25)}
						</button>
					{/each}
				</div>
			</div>
		{/if}
	</div>
{/if}
