<script lang="ts">
	import { onMount, onDestroy } from 'svelte';
	import { browser } from '$app/environment';
	import { 
		unifiedFilters,
		currentGeoLevel,
		currentGeoFilter,
		currentYears,
		currentSelectedIndicators,
		selectedIndicatorsWithMetadata,
		isAnalysisReady
	} from '$lib/stores/unifiedFilters';
	import { crossfade } from 'svelte/transition';
	import { quintOut } from 'svelte/easing';
	import { formatValueByType } from '$lib/utils';
	import { showVariableSelector } from '$lib/stores/interactiveSteps';
	import { getStateNameByCode } from '$lib/constants/states';
	import Card from './Card.svelte';
	import Button from './Button.svelte';
	import SkeletonLoader from './SkeletonLoader.svelte';
	import EmptyState from './EmptyState.svelte';
	import LoadingSpinner from './LoadingSpinner.svelte';
	
	// Component state
	let isLoading = false;
	let error: string | null = null;
	let tableData: any[] = [];
	let filteredData: any[] = [];
	let columns: string[] = [];
	let debounceTimer: NodeJS.Timeout | null = null;
	let hasAttemptedLoad = false; // Track if we've attempted to load data
	
	// Sorting and filtering state
	let sortColumn: string | null = null;
	let sortDirection: 'asc' | 'desc' = 'asc';
	let searchTerm = '';
	
	// Crossfade transition for smooth updates
	const [send, receive] = crossfade({
		duration: 300,
		easing: quintOut
	});
	
	// Debounce delay in milliseconds
	const DEBOUNCE_DELAY = 500;
	
	// Function to debounce API calls
	function debounceApiCall(callback: () => void, delay: number) {
		if (debounceTimer) {
			clearTimeout(debounceTimer);
		}
		debounceTimer = setTimeout(callback, delay);
	}
	
	// Function to fetch all geo_ids for a given geography level and year
	async function fetchGeoIds(geoLevel: string, year: number, stateFilter?: string | null): Promise<string[]> {
		try {
			const params = new URLSearchParams({
				geo_level: geoLevel,
				year: year.toString()
			});
			
			// Add state filter if provided
			if (stateFilter) {
				params.set('state_filter', stateFilter);
				console.log('DataTable: Adding state filter:', stateFilter);
			}
			
			console.log('DataTable: Fetching geo_ids with URL:', `/api/geometries?${params}`);
			// Use the geometries endpoint which properly filters by geo_level
			const response = await fetch(`/api/geometries?${params}`);
			
			if (!response.ok) {
				throw new Error(`Failed to fetch geo_ids: ${response.statusText}`);
			}
			
			const data = await response.json();
			
			// Extract geo_ids from the response - geometries endpoint ensures proper geo_level filtering
			return data.geoJson?.features?.map((feature: any) => feature.properties?.geo_id) || [];
		} catch (err) {
			console.error('Error fetching geo_ids:', err);
			return [];
		}
	}
	
	// Function to fetch table data from API
	async function fetchTableData() {
		if (!$isAnalysisReady || !$currentGeoLevel) {
			return;
		}
		
		isLoading = true;
		error = null;
		
		try {
			// First, get all geo_ids for the selected geography level and years
			const allGeoIds = new Set<string>();
			
			// Fetch geo_ids for each year (in case different years have different geographies)
			for (const year of $currentYears) {
				const yearGeoIds = await fetchGeoIds($currentGeoLevel, year, $currentGeoFilter);
				yearGeoIds.forEach(id => allGeoIds.add(id));
			}
			
			if (allGeoIds.size === 0) {
				throw new Error('No geographic areas found for the selected filters');
			}
			
			// Prepare the request payload with geo_level to ensure proper filtering
			const requestPayload = {
				geo_ids: Array.from(allGeoIds),
				indicator_ids: $currentSelectedIndicators,
				years: $currentYears,
				geo_level: $currentGeoLevel  // Add geo_level to filter out mixed geographic levels
			};
			
			console.log('Fetching table data with payload:', requestPayload);
			
			const response = await fetch('/api/table-data', {
				method: 'POST',
				headers: {
					'Content-Type': 'application/json'
				},
				body: JSON.stringify(requestPayload)
			});
			
			if (!response.ok) {
				throw new Error(`HTTP ${response.status}: ${response.statusText}`);
			}
			
			const data = await response.json();
			
			if (!Array.isArray(data) || data.length === 0) {
				// No data available
				tableData = [];
				filteredData = [];
				columns = [];
				return;
			}
			
			// Extract column names from the first row
			const firstRow = data[0];
			columns = Object.keys(firstRow);
			
			// Store the data
			tableData = data;
			filteredData = data;
			
			console.log('Table data received:', {
				rows: data.length,
				columns: columns.length,
				sampleRow: firstRow
			});
			
		} catch (err) {
			console.error('Error fetching table data:', err);
			error = err instanceof Error ? err.message : 'Failed to load table data';
			tableData = [];
			filteredData = [];
			columns = [];
		} finally {
			isLoading = false;
		}
	}
	
	// Function to handle sorting
	function handleSort(column: string) {
		if (sortColumn === column) {
			// Toggle direction if same column
			sortDirection = sortDirection === 'asc' ? 'desc' : 'asc';
		} else {
			// New column, default to ascending
			sortColumn = column;
			sortDirection = 'asc';
		}
		
		// Apply sorting
		applySortingAndFiltering();
	}
	
	// Function to apply sorting and filtering
	function applySortingAndFiltering() {
		let result = [...tableData];
		
		// Apply search filter
		if (searchTerm.trim()) {
			const searchLower = searchTerm.toLowerCase();
			result = result.filter(row => {
				// Search in geo_name primarily, but also other string fields
				const geoName = String(row.geo_name || '').toLowerCase();
				const geoId = String(row.geo_id || '').toLowerCase();
				return geoName.includes(searchLower) || geoId.includes(searchLower);
			});
		}
		
		// Apply sorting
		if (sortColumn) {
			result.sort((a, b) => {
				const aVal = a[sortColumn];
				const bVal = b[sortColumn];
				
				// Handle null/undefined values
				if (aVal == null && bVal == null) return 0;
				if (aVal == null) return sortDirection === 'asc' ? 1 : -1;
				if (bVal == null) return sortDirection === 'asc' ? -1 : 1;
				
				// Compare values
				let comparison = 0;
				if (typeof aVal === 'number' && typeof bVal === 'number') {
					comparison = aVal - bVal;
				} else {
					comparison = String(aVal).localeCompare(String(bVal));
				}
				
				return sortDirection === 'asc' ? comparison : -comparison;
			});
		}
		
		filteredData = result;
	}
	
	// Function to export data to CSV
	function exportToCSV() {
		if (filteredData.length === 0) return;
		
		// Create CSV content
		const headers = columns.map(col => getColumnDisplayName(col));
		const csvContent = [
			headers.join(','),
			...filteredData.map(row => 
				columns.map(col => {
					const value = row[col];
					if (value == null) return '';
					
					// Escape quotes and wrap in quotes if contains comma or quote
					const stringValue = String(value);
					if (stringValue.includes(',') || stringValue.includes('"') || stringValue.includes('\n')) {
						return `"${stringValue.replace(/"/g, '""')}"`;
					}
					return stringValue;
				}).join(',')
			)
		].join('\n');
		
		// Create and trigger download
		const blob = new Blob([csvContent], { type: 'text/csv;charset=utf-8;' });
		const link = document.createElement('a');
		const url = URL.createObjectURL(blob);
		link.setAttribute('href', url);
		link.setAttribute('download', `data-export-${new Date().toISOString().split('T')[0]}.csv`);
		link.style.visibility = 'hidden';
		document.body.appendChild(link);
		link.click();
		document.body.removeChild(link);
		URL.revokeObjectURL(url);
	}
	
	// Reactive statement to apply filtering and sorting when data or search term changes
	$: if (tableData.length > 0) {
		applySortingAndFiltering();
	}
	
	// Reactive statement to trigger filtering when searchTerm changes
	$: if (tableData.length > 0 && searchTerm !== undefined) {
		applySortingAndFiltering();
	}
	
	// Reactive statement to fetch data when analysis filters change
	$: if (browser && $isAnalysisReady) {
		debounceApiCall(fetchTableData, DEBOUNCE_DELAY);
	}
	
	// Additional reactive statements to ensure data updates when individual filters change
	$: if (browser && $currentYears && $currentYears.length > 0 && $currentSelectedIndicators && $currentSelectedIndicators.length > 0 && $currentGeoLevel) {
		debounceApiCall(fetchTableData, DEBOUNCE_DELAY);
	}
	
	// Reactive statement to refetch data when state filter changes
	$: if (browser && $isAnalysisReady && $currentGeoFilter !== undefined) {
		debounceApiCall(fetchTableData, DEBOUNCE_DELAY);
	}
	
	// Clean up debounce timer on component destroy
	onDestroy(() => {
		if (debounceTimer) {
			clearTimeout(debounceTimer);
		}
	});
	
	// Function to format cell values with smart type detection
	function formatCellValue(value: any, columnName: string): string {
		if (value === null || value === undefined) {
			return '—';
		}
		
		// Handle state_fips column - convert FIPS code to state name
		if (columnName === 'state_fips') {
			const stateName = getStateNameByCode(String(value));
			return stateName || String(value);
		}
		
		// Skip formatting for non-numeric columns
		if (['geo_id', 'geo_name', 'year', 'state_fips'].includes(columnName)) {
			return String(value);
		}
		
		// Get indicator metadata for better formatting context
		let indicatorName = '';
		if ($selectedIndicatorsWithMetadata) {
			const indicator = $selectedIndicatorsWithMetadata.find(ind => ind.id === columnName);
			if (indicator) {
				indicatorName = indicator.name;
			}
		}
		
		// Use the smart formatting function
		return formatValueByType(value, columnName, indicatorName);
	}
	
	// Function to get column header display name
	function getColumnDisplayName(columnName: string): string {
		// Handle special cases first
		const specialCases: Record<string, string> = {
			'geo_id': 'Geography ID',
			'geo_name': 'Geography Name',
			'state_fips': 'State',
			'year': 'Year'
		};
		
		if (specialCases[columnName]) {
			return specialCases[columnName];
		}
		
		// Try to get the display name from indicator metadata
		if ($selectedIndicatorsWithMetadata) {
			const indicator = $selectedIndicatorsWithMetadata.find(ind => ind.id === columnName);
			if (indicator) {
				return indicator.name;
			}
		}
		
		// Fallback: Convert snake_case to Title Case
		return columnName
			.split('_')
			.map(word => word.charAt(0).toUpperCase() + word.slice(1))
			.join(' ');
	}
	
	// Function to determine if a column should be sticky (fixed position)
	function isStickyColumn(columnName: string): boolean {
		return ['geo_name', 'state_fips', 'year'].includes(columnName);
	}
	
	// Function to get column CSS classes
	function getColumnClasses(columnName: string): string {
		const baseClasses = 'px-4 py-3 text-left';
		
		if (isStickyColumn(columnName)) {
			let leftOffset = 'left-0';
			let minWidth = '';
			
			if (columnName === 'geo_name') {
				leftOffset = 'left-0';
				minWidth = 'min-w-[200px] w-[200px]';
			} else if (columnName === 'state_fips') {
				leftOffset = 'left-[200px]';
				minWidth = 'min-w-[120px] w-[120px]';
			} else if (columnName === 'year') {
				leftOffset = 'left-[320px]';
				minWidth = 'min-w-[80px] w-[80px]';
			}
			
			return `${baseClasses} ${minWidth} sticky ${leftOffset} bg-white border-r border-gray-200 z-10`;
		}
		
		return baseClasses;
	}
	
	// Function to get header CSS classes
	function getHeaderClasses(columnName: string): string {
		const baseClasses = 'px-4 py-3 text-left text-xs font-medium text-gray-500 uppercase tracking-wider border-b border-gray-200';
		
		if (isStickyColumn(columnName)) {
			let leftOffset = 'left-0';
			let minWidth = '';
			
			if (columnName === 'geo_name') {
				leftOffset = 'left-0';
				minWidth = 'min-w-[200px] w-[200px]';
			} else if (columnName === 'state_fips') {
				leftOffset = 'left-[200px]';
				minWidth = 'min-w-[120px] w-[120px]';
			} else if (columnName === 'year') {
				leftOffset = 'left-[320px]';
				minWidth = 'min-w-[80px] w-[80px]';
			}
			
			return `${baseClasses} ${minWidth} sticky ${leftOffset} bg-gray-50 border-r border-gray-200 z-20`;
		}
		
		return `${baseClasses} bg-gray-50`;
	}
</script>

<div class="bg-gradient-to-br from-white via-white to-teal-50/30 rounded-2xl shadow-floating border border-teal-200/30 backdrop-blur-sm">
	<div class="relative">
		<!-- Header -->
		<div class="px-6 py-5 border-b border-teal-200/40 bg-gradient-to-r from-white via-teal-50/20 to-white rounded-t-2xl">
			<div class="flex items-center space-x-3">
				<div class="w-10 h-10 rounded-xl bg-gradient-to-br from-teal-100 to-teal-200 flex items-center justify-center shadow-elegant">
					<svg class="w-5 h-5 text-teal-700" fill="none" stroke="currentColor" viewBox="0 0 24 24">
						<path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M3 10h18M3 14h18m-9-4v8m-7 0V4a1 1 0 011-1h12a1 1 0 011 1v16a1 1 0 01-1 1H4a1 1 0 01-1-1z"/>
					</svg>
				</div>
				<div>
					<h3 class="text-xl font-bold text-teal-900">Data Table</h3>
					<p class="text-sm text-teal-700 mt-0.5">
						{#if $isAnalysisReady}
							Showing data for {$currentSelectedIndicators.length} indicator{$currentSelectedIndicators.length !== 1 ? 's' : ''} 
							across {$currentYears.length} year{$currentYears.length !== 1 ? 's' : ''}
						{:else}
							Select indicators, geography level, and years to view data
						{/if}
					</p>
				</div>
			</div>
		</div>
		
		<!-- Content -->
		<div class="relative">
			<!-- Loading overlay -->
			{#if isLoading}
				<div 
					class="absolute inset-0 bg-white bg-opacity-90 backdrop-blur-sm flex items-center justify-center z-30"
					in:receive={{ key: 'loading' }}
					out:send={{ key: 'loading' }}
				>
					<LoadingSpinner 
						variant="ring" 
						size="lg" 
						color="primary" 
						text="Loading table data..." 
					/>
				</div>
			{/if}
			
			<!-- Error state -->
			{#if error}
				<div 
					in:receive={{ key: 'error' }}
					out:send={{ key: 'error' }}
				>
					<EmptyState 
						variant="error"
						title="Error Loading Data"
						description={error}
						actionText="Try Again"
						on:click={fetchTableData}
					/>
				</div>
			{/if}
			
			
			<!-- Selection prompt -->
			{#if !$isAnalysisReady && !isLoading}
				<EmptyState 
					variant="selection"
					title="Configure Your Analysis"
					description="Select indicators, geography level, and years to view the data table."
					actionText="Open Variable Selector"
					on:click={() => showVariableSelector.set(true)}
				/>
			{/if}
			
			<!-- Data table -->
			{#if !isLoading && !error && tableData.length > 0}
				<!-- Table controls -->
				<div class="px-6 py-4 border-b border-teal-200/40 bg-gradient-to-r from-teal-50/20 via-white/50 to-teal-50/20">
					<div class="flex flex-col sm:flex-row sm:items-center sm:justify-between gap-4">
						<!-- Search input -->
						<div class="flex-1 max-w-md">
							<div class="relative">
								<div class="absolute inset-y-0 left-0 pl-4 flex items-center pointer-events-none">
									<svg class="h-5 w-5 text-teal-500" fill="none" stroke="currentColor" viewBox="0 0 24 24">
										<path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M21 21l-6-6m2-5a7 7 0 11-14 0 7 7 0 0114 0z" />
									</svg>
								</div>
								<input
									type="text"
									bind:value={searchTerm}
									placeholder="Search by geography name..."
									class="block w-full pl-12 pr-12 py-3 bg-white/80 backdrop-blur-sm border border-teal-200/60 rounded-xl text-sm placeholder-teal-400 focus:outline-none focus:ring-2 focus:ring-teal-500 focus:border-teal-500 hover:bg-white hover:shadow-elegant transition-all duration-300 text-teal-800 font-medium"
								/>
								{#if searchTerm}
									<button
										on:click={() => searchTerm = ''}
										class="absolute inset-y-0 right-0 pr-4 flex items-center text-teal-400 hover:text-teal-600 transition-colors"
									>
										<svg class="h-5 w-5" fill="none" stroke="currentColor" viewBox="0 0 24 24">
											<path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M6 18L18 6M6 6l12 12" />
										</svg>
									</button>
								{/if}
							</div>
						</div>
						
						<!-- Export button -->
						<div class="flex items-center space-x-2">
							<Button
								variant="outline"
								size="sm"
								on:click={exportToCSV}
								disabled={filteredData.length === 0}
							>
								<svg class="w-4 h-4 mr-2" fill="none" stroke="currentColor" viewBox="0 0 24 24">
									<path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M12 10v6m0 0l-3-3m3 3l3-3m2 8H7a2 2 0 01-2-2V5a2 2 0 012-2h5.586a1 1 0 01.707.293l5.414 5.414a1 1 0 01.293.707V19a2 2 0 01-2 2z" />
								</svg>
								Export CSV
							</Button>
						</div>
					</div>
				</div>
				
				<div class="overflow-x-auto max-h-96">
					<table class="min-w-full divide-y divide-gray-200">
						<thead>
							<tr>
								{#each columns as column}
									<th class={getHeaderClasses(column)}>
										<button
											class="flex items-center space-x-1 hover:text-gray-700 focus:outline-none focus:text-gray-700 transition-colors group"
											on:click={() => handleSort(column)}
										>
											<span>{getColumnDisplayName(column)}</span>
											{#if sortColumn === column}
												{#if sortDirection === 'asc'}
													<svg class="w-4 h-4" fill="none" stroke="currentColor" viewBox="0 0 24 24">
														<path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M5 15l7-7 7 7" />
													</svg>
												{:else}
													<svg class="w-4 h-4" fill="none" stroke="currentColor" viewBox="0 0 24 24">
														<path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M19 9l-7 7-7-7" />
													</svg>
												{/if}
											{:else}
												<svg class="w-4 h-4 opacity-0 group-hover:opacity-50" fill="none" stroke="currentColor" viewBox="0 0 24 24">
													<path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M8 9l4-4 4 4m0 6l-4 4-4-4" />
												</svg>
											{/if}
										</button>
									</th>
								{/each}
							</tr>
						</thead>
						<tbody class="bg-white divide-y divide-gray-200">
							{#each filteredData as row, rowIndex}
								<tr class="hover:bg-gray-50 transition-colors">
									{#each columns as column}
										<td class={getColumnClasses(column)}>
											<span class="text-sm text-gray-900">
												{formatCellValue(row[column], column)}
											</span>
										</td>
									{/each}
								</tr>
							{/each}
						</tbody>
					</table>
				</div>
				
				<!-- Table footer with row count -->
				<div class="px-6 py-4 border-t border-teal-200/40 bg-gradient-to-r from-white via-teal-50/20 to-white rounded-b-2xl">
					<div class="flex items-center justify-between">
						<div class="flex items-center space-x-2">
							<div class="w-2 h-2 bg-teal-600 rounded-full"></div>
							<p class="text-sm font-medium text-teal-700">
								{#if searchTerm || sortColumn}
									Showing <strong class="text-teal-900">{filteredData.length}</strong> of <strong class="text-teal-900">{tableData.length}</strong> row{tableData.length !== 1 ? 's' : ''}
								{:else}
									Showing <strong class="text-teal-900">{tableData.length}</strong> row{tableData.length !== 1 ? 's' : ''}
								{/if}
							</p>
						</div>
						
						{#if searchTerm || sortColumn}
							<button
								on:click={() => { searchTerm = ''; sortColumn = null; }}
								class="text-sm text-teal-600 hover:text-teal-800 font-semibold bg-white/60 backdrop-blur-sm border border-teal-200/60 rounded-lg px-3 py-1.5 hover:bg-white hover:shadow-elegant transition-all duration-300"
							>
								<svg class="w-3 h-3 mr-1.5 inline" fill="none" stroke="currentColor" viewBox="0 0 24 24">
									<path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M6 18L18 6M6 6l12 12"/>
								</svg>
								Clear filters
							</button>
						{/if}
					</div>
				</div>
			{/if}
		</div>
	</div>
</div>
