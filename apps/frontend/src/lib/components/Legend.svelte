<script lang="ts">
	import { fade } from 'svelte/transition';
	
	// Props
	export let legend: Array<{
		label: string;
		color: string;
	}> = [];
	
	// Component state
	let isExpanded = true;
	
	// Toggle legend visibility
	function toggleLegend() {
		isExpanded = !isExpanded;
	}
	
	// Create pattern for "no data" entries
	function createHashPattern(color: string): string {
		const patternId = `hash-pattern-${color.replace('#', '')}`;
		return `url(#${patternId})`;
	}
	
	// Check if this is a "no data" entry
	function isNoDataEntry(label: string): boolean {
		return label.toLowerCase().includes('no data');
	}
</script>

<!-- Legend container -->
<div 
	class="bg-white rounded-lg shadow-lg border border-gray-200 overflow-hidden"
	transition:fade={{ duration: 200 }}
>
	<!-- Legend header -->
	<div class="flex items-center justify-between p-3 bg-gray-50 border-b border-gray-200">
		<h3 class="text-sm font-semibold text-gray-700">Legend</h3>
		<button
			class="text-gray-500 hover:text-gray-700 transition-colors"
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
									<svg width="16" height="16" class="border border-gray-300 rounded">
										<rect 
											width="16" 
											height="16" 
											fill="url(#hash-pattern-{entry.color.replace('#', '')})"
										/>
									</svg>
								{:else}
									<!-- Solid color for data -->
									<div 
										class="w-4 h-4 border border-gray-300 rounded"
										style="background-color: {entry.color};"
									></div>
								{/if}
							</div>
							
							<!-- Label -->
							<span class="text-xs text-gray-700 leading-tight">
								{entry.label}
							</span>
						</div>
					{/each}
				</div>
			{:else}
				<!-- No legend data -->
				<div class="text-center py-2">
					<p class="text-xs text-gray-500">No legend data available</p>
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
</style>
