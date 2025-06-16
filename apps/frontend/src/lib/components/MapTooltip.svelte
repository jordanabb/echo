<script lang="ts">
	import { createEventDispatcher } from 'svelte';
	import { fade, fly } from 'svelte/transition';
	import { quintOut } from 'svelte/easing';
	import { indicators, type IndicatorMetadata } from '$lib/stores/metadata';
	import { currentGeoLevel } from '$lib/stores/unifiedFilters';
	import { getStateNameByCode } from '$lib/constants/states';
	import { formatValueByType } from '$lib/utils';

	// Props
	export let feature: any = null;
	export let position: { x: number; y: number } = { x: 0, y: 0 };
	export let isVisible: boolean = false;
	export let isHover: boolean = false; // true for hover tooltip, false for click tooltip
	export let currentIndicatorId: string | null = null;
	export let currentYear: number | null = null;

	const dispatch = createEventDispatcher();

	// Get current indicator metadata
	$: currentIndicator = currentIndicatorId 
		? $indicators.find(ind => ind.id === currentIndicatorId) 
		: null;

	// Format value with appropriate precision and units using standardized formatting
	function formatValue(value: number | null, indicator: IndicatorMetadata | null): string {
		if (value === null || value === undefined) {
			return 'No data';
		}

		// Use the standardized formatting function
		const indicatorId = indicator?.id || '';
		const indicatorName = indicator?.name || '';
		
		return formatValueByType(value, indicatorId, indicatorName);
	}

	// Get geography type display name
	function getGeoTypeDisplayName(geoLevel: string | null): string {
		const geoTypeMap: Record<string, string> = {
			'county': 'County',
			'tract': 'Census Tract',
			'school_district': 'School District',
			'sldl': 'State Legislative District (Lower)',
			'sldu': 'State Legislative District (Upper)'
		};
		
		return geoLevel ? (geoTypeMap[geoLevel] || geoLevel) : 'Area';
	}

	// Extract state name from geo_id
	function getStateName(geoId: string): string | null {
		if (!geoId || geoId.length < 2) return null;
		
		// Extract the first 2 digits (state FIPS code)
		const stateFips = geoId.substring(0, 2);
		return getStateNameByCode(stateFips);
	}

	// Format the full geographic name with state
	function formatGeographicName(feature: any): string {
		const baseName = feature.properties.name || feature.properties.geo_name || 
						`${getGeoTypeDisplayName($currentGeoLevel)} ${feature.properties.geo_id}`;
		
		const stateName = getStateName(feature.properties.geo_id);
		
		if (stateName) {
			return `${baseName}, ${stateName}`;
		}
		
		return baseName;
	}

	// Close tooltip
	function closeTooltip() {
		dispatch('close');
	}

	// Handle click outside to close (for click tooltips)
	function handleClickOutside(event: MouseEvent) {
		if (!isHover && isVisible) {
			const target = event.target as HTMLElement;
			const tooltip = document.querySelector('.map-tooltip');
			if (tooltip && !tooltip.contains(target)) {
				closeTooltip();
			}
		}
	}

	// Add click outside listener for click tooltips
	$: if (typeof window !== 'undefined') {
		if (!isHover && isVisible) {
			document.addEventListener('click', handleClickOutside);
		} else {
			document.removeEventListener('click', handleClickOutside);
		}
	}
</script>

<svelte:window on:click={handleClickOutside} />

{#if isVisible && feature}
	<div 
		class="map-tooltip fixed z-50 pointer-events-none"
		class:pointer-events-auto={!isHover}
		style="left: {position.x}px; top: {position.y}px; transform: translate(-50%, -100%);"
		in:fly={{ y: 10, duration: 200, easing: quintOut }}
		out:fade={{ duration: 150 }}
	>
		<div 
			class="bg-white rounded-lg shadow-lg border border-gray-200 max-w-sm"
			class:shadow-xl={!isHover}
			class:border-gray-300={!isHover}
		>
			<!-- Header -->
			<div class="px-4 py-3 border-b border-gray-100">
				<div class="flex items-start justify-between">
					<div class="flex-1">
						<h3 class="font-semibold text-gray-900 text-sm leading-tight">
							{formatGeographicName(feature)}
						</h3>
						<p class="text-xs text-gray-500 mt-1">
							{getGeoTypeDisplayName($currentGeoLevel)} • ID: {feature.properties.geo_id}
						</p>
					</div>
					
					{#if !isHover}
						<button 
							class="ml-2 text-gray-400 hover:text-gray-600 transition-colors pointer-events-auto"
							on:click={closeTooltip}
							aria-label="Close tooltip"
						>
							<svg class="w-4 h-4" fill="none" stroke="currentColor" viewBox="0 0 24 24">
								<path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M6 18L18 6M6 6l12 12" />
							</svg>
						</button>
					{/if}
				</div>
			</div>

			<!-- Content -->
			<div class="px-4 py-3">
				{#if currentIndicator}
					<!-- Primary indicator value -->
					<div class="mb-3">
						<div class="flex items-center justify-between mb-1">
							<span class="text-sm font-medium text-gray-700">
								{currentIndicator.name}
							</span>
							{#if currentYear}
								<span class="text-xs text-gray-500">
									{currentYear}
								</span>
							{/if}
						</div>
						
						<div class="text-lg font-semibold text-gray-900">
							{formatValue(feature.properties.value, currentIndicator)}
						</div>
						
						{#if feature.properties.bin !== undefined && feature.properties.bin >= 0}
							<div class="text-xs text-gray-500 mt-1">
								Quintile {feature.properties.bin + 1} of 5
							</div>
						{/if}
					</div>

					<!-- Indicator description (for click tooltips) -->
					{#if !isHover && currentIndicator.description}
						<div class="mb-3 pb-3 border-b border-gray-100">
							<p class="text-xs text-gray-600 leading-relaxed">
								{currentIndicator.description}
							</p>
						</div>
					{/if}
				{:else}
					<!-- No indicator selected -->
					<div class="text-sm text-gray-500">
						No indicator data available
					</div>
				{/if}

				<!-- Additional metadata (for click tooltips) -->
				{#if !isHover}
					<div class="space-y-2">
						{#if currentIndicator?.theme}
							<div class="flex items-center justify-between text-xs">
								<span class="text-gray-500">Theme:</span>
								<span class="text-gray-700 font-medium">{currentIndicator.theme}</span>
							</div>
						{/if}
						
						{#if feature.properties.value !== null && feature.properties.value !== undefined}
							<div class="flex items-center justify-between text-xs">
								<span class="text-gray-500">Raw Value:</span>
								<span class="text-gray-700 font-mono">{feature.properties.value}</span>
							</div>
						{/if}
					</div>
				{/if}
			</div>

			<!-- Footer for click tooltips -->
			{#if !isHover}
				<div class="px-4 py-2 bg-gray-50 rounded-b-lg border-t border-gray-100">
					<p class="text-xs text-gray-500 text-center">
						Click elsewhere to close
					</p>
				</div>
			{/if}
		</div>

		<!-- Tooltip arrow -->
		<div class="absolute top-full left-1/2 transform -translate-x-1/2">
			<div class="w-0 h-0 border-l-4 border-r-4 border-t-4 border-transparent border-t-white"></div>
			<div class="w-0 h-0 border-l-4 border-r-4 border-t-4 border-transparent border-t-gray-200 absolute top-0 left-1/2 transform -translate-x-1/2 translate-y-px"></div>
		</div>
	</div>
{/if}

<style>
	.map-tooltip {
		z-index: 1000;
	}
</style>
