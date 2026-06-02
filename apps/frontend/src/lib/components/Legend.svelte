<script lang="ts">
	import { fade } from 'svelte/transition';
	import { createEventDispatcher } from 'svelte';

	const dispatch = createEventDispatcher();

	// Props
	export let legend: Array<{
		label: string;
		color: string;
	}> = [];
	export let indicatorName: string = '';

	// Parse unit from indicator name
	$: unitInfo = parseUnit(indicatorName);

	function parseUnit(name: string): { prefix: string; suffix: string; caption: string } {
		if (!name) return { prefix: '', suffix: '', caption: '' };
		// Extract unit marker from parentheses at end of name
		const dollarMatch = name.match(/\(\$\)\s*$/);
		const pctMatch = name.match(/\((%[^)]*)\)\s*$/);
		if (dollarMatch) {
			const caption = name.replace(/\s*\(\$\)\s*$/, '').trim();
			return { prefix: '$', suffix: '', caption };
		}
		if (pctMatch) {
			const caption = name.replace(/\s*\(%[^)]*\)\s*$/, '').trim();
			return { prefix: '', suffix: '%', caption };
		}
		// No unit marker
		return { prefix: '', suffix: '', caption: name };
	}

	// Component state
	let isExpanded = true;
	let filterEnabled = false;
	let sliderMin = 0;
	let sliderMax = 100;
	let rangeMin = 0;
	let rangeMax = 100;

	// Parse min/max values from legend labels
	$: {
		const dataEntries = legend.filter(e => !isNoDataEntry(e.label));
		if (dataEntries.length > 0) {
			const firstLabel = dataEntries[0].label;
			const lastLabel = dataEntries[dataEntries.length - 1].label;
			const firstParts = firstLabel.split(' - ');
			const lastParts = lastLabel.split(' - ');
			if (firstParts.length === 2 && lastParts.length === 2) {
				const parsedMin = parseFloat(firstParts[0].replace(/,/g, ''));
				const parsedMax = parseFloat(lastParts[1].replace(/,/g, ''));
				if (!isNaN(parsedMin) && !isNaN(parsedMax)) {
					sliderMin = parsedMin;
					sliderMax = parsedMax;
					// Reset range when legend changes
					rangeMin = parsedMin;
					rangeMax = parsedMax;
					filterEnabled = false;
					dispatch('filterChange', null);
				}
			}
		}
	}

	// Handle slider changes
	function handleRangeChange() {
		if (rangeMin === sliderMin && rangeMax === sliderMax) {
			filterEnabled = false;
			dispatch('filterChange', null);
		} else {
			filterEnabled = true;
			dispatch('filterChange', { min: rangeMin, max: rangeMax });
		}
	}

	function handleMinInput(e: Event) {
		const val = parseFloat((e.target as HTMLInputElement).value);
		if (val <= rangeMax) {
			rangeMin = val;
			handleRangeChange();
		}
	}

	function handleMaxInput(e: Event) {
		const val = parseFloat((e.target as HTMLInputElement).value);
		if (val >= rangeMin) {
			rangeMax = val;
			handleRangeChange();
		}
	}

	function handleMinTextInput(e: Event) {
		const val = parseFloat((e.target as HTMLInputElement).value);
		if (!isNaN(val)) {
			rangeMin = Math.max(sliderMin, Math.min(val, rangeMax));
			(e.target as HTMLInputElement).value = String(rangeMin);
			handleRangeChange();
		}
	}

	function handleMaxTextInput(e: Event) {
		const val = parseFloat((e.target as HTMLInputElement).value);
		if (!isNaN(val)) {
			rangeMax = Math.min(sliderMax, Math.max(val, rangeMin));
			(e.target as HTMLInputElement).value = String(rangeMax);
			handleRangeChange();
		}
	}

	function resetFilter() {
		rangeMin = sliderMin;
		rangeMax = sliderMax;
		filterEnabled = false;
		dispatch('filterChange', null);
	}

	// Format value for display
	function formatValue(val: number): string {
		if (Math.abs(val) >= 1000) {
			return val.toLocaleString('en-US', { maximumFractionDigits: 0 });
		}
		return val.toLocaleString('en-US', { maximumFractionDigits: 2 });
	}

	// Toggle legend visibility
	function toggleLegend() {
		isExpanded = !isExpanded;
	}

	// Check if this is a "no data" entry
	function isNoDataEntry(label: string): boolean {
		return label.toLowerCase().includes('no data');
	}

	// Format legend label with unit symbols
	function formatLabelWithUnit(label: string): string {
		if (isNoDataEntry(label)) return label;
		if (!unitInfo.prefix && !unitInfo.suffix) return label;
		// Labels are formatted as "lower - upper"
		const parts = label.split(' - ');
		if (parts.length !== 2) return label;
		const formatted = parts.map(p => {
			const trimmed = p.trim();
			return `${unitInfo.prefix}${trimmed}${unitInfo.suffix}`;
		});
		return formatted.join(' – ');
	}

	// Calculate percentage position for slider track highlight
	$: trackLeft = ((rangeMin - sliderMin) / (sliderMax - sliderMin)) * 100;
	$: trackWidth = ((rangeMax - rangeMin) / (sliderMax - sliderMin)) * 100;
</script>

<!-- Legend container -->
<div
	class="bg-white rounded-lg shadow-lg border border-neutral-200 overflow-hidden"
	transition:fade={{ duration: 200 }}
>
	<!-- Legend header -->
	<div class="flex items-center justify-between p-3 bg-neutral-50 border-b border-neutral-200">
		<h3 class="text-sm font-semibold text-neutral-700">Legend</h3>
		<button
			class="text-neutral-500 hover:text-neutral-700 transition-colors"
			on:click={toggleLegend}
			aria-label={isExpanded ? 'Collapse legend' : 'Expand legend'}
		>
			<svg
				class="w-4 h-4 transform transition-transform duration-200"
				class:rotate-180={!isExpanded}
				fill="none"
				stroke="currentColor"
				viewBox="0 0 24 24"
			>
				<path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M19 9l-7 7-7-7" />
			</svg>
		</button>
	</div>

	<!-- Legend content -->
	{#if isExpanded}
		<div class="p-3" transition:fade={{ duration: 150 }}>
			{#if legend.length > 0}
				<!-- SVG definitions for patterns -->
				<svg width="0" height="0" class="absolute">
					<defs>
						{#each legend as entry}
							{#if isNoDataEntry(entry.label)}
								<pattern
									id="hash-pattern-{entry.color.replace('#', '')}"
									patternUnits="userSpaceOnUse"
									width="8"
									height="8"
								>
									<rect width="8" height="8" fill="{entry.color}" opacity="0.3" />
									<path d="M0,8 L8,0 M-2,2 L2,-2 M6,10 L10,6" stroke="{entry.color}" stroke-width="1" />
								</pattern>
							{/if}
						{/each}
					</defs>
				</svg>

				<!-- Legend entries -->
				<div class="space-y-2">
					{#each legend as entry, index}
						<div class="flex items-center space-x-3">
							<!-- Color indicator -->
							<div class="flex-shrink-0">
								{#if isNoDataEntry(entry.label)}
									<!-- Hash pattern for no data -->
									<svg width="16" height="16" class="border border-neutral-300 rounded">
										<rect
											width="16"
											height="16"
											fill="url(#hash-pattern-{entry.color.replace('#', '')})"
										/>
									</svg>
								{:else}
									<!-- Solid color for data -->
									<div
										class="w-4 h-4 border border-neutral-300 rounded"
										style="background-color: {entry.color};"
									></div>
								{/if}
							</div>

							<!-- Label -->
							<span class="text-xs text-neutral-700 leading-tight">
								{formatLabelWithUnit(entry.label)}
							</span>
						</div>
					{/each}
				</div>

				<!-- Quintile note -->
				<p class="text-[10px] text-neutral-400 mt-2">Each color represents one quintile of values</p>

				<!-- Value filter slider -->
				{#if sliderMin !== sliderMax}
					<div class="mt-3 pt-3 border-t border-neutral-200">
						<div class="flex items-center justify-between mb-1">
							<span class="text-xs font-semibold text-neutral-700">Filter</span>
							<button
								class="text-[10px] px-2 py-0.5 rounded font-medium transition-colors {filterEnabled ? 'bg-teal-600 text-white hover:bg-teal-700' : 'bg-neutral-200 text-neutral-400 cursor-default'}"
								on:click={resetFilter}
								disabled={!filterEnabled}
							>
								Reset
							</button>
						</div>
						{#if unitInfo.caption}
							<p class="text-[10px] text-neutral-500 mb-1.5">{unitInfo.caption}</p>
						{/if}

						<!-- Editable range inputs -->
						<div class="flex items-center gap-1 mb-2">
							{#if unitInfo.prefix}<span class="text-xs text-neutral-400">{unitInfo.prefix}</span>{/if}
							<input
								type="number"
								class="filter-input"
								value={rangeMin}
								min={sliderMin}
								max={rangeMax}
								step={(sliderMax - sliderMin) / 200}
								on:change={handleMinTextInput}
							/>
							{#if unitInfo.suffix}<span class="text-xs text-neutral-400">{unitInfo.suffix}</span>{/if}
							<span class="text-xs text-neutral-400 mx-0.5">–</span>
							{#if unitInfo.prefix}<span class="text-xs text-neutral-400">{unitInfo.prefix}</span>{/if}
							<input
								type="number"
								class="filter-input"
								value={rangeMax}
								min={rangeMin}
								max={sliderMax}
								step={(sliderMax - sliderMin) / 200}
								on:change={handleMaxTextInput}
							/>
							{#if unitInfo.suffix}<span class="text-xs text-neutral-400">{unitInfo.suffix}</span>{/if}
						</div>

						<!-- Dual range slider -->
						<div class="range-slider">
							<div class="range-track">
								<div
									class="range-highlight"
									style="left: {trackLeft}%; width: {trackWidth}%;"
								></div>
							</div>
							<input
								type="range"
								min={sliderMin}
								max={sliderMax}
								step={(sliderMax - sliderMin) / 200}
								value={rangeMin}
								on:input={handleMinInput}
								class="range-input"
							/>
							<input
								type="range"
								min={sliderMin}
								max={sliderMax}
								step={(sliderMax - sliderMin) / 200}
								value={rangeMax}
								on:input={handleMaxInput}
								class="range-input"
							/>
						</div>
					</div>
				{/if}
			{:else}
				<!-- No legend data -->
				<div class="text-center py-2">
					<p class="text-xs text-neutral-500">No legend data available</p>
				</div>
			{/if}
		</div>
	{/if}
</div>

<style>
	/* Ensure SVG patterns render correctly */
	svg {
		shape-rendering: crispEdges;
	}

	/* Filter text input styles */
	.filter-input {
		width: 100%;
		min-width: 0;
		flex: 1;
		font-size: 11px;
		padding: 2px 4px;
		border: 1px solid #d1d5db;
		border-radius: 4px;
		text-align: right;
		color: #374151;
		background: white;
		-moz-appearance: textfield;
		font-variant-numeric: tabular-nums;
	}
	.filter-input::-webkit-outer-spin-button,
	.filter-input::-webkit-inner-spin-button {
		-webkit-appearance: none;
		margin: 0;
	}
	.filter-input:focus {
		outline: none;
		border-color: #08ACA6;
		box-shadow: 0 0 0 1px #08ACA6;
	}

	/* Dual range slider styles */
	.range-slider {
		position: relative;
		height: 24px;
		margin-top: 4px;
	}

	.range-track {
		position: absolute;
		top: 50%;
		transform: translateY(-50%);
		width: 100%;
		height: 4px;
		background: #e5e7eb;
		border-radius: 2px;
		pointer-events: none;
	}

	.range-highlight {
		position: absolute;
		height: 100%;
		background: #08ACA6;
		border-radius: 2px;
	}

	.range-input {
		position: absolute;
		top: 0;
		left: 0;
		width: 100%;
		height: 100%;
		-webkit-appearance: none;
		appearance: none;
		background: transparent;
		pointer-events: none;
		margin: 0;
	}

	.range-input::-webkit-slider-thumb {
		-webkit-appearance: none;
		appearance: none;
		width: 14px;
		height: 14px;
		border-radius: 50%;
		background: #08ACA6;
		border: 2px solid white;
		box-shadow: 0 1px 3px rgba(0, 0, 0, 0.3);
		cursor: pointer;
		pointer-events: all;
	}

	.range-input::-moz-range-thumb {
		width: 14px;
		height: 14px;
		border-radius: 50%;
		background: #08ACA6;
		border: 2px solid white;
		box-shadow: 0 1px 3px rgba(0, 0, 0, 0.3);
		cursor: pointer;
		pointer-events: all;
	}
</style>
