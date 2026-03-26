<script lang="ts">
	import { createEventDispatcher } from 'svelte';
	import Button from './Button.svelte';
	
	// Props
	export let availableUnits: {geo_id: string, geo_name: string}[] = [];
	export let selectedUnits: string[] = [];
	export let disabled: boolean = false;
	export let placeholder: string = "Search geographic units...";
	
	// Event dispatcher
	const dispatch = createEventDispatcher<{
		change: string[];
	}>();
	
	// Component state
	let searchTerm = '';
	let isDropdownOpen = false;
	let dropdownContainer: HTMLDivElement;
	
	// Filtered units based on search term
	$: filteredUnits = availableUnits.filter(unit => 
		unit.geo_name.toLowerCase().includes(searchTerm.toLowerCase()) ||
		unit.geo_id.toLowerCase().includes(searchTerm.toLowerCase())
	);
	
	// Selected unit names for display
	$: selectedUnitNames = availableUnits
		.filter(unit => selectedUnits.includes(unit.geo_id))
		.map(unit => unit.geo_name);
	
	// Display text for the selector
	$: displayText = selectedUnits.length === 0 
		? 'Select geographic units...'
		: selectedUnits.length === 1
		? selectedUnitNames[0]
		: selectedUnits.length === availableUnits.length
		? 'All units selected'
		: `${selectedUnits.length} units selected`;
	
	// Handle unit selection toggle
	function toggleUnit(geoId: string) {
		if (selectedUnits.includes(geoId)) {
			selectedUnits = selectedUnits.filter(id => id !== geoId);
		} else {
			selectedUnits = [...selectedUnits, geoId];
		}
		dispatch('change', selectedUnits);
	}
	
	// Select all units
	function selectAll() {
		selectedUnits = availableUnits.map(unit => unit.geo_id);
		dispatch('change', selectedUnits);
	}
	
	// Clear all selections
	function clearAll() {
		selectedUnits = [];
		dispatch('change', selectedUnits);
	}
	
	// Handle dropdown toggle
	function toggleDropdown() {
		if (disabled) return;
		isDropdownOpen = !isDropdownOpen;
		if (isDropdownOpen) {
			// Focus search input when dropdown opens
			setTimeout(() => {
				const searchInput = dropdownContainer?.querySelector('input[type="text"]') as HTMLInputElement;
				searchInput?.focus();
			}, 10);
		}
	}
	
	// Close dropdown when clicking outside
	function handleClickOutside(event: MouseEvent) {
		if (dropdownContainer && !dropdownContainer.contains(event.target as Node)) {
			isDropdownOpen = false;
		}
	}
	
	// Handle keyboard navigation
	function handleKeydown(event: KeyboardEvent) {
		if (event.key === 'Escape') {
			isDropdownOpen = false;
		}
	}
</script>

<svelte:window on:click={handleClickOutside} on:keydown={handleKeydown} />

<div class="relative" bind:this={dropdownContainer}>
	<!-- Selector Button -->
	<button
		type="button"
		class="relative w-full bg-white border border-neutral-300 rounded-md shadow-sm pl-3 pr-10 py-2 text-left cursor-pointer focus:outline-none focus:ring-1 focus:ring-blue-500 focus:border-blue-500 text-sm {disabled ? 'opacity-50 cursor-not-allowed' : 'hover:border-neutral-400'}"
		on:click={toggleDropdown}
		{disabled}
		aria-haspopup="listbox"
		aria-expanded={isDropdownOpen}
	>
		<span class="block truncate {selectedUnits.length === 0 ? 'text-neutral-500' : 'text-neutral-900'}">
			{displayText}
		</span>
		<span class="absolute inset-y-0 right-0 flex items-center pr-2 pointer-events-none">
			<svg class="h-5 w-5 text-neutral-400 transform transition-transform {isDropdownOpen ? 'rotate-180' : ''}" viewBox="0 0 20 20" fill="currentColor">
				<path fill-rule="evenodd" d="M5.293 7.293a1 1 0 011.414 0L10 10.586l3.293-3.293a1 1 0 111.414 1.414l-4 4a1 1 0 01-1.414 0l-4-4a1 1 0 010-1.414z" clip-rule="evenodd" />
			</svg>
		</span>
	</button>
	
	<!-- Dropdown -->
	{#if isDropdownOpen}
		<div class="absolute z-50 mt-1 w-full bg-white shadow-lg max-h-80 rounded-md py-1 text-base ring-1 ring-black ring-opacity-5 overflow-auto focus:outline-none text-sm">
			<!-- Search Input -->
			<div class="sticky top-0 bg-white px-3 py-2 border-b border-neutral-200">
				<input
					type="text"
					class="w-full px-3 py-1 border border-neutral-300 rounded-md focus:outline-none focus:ring-1 focus:ring-blue-500 focus:border-blue-500 text-sm"
					placeholder={placeholder}
					bind:value={searchTerm}
				/>
			</div>
			
			<!-- Bulk Actions -->
			{#if availableUnits.length > 0}
				<div class="sticky top-12 bg-white px-3 py-2 border-b border-neutral-200 flex space-x-2">
					<Button
						variant="outline"
						size="xs"
						on:click={selectAll}
						disabled={selectedUnits.length === availableUnits.length}
					>
						Select All
					</Button>
					<Button
						variant="outline"
						size="xs"
						on:click={clearAll}
						disabled={selectedUnits.length === 0}
					>
						Clear All
					</Button>
				</div>
			{/if}
			
			<!-- Unit List -->
			{#if filteredUnits.length === 0}
				<div class="px-3 py-2 text-neutral-500 text-center">
					{searchTerm ? 'No units match your search' : 'No units available'}
				</div>
			{:else}
				{#each filteredUnits as unit (unit.geo_id)}
					<label class="flex items-center px-3 py-2 hover:bg-neutral-50 cursor-pointer">
						<input
							type="checkbox"
							class="h-4 w-4 text-blue-600 focus:ring-blue-500 border-neutral-300 rounded"
							checked={selectedUnits.includes(unit.geo_id)}
							on:change={() => toggleUnit(unit.geo_id)}
						/>
						<span class="ml-3 block truncate text-neutral-900">
							{unit.geo_name}
						</span>
						<span class="ml-auto text-xs text-neutral-500">
							{unit.geo_id}
						</span>
					</label>
				{/each}
			{/if}
		</div>
	{/if}
</div>
