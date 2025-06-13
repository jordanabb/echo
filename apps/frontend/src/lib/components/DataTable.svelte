<script lang="ts">
	import { onMount, onDestroy } from 'svelte';
	import { browser } from '$app/environment';
	import { 
		unifiedFilters,
		currentGeoLevel,
		currentYears,
		currentSelectedIndicators,
		selectedIndicatorsWithMetadata,
		isAnalysisReady
	} from '$lib/stores/unifiedFilters';
	import { crossfade } from 'svelte/transition';
	import { quintOut } from 'svelte/easing';
	import Card from './Card.svelte';
	import Button from './Button.svelte';
	
	// Component state
	let isLoading = false;
	let error: string | null = null;
	let tableData: any[] = [];
	let filteredData: any[] = [];
	let columns: string[] = [];
	let debounceTimer: NodeJS.Timeout | null = null;
	
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
	async function fetchGeoIds(geoLevel: string, year: number): Promise<string[]> {
		try {
			const params = new URLSearchParams({
				indicator: 'total_population', // Use a common indicator to get all geo_ids
				geo_level: geoLevel,
				year: year.toString()
			});
			
			const response = await fetch(`/api/map-view?${params}`);
			
			if (!response.ok) {
				throw new Error(`Failed to fetch geo_ids: ${response.statusText}`);
			}
			
			const data = await response.json();
			
			// Extract geo_ids from the response
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
				const yearGeoIds = await fetchGeoIds($currentGeoLevel, year);
				yearGeoIds.forEach(id => allGeoIds.add(id));
			}
			
			if (allGeoIds.size === 0) {
				throw new Error('No geographic areas found for the selected filters');
			}
			
			// Prepare the request payload
			const requestPayload = {
				geo_ids: Array.from(allGeoIds),
				indicator_ids: $currentSelectedIndicators,
				years: $currentYears
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
	
	// Reactive statement to apply filtering and sorting when data or filters change
	$: if (tableData.length > 0) {
		applySortingAndFiltering();
	}
	
	// Reset search and sorting when new data is loaded
	$: if (tableData.length > 0 && !isLoading) {
		// Reset filters when new data arrives
		if (searchTerm === '' && sortColumn === null) {
			filteredData = [...tableData];
		}
	}
	
	// Reactive statement to fetch data when analysis filters change
	$: if (browser && $isAnalysisReady) {
		debounceApiCall(fetchTableData, DEBOUNCE_DELAY);
	}
	
	// Clean up debounce timer on component destroy
	onDestroy(() => {
		if (debounceTimer) {
			clearTimeout(debounceTimer);
		}
	});
	
	// Function to format cell values
	function formatCellValue(value: any): string {
		if (value === null || value === undefined) {
			return '—';
		}
		
		if (typeof value === 'number') {
			// Format numbers with appropriate precision
			if (Number.isInteger(value)) {
				return value.toLocaleString();
			} else {
				return value.toLocaleString(undefined, { 
					minimumFractionDigits: 0, 
					maximumFractionDigits: 2 
				});
			}
		}
		
		return String(value);
	}
	
	// Function to get column header display name
	function getColumnDisplayName(columnName: string): string {
		// Convert snake_case to Title Case and handle special cases
		const specialCases: Record<string, string> = {
			'geo_id': 'Geography ID',
			'geo_name': 'Geography Name',
			'year': 'Year'
		};
		
		if (specialCases[columnName]) {
			return specialCases[columnName];
		}
		
		// Convert snake_case to Title Case
		return columnName
			.split('_')
			.map(word => word.charAt(0).toUpperCase() + word.slice(1))
			.join(' ');
	}
	
	// Function to determine if a column should be sticky (fixed position)
	function isStickyColumn(columnName: string): boolean {
		return ['geo_name', 'year'].includes(columnName);
	}
	
	// Function to get column CSS classes
	function getColumnClasses(columnName: string): string {
		const baseClasses = 'px-4 py-3 text-left';
		
		if (isStickyColumn(columnName)) {
			const leftOffset = columnName === 'geo_name' ? 'left-0' : 'left-48';
			return `${baseClasses} sticky ${leftOffset} bg-white border-r border-gray-200 z-10`;
		}
		
		return baseClasses;
	}
	
	// Function to get header CSS classes
	function getHeaderClasses(columnName: string): string {
		const baseClasses = 'px-4 py-3 text-left text-xs font-medium text-gray-500 uppercase tracking-wider border-b border-gray-200';
		
		if (isStickyColumn(columnName)) {
			const leftOffset = columnName === 'geo_name' ? 'left-0' : 'left-48';
			return `${baseClasses} sticky ${leftOffset} bg-gray-50 border-r border-gray-200 z-20`;
		}
		
		return `${baseClasses} bg-gray-50`;
	}
</script>

<Card variant="default" padding="none">
	<div class="relative">
		<!-- Header -->
		<div class="px-6 py-4 border-b border-gray-200">
			<h3 class="text-lg font-semibold text-gray-900">Data Table</h3>
			<p class="text-sm text-gray-600 mt-1">
				{#if $isAnalysisReady}
					Showing data for {$currentSelectedIndicators.length} indicator{$currentSelectedIndicators.length !== 1 ? 's' : ''} 
					across {$currentYears.length} year{$currentYears.length !== 1 ? 's' : ''}
				{:else}
					Select indicators, geography level, and years to view data
				{/if}
			</p>
		</div>
		
		<!-- Content -->
		<div class="relative">
			<!-- Loading overlay -->
			{#if isLoading}
				<div 
					class="absolute inset-0 bg-white bg-opacity-75 flex items-center justify-center z-30"
					in:receive={{ key: 'loading' }}
					out:send={{ key: 'loading' }}
				>
					<div class="flex items-center space-x-3">
						<div class="animate-spin rounded-full h-8 w-8 border-b-2 border-blue-600"></div>
						<span class="text-gray-700 font-medium">Loading table data...</span>
					</div>
				</div>
			{/if}
			
			<!-- Error state -->
			{#if error}
				<div 
					class="p-8 text-center"
					in:receive={{ key: 'error' }}
					out:send={{ key: 'error' }}
				>
					<div class="text-red-600 text-xl mb-2">⚠️</div>
					<h4 class="text-red-800 font-semibold mb-2">Error Loading Data</h4>
					<p class="text-red-700 text-sm mb-4">{error}</p>
					<button 
						class="px-4 py-2 bg-red-600 text-white rounded hover:bg-red-700 transition-colors"
						on:click={fetchTableData}
					>
						Retry
					</button>
				</div>
			{/if}
			
			<!-- No data state -->
			{#if !isLoading && !error && tableData.length === 0 && $isAnalysisReady}
				<div class="p-8 text-center">
					<div class="text-gray-400 text-xl mb-2">📊</div>
					<h4 class="text-gray-700 font-semibold mb-2">No Data Available</h4>
					<p class="text-gray-600 text-sm">
						No data available for this selection. Please try a different year or indicator.
					</p>
				</div>
			{/if}
			
			<!-- Selection prompt -->
			{#if !$isAnalysisReady && !isLoading}
				<div class="p-8 text-center">
					<div class="text-gray-400 text-xl mb-2">🔍</div>
					<h4 class="text-gray-700 font-semibold mb-2">Make Your Selection</h4>
					<p class="text-gray-600 text-sm">
						Please select indicators, geography level, and years to view the data table.
					</p>
				</div>
			{/if}
			
			<!-- Data table -->
			{#if !isLoading && !error && tableData.length > 0}
				<!-- Table controls -->
				<div class="px-6 py-4 border-b border-gray-200 bg-gray-50">
					<div class="flex flex-col sm:flex-row sm:items-center sm:justify-between gap-4">
						<!-- Search input -->
						<div class="flex-1 max-w-md">
							<div class="relative">
								<div class="absolute inset-y-0 left-0 pl-3 flex items-center pointer-events-none">
									<svg class="h-5 w-5 text-gray-400" fill="none" stroke="currentColor" viewBox="0 0 24 24">
										<path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M21 21l-6-6m2-5a7 7 0 11-14 0 7 7 0 0114 0z" />
									</svg>
								</div>
								<input
									type="text"
									bind:value={searchTerm}
									placeholder="Search by geography name..."
									class="block w-full pl-10 pr-3 py-2 border border-gray-300 rounded-md leading-5 bg-white placeholder-gray-500 focus:outline-none focus:placeholder-gray-400 focus:ring-1 focus:ring-blue-500 focus:border-blue-500 text-sm"
								/>
								{#if searchTerm}
									<button
										on:click={() => searchTerm = ''}
										class="absolute inset-y-0 right-0 pr-3 flex items-center"
									>
										<svg class="h-4 w-4 text-gray-400 hover:text-gray-600" fill="none" stroke="currentColor" viewBox="0 0 24 24">
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
												{formatCellValue(row[column])}
											</span>
										</td>
									{/each}
								</tr>
							{/each}
						</tbody>
					</table>
				</div>
				
				<!-- Table footer with row count -->
				<div class="px-6 py-3 border-t border-gray-200 bg-gray-50">
					<div class="flex items-center justify-between">
						<p class="text-sm text-gray-600">
							{#if searchTerm || sortColumn}
								Showing {filteredData.length} of {tableData.length} row{tableData.length !== 1 ? 's' : ''}
							{:else}
								Showing {tableData.length} row{tableData.length !== 1 ? 's' : ''}
							{/if}
						</p>
						
						{#if searchTerm || sortColumn}
							<button
								on:click={() => { searchTerm = ''; sortColumn = null; }}
								class="text-sm text-blue-600 hover:text-blue-800 font-medium"
							>
								Clear filters
							</button>
						{/if}
					</div>
				</div>
			{/if}
		</div>
	</div>
</Card>
