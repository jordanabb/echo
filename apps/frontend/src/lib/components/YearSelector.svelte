<script lang="ts">
	import { createEventDispatcher } from 'svelte';
	import { allAvailableYears } from '$lib/stores/metadata';
	import Button from './Button.svelte';

	// Component props
	export let selectedYears: number[] = [];
	export let availableYears: number[] = [];
	export let mode: 'dropdown' | 'inline' = 'dropdown';
	export let placeholder = 'Select years...';
	export let showSelectAll = true;
	export let showClearAll = true;
	export let maxDisplayYears = 3; // For compact display

	// Use provided availableYears or fall back to all available years
	$: years = availableYears.length > 0 ? availableYears : $allAvailableYears;

	// Local state
	let isOpen = false;
	let dropdownElement: HTMLDivElement;

	// Event dispatcher
	const dispatch = createEventDispatcher<{
		change: { selectedYears: number[] };
		yearToggle: { year: number; selected: boolean };
	}>();

	/**
	 * Toggles a year selection
	 */
	function toggleYear(year: number): void {
		const isSelected = selectedYears.includes(year);
		let newSelectedYears: number[];

		if (isSelected) {
			// Remove year, but ensure at least one year remains
			newSelectedYears = selectedYears.filter(y => y !== year);
			if (newSelectedYears.length === 0) {
				// Don't allow removing the last year
				return;
			}
		} else {
			// Add year
			newSelectedYears = [...selectedYears, year].sort((a, b) => a - b);
		}

		selectedYears = newSelectedYears;
		dispatch('change', { selectedYears: newSelectedYears });
		dispatch('yearToggle', { year, selected: !isSelected });
	}

	/**
	 * Selects all available years
	 */
	function selectAllYears(): void {
		const newSelectedYears = [...years].sort((a, b) => a - b);
		selectedYears = newSelectedYears;
		dispatch('change', { selectedYears: newSelectedYears });
	}

	/**
	 * Clears all years except the most recent one
	 */
	function clearAllYears(): void {
		const mostRecentYear = Math.max(...years);
		const newSelectedYears = [mostRecentYear];
		selectedYears = newSelectedYears;
		dispatch('change', { selectedYears: newSelectedYears });
	}

	/**
	 * Gets display text for selected years
	 */
	function getDisplayText(): string {
		if (selectedYears.length === 0) {
			return placeholder;
		}

		if (selectedYears.length === 1) {
			return selectedYears[0].toString();
		}

		if (selectedYears.length <= maxDisplayYears) {
			return selectedYears.sort((a, b) => a - b).join(', ');
		}

		// Check if years form a continuous range
		const sortedYears = [...selectedYears].sort((a, b) => a - b);
		const isRange = sortedYears.every((year, index) => 
			index === 0 || year === sortedYears[index - 1] + 1
		);

		if (isRange) {
			return `${sortedYears[0]}-${sortedYears[sortedYears.length - 1]} (${selectedYears.length} years)`;
		}

		// Show first few years and count
		const displayYears = sortedYears.slice(0, maxDisplayYears).join(', ');
		const remainingCount = selectedYears.length - maxDisplayYears;
		return `${displayYears} (+${remainingCount} more)`;
	}

	/**
	 * Closes dropdown when clicking outside
	 */
	function handleClickOutside(event: MouseEvent): void {
		if (dropdownElement && !dropdownElement.contains(event.target as Node)) {
			isOpen = false;
		}
	}

	/**
	 * Handles keyboard navigation
	 */
	function handleKeydown(event: KeyboardEvent): void {
		if (event.key === 'Escape') {
			isOpen = false;
		}
	}
</script>

<svelte:window on:click={handleClickOutside} on:keydown={handleKeydown} />

{#if mode === 'dropdown'}
	<!-- Dropdown Mode -->
	<div class="relative" bind:this={dropdownElement}>
		<button
			type="button"
			class="w-full flex items-center justify-between px-3 py-2 border border-neutral-300 rounded-md shadow-sm bg-white text-sm focus:outline-none focus:ring-2 focus:ring-primary-500 focus:border-primary-500 hover:bg-neutral-50 transition-colors"
			on:click={() => isOpen = !isOpen}
		>
			<span class="truncate" class:text-neutral-500={selectedYears.length === 0}>
				{getDisplayText()}
			</span>
			<svg 
				class="ml-2 h-4 w-4 text-neutral-400 transition-transform duration-200 {isOpen ? 'rotate-180' : ''}"
				fill="none" 
				stroke="currentColor" 
				viewBox="0 0 24 24"
			>
				<path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M19 9l-7 7-7-7" />
			</svg>
		</button>

		{#if isOpen}
			<div class="absolute z-[60] mt-1 w-full min-w-max bg-white border border-neutral-300 rounded-md shadow-lg max-h-60 overflow-y-auto">
				<!-- Header with controls -->
				{#if showSelectAll || showClearAll}
					<div class="px-3 py-2 border-b border-neutral-200 bg-neutral-50">
						<div class="flex items-center justify-between">
							<span class="text-xs font-medium text-neutral-700">
								{selectedYears.length} of {years.length} selected
							</span>
							<div class="flex space-x-2">
								{#if showSelectAll}
									<button
										type="button"
										class="text-xs text-primary-600 hover:text-primary-700 font-medium"
										on:click={selectAllYears}
									>
										Select All
									</button>
								{/if}
								{#if showClearAll && selectedYears.length > 1}
									<button
										type="button"
										class="text-xs text-neutral-600 hover:text-neutral-700 font-medium"
										on:click={clearAllYears}
									>
										Clear All
									</button>
								{/if}
							</div>
						</div>
					</div>
				{/if}

				<!-- Year options -->
				<div class="py-1">
					{#each years as year}
						{@const isSelected = selectedYears.includes(year)}
						{@const isLastSelected = selectedYears.length === 1 && isSelected}
						<label 
							class="flex items-center px-3 py-2 hover:bg-neutral-50 cursor-pointer transition-colors {isLastSelected ? 'opacity-50 cursor-not-allowed' : ''}"
							class:bg-primary-50={isSelected && !isLastSelected}
						>
							<input
								type="checkbox"
								checked={isSelected}
								disabled={isLastSelected}
								on:change={() => !isLastSelected && toggleYear(year)}
								class="h-4 w-4 text-primary-600 border-neutral-300 rounded focus:ring-primary-500 focus:ring-2 transition-colors"
							/>
							<span class="ml-3 text-sm text-neutral-900 flex-1">
								{year}
							</span>
							{#if isSelected}
								<svg class="h-4 w-4 text-primary-600" fill="currentColor" viewBox="0 0 20 20">
									<path fill-rule="evenodd" d="M16.707 5.293a1 1 0 010 1.414l-8 8a1 1 0 01-1.414 0l-4-4a1 1 0 011.414-1.414L8 12.586l7.293-7.293a1 1 0 011.414 0z" clip-rule="evenodd" />
								</svg>
							{/if}
						</label>
					{/each}
				</div>

				{#if selectedYears.length === 1}
					<div class="px-3 py-2 border-t border-neutral-200 bg-neutral-50">
						<p class="text-xs text-neutral-600">
							At least one year must be selected
						</p>
					</div>
				{/if}
			</div>
		{/if}
	</div>
{:else}
	<!-- Inline Mode -->
	<div class="space-y-3">
		<!-- Header with controls -->
		{#if showSelectAll || showClearAll}
			<div class="flex items-center justify-between">
				<span class="text-sm font-medium text-neutral-700">
					Data Years ({selectedYears.length} selected)
				</span>
				<div class="flex space-x-2">
					{#if showSelectAll}
						<Button variant="ghost" size="sm" on:click={selectAllYears}>
							Select All
						</Button>
					{/if}
					{#if showClearAll && selectedYears.length > 1}
						<Button variant="ghost" size="sm" on:click={clearAllYears}>
							Clear All
						</Button>
					{/if}
				</div>
			</div>
		{/if}

		<!-- Year checkboxes -->
		<div class="grid grid-cols-2 sm:grid-cols-3 md:grid-cols-4 gap-2">
			{#each years as year}
				{@const isSelected = selectedYears.includes(year)}
				{@const isLastSelected = selectedYears.length === 1 && isSelected}
				<label 
					class="flex items-center space-x-2 p-2 border border-neutral-200 rounded-md hover:bg-neutral-50 cursor-pointer transition-colors {isLastSelected ? 'opacity-50 cursor-not-allowed' : ''}"
					class:bg-primary-50={isSelected && !isLastSelected}
					class:border-primary-300={isSelected && !isLastSelected}
				>
					<input
						type="checkbox"
						checked={isSelected}
						disabled={isLastSelected}
						on:change={() => !isLastSelected && toggleYear(year)}
						class="h-4 w-4 text-primary-600 border-neutral-300 rounded focus:ring-primary-500 focus:ring-2 transition-colors"
					/>
					<span class="text-sm text-neutral-900 flex-1">
						{year}
					</span>
					{#if isSelected}
						<svg class="h-4 w-4 text-primary-600" fill="currentColor" viewBox="0 0 20 20">
							<path fill-rule="evenodd" d="M16.707 5.293a1 1 0 010 1.414l-8 8a1 1 0 01-1.414 0l-4-4a1 1 0 011.414-1.414L8 12.586l7.293-7.293a1 1 0 011.414 0z" clip-rule="evenodd" />
						</svg>
					{/if}
				</label>
			{/each}
		</div>

		{#if selectedYears.length === 1}
			<p class="text-xs text-neutral-600">
				At least one year must be selected
			</p>
		{/if}
	</div>
{/if}
