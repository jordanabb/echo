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

	// Pagination state
	let currentPage = 1;
	let pageSize = 100;
	let totalRows = 0;
	$: startRow = (currentPage - 1) * pageSize + 1;
	$: endRow = Math.min(currentPage * pageSize, totalRows);
	$: totalPages = Math.ceil(totalRows / pageSize);
	
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
	
	// Function to fetch geo_ids using the lightweight endpoint (no geometry data)
	async function fetchGeoIds(geoLevel: string, year: number, stateFilter?: string[]): Promise<string[]> {
		try {
			const params = new URLSearchParams({
				geo_level: geoLevel,
				year: year.toString()
			});
			if (stateFilter && stateFilter.length > 0) {
				params.set('state_filter', stateFilter.join(','));
			}
			const response = await fetch(`/api/geo-ids?${params}`);
			if (!response.ok) {
				throw new Error(`Failed to fetch geo_ids: ${response.statusText}`);
			}
			return await response.json();
		} catch (err) {
			console.error('Error fetching geo_ids:', err);
			return [];
		}
	}
	
	// Cached geo_ids to avoid re-fetching on page changes
	let cachedGeoIds: string[] = [];
	let cachedGeoKey = '';

	async function getGeoIds(): Promise<string[]> {
		const key = `${$currentGeoLevel}-${($currentGeoFilter || []).join(',')}-${$currentYears.join(',')}`;
		if (key === cachedGeoKey && cachedGeoIds.length > 0) {
			return cachedGeoIds;
		}

		const allGeoIds = new Set<string>();
		for (const year of $currentYears) {
			const yearGeoIds = await fetchGeoIds($currentGeoLevel, year, $currentGeoFilter);
			yearGeoIds.forEach(id => allGeoIds.add(id));
		}

		cachedGeoIds = Array.from(allGeoIds);
		cachedGeoKey = key;
		return cachedGeoIds;
	}

	// Function to fetch table data from API
	async function fetchTableData(page?: number) {
		if (!$isAnalysisReady || !$currentGeoLevel) {
			return;
		}

		isLoading = true;
		error = null;

		try {
			const geoIds = await getGeoIds();

			if (geoIds.length === 0) {
				throw new Error('No geographic areas found for the selected filters');
			}

			const requestPayload: any = {
				geo_ids: geoIds,
				indicator_ids: $currentSelectedIndicators,
				years: $currentYears,
				geo_level: $currentGeoLevel,
				page: page ?? currentPage,
				page_size: pageSize,
				...(searchTerm.trim() ? { search: searchTerm.trim() } : {})
			};

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

			const result = await response.json();
			const data = result.data || [];
			totalRows = result.total || 0;

			if (data.length === 0) {
				tableData = [];
				filteredData = [];
				columns = [];
				return;
			}

			columns = Object.keys(data[0]);
			tableData = data;
			filteredData = data;

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

	function goToPage(page: number) {
		const maxPage = Math.max(1, Math.ceil(totalRows / pageSize));
		currentPage = Math.max(1, Math.min(page, maxPage));
		fetchTableData(currentPage);
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
		applySorting();
	}
	
	// Function to apply sorting (search is now server-side)
	function applySorting() {
		let result = [...tableData];

		if (sortColumn) {
			result.sort((a, b) => {
				const aVal = a[sortColumn];
				const bVal = b[sortColumn];

				if (aVal == null && bVal == null) return 0;
				if (aVal == null) return sortDirection === 'asc' ? 1 : -1;
				if (bVal == null) return sortDirection === 'asc' ? -1 : 1;

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
	
	// Function to export data to CSV — fetches ALL rows (no pagination)
	let isExporting = false;
	async function exportToCSV() {
		if (columns.length === 0) return;

		isExporting = true;
		try {
			const geoIds = await getGeoIds();
			const requestPayload = {
				geo_ids: geoIds,
				indicator_ids: $currentSelectedIndicators,
				years: $currentYears,
				geo_level: $currentGeoLevel
				// No page param → backend returns all rows
			};

			const response = await fetch('/api/table-data', {
				method: 'POST',
				headers: { 'Content-Type': 'application/json' },
				body: JSON.stringify(requestPayload)
			});

			if (!response.ok) throw new Error('Failed to fetch export data');

			const result = await response.json();
			const allData = result.data || [];
			if (allData.length === 0) return;

			const exportColumns = Object.keys(allData[0]);
			const headers = exportColumns.map(col => getColumnDisplayName(col));
			const csvContent = [
				headers.join(','),
				...allData.map((row: any) =>
					exportColumns.map(col => {
						const value = row[col];
						if (value == null) return '';
						const stringValue = String(value);
						if (stringValue.includes(',') || stringValue.includes('"') || stringValue.includes('\n')) {
							return `"${stringValue.replace(/"/g, '""')}"`;
						}
						return stringValue;
					}).join(',')
				)
			].join('\n');

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
		} catch (err) {
			console.error('CSV export error:', err);
		} finally {
			isExporting = false;
		}
	}
	
	// Reactive statement to apply sorting when data changes
	$: if (tableData.length > 0) {
		applySorting();
	}

	// Reactive statement to search server-side when searchTerm changes
	$: if (browser && $isAnalysisReady && searchTerm !== undefined) {
		currentPage = 1;
		debounceApiCall(() => fetchTableData(1), DEBOUNCE_DELAY);
	}
	
	// Reactive statement to fetch data when analysis filters change — reset to page 1
	$: if (browser && $isAnalysisReady) {
		currentPage = 1;
		debounceApiCall(() => fetchTableData(1), DEBOUNCE_DELAY);
	}

	// Additional reactive statements to ensure data updates when individual filters change
	$: if (browser && $currentYears && $currentYears.length > 0 && $currentSelectedIndicators && $currentSelectedIndicators.length > 0 && $currentGeoLevel) {
		currentPage = 1;
		debounceApiCall(() => fetchTableData(1), DEBOUNCE_DELAY);
	}

	// Reactive statement to refetch data when state filter changes
	$: if (browser && $isAnalysisReady && $currentGeoFilter !== undefined) {
		currentPage = 1;
		debounceApiCall(() => fetchTableData(1), DEBOUNCE_DELAY);
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
		const baseClasses = 'px-2 md:px-4 py-2 md:py-3 text-left text-sm md:text-base';

		if (isStickyColumn(columnName)) {
			let leftOffset = 'left-0';
			let minWidth = '';

			if (columnName === 'geo_name') {
				leftOffset = 'left-0';
				minWidth = 'min-w-[120px] w-[120px] md:min-w-[200px] md:w-[200px]';
			} else if (columnName === 'state_fips') {
				leftOffset = 'left-[120px] md:left-[200px]';
				minWidth = 'min-w-[60px] w-[60px] md:min-w-[120px] md:w-[120px]';
			} else if (columnName === 'year') {
				leftOffset = 'left-[180px] md:left-[320px]';
				minWidth = 'min-w-[50px] w-[50px] md:min-w-[80px] md:w-[80px]';
			}

			return `${baseClasses} ${minWidth} sticky ${leftOffset} bg-white border-r border-neutral-200 z-10`;
		}

		return baseClasses;
	}

	// Function to get header CSS classes
	function getHeaderClasses(columnName: string): string {
		const baseClasses = 'px-2 md:px-4 py-2 md:py-3 text-left text-xs font-medium text-neutral-500 uppercase tracking-wider border-b border-neutral-200';

		if (isStickyColumn(columnName)) {
			let leftOffset = 'left-0';
			let minWidth = '';

			if (columnName === 'geo_name') {
				leftOffset = 'left-0';
				minWidth = 'min-w-[120px] w-[120px] md:min-w-[200px] md:w-[200px]';
			} else if (columnName === 'state_fips') {
				leftOffset = 'left-[120px] md:left-[200px]';
				minWidth = 'min-w-[60px] w-[60px] md:min-w-[120px] md:w-[120px]';
			} else if (columnName === 'year') {
				leftOffset = 'left-[180px] md:left-[320px]';
				minWidth = 'min-w-[50px] w-[50px] md:min-w-[80px] md:w-[80px]';
			}

			return `${baseClasses} ${minWidth} sticky ${leftOffset} bg-neutral-50 border-r border-neutral-200 z-20`;
		}

		return `${baseClasses} bg-neutral-50`;
	}
</script>

<div class="bg-gradient-to-br from-white via-white to-teal-50/30 rounded-2xl shadow-floating border border-teal-200/30 backdrop-blur-sm">
	<div class="relative">
		<!-- Header -->
		<div class="px-4 md:px-6 py-4 md:py-5 border-b border-neutral-200 bg-white rounded-t-2xl">
			<div class="flex items-center space-x-2 md:space-x-3">
				<div class="w-8 h-8 md:w-10 md:h-10 rounded-xl bg-teal-700 flex items-center justify-center flex-shrink-0">
					<svg class="w-4 h-4 md:w-5 md:h-5 text-white" fill="none" stroke="currentColor" viewBox="0 0 24 24">
						<path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M3 10h18M3 14h18m-9-4v8m-7 0V4a1 1 0 011-1h12a1 1 0 011 1v16a1 1 0 01-1 1H4a1 1 0 01-1-1z"/>
					</svg>
				</div>
				<div>
					<h3 class="text-xl font-bold text-neutral-900">Data Table</h3>
					<p class="text-sm text-neutral-600 mt-0.5">
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
				<div class="px-4 md:px-6 py-3 md:py-4 border-b border-teal-200/40 bg-gradient-to-r from-teal-50/20 via-white/50 to-teal-50/20">
					<div class="flex flex-col sm:flex-row sm:items-center sm:justify-between gap-3 md:gap-4">
						<!-- Search input -->
						<div class="flex-1 w-full sm:max-w-md">
							<div class="relative">
								<div class="absolute inset-y-0 left-0 pl-4 flex items-center pointer-events-none">
									<svg class="h-5 w-5 text-neutral-500" fill="none" stroke="currentColor" viewBox="0 0 24 24">
										<path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M21 21l-6-6m2-5a7 7 0 11-14 0 7 7 0 0114 0z" />
									</svg>
								</div>
								<input
									type="text"
									bind:value={searchTerm}
									placeholder="Search by geography name"
									class="block w-full pl-12 pr-12 py-3 bg-white border border-neutral-200 rounded-xl text-sm placeholder-neutral-400 focus:outline-none focus:ring-2 focus:ring-teal-500 focus:border-teal-700 hover:border-neutral-300 transition-all duration-300 text-neutral-800 font-medium"
								/>
								{#if searchTerm}
									<button
										on:click={() => searchTerm = ''}
										class="absolute inset-y-0 right-0 pr-4 flex items-center text-neutral-400 hover:text-neutral-600 transition-colors"
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
								disabled={totalRows === 0 || isExporting}
							>
								<svg class="w-4 h-4 mr-2" fill="none" stroke="currentColor" viewBox="0 0 24 24">
									<path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M12 10v6m0 0l-3-3m3 3l3-3m2 8H7a2 2 0 01-2-2V5a2 2 0 012-2h5.586a1 1 0 01.707.293l5.414 5.414a1 1 0 01.293.707V19a2 2 0 01-2 2z" />
								</svg>
								{isExporting ? 'Exporting...' : `Export CSV (${totalRows.toLocaleString()} rows)`}
							</Button>
						</div>
					</div>
				</div>
				
				<div class="overflow-x-auto max-h-96">
					<table class="min-w-full divide-y divide-neutral-200">
						<thead>
							<tr>
								{#each columns as column}
									<th class={getHeaderClasses(column)}>
										<button
											class="flex items-center space-x-1 hover:text-neutral-700 focus:outline-none focus:text-neutral-700 transition-colors group"
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
						<tbody class="bg-white divide-y divide-neutral-200">
							{#each filteredData as row, rowIndex}
								<tr class="hover:bg-neutral-50 transition-colors">
									{#each columns as column}
										<td class={getColumnClasses(column)}>
											<span class="text-sm text-neutral-900">
												{formatCellValue(row[column], column)}
											</span>
										</td>
									{/each}
								</tr>
							{/each}
						</tbody>
					</table>
				</div>
				
				<!-- Table footer with pagination -->
				<div class="px-4 md:px-6 py-3 md:py-4 border-t border-neutral-200 bg-white rounded-b-2xl">
					<div class="flex flex-col sm:flex-row items-center justify-between gap-3">
						<div class="flex items-center space-x-2">
							<div class="w-2 h-2 bg-teal-700 rounded-full"></div>
							<p class="text-sm font-medium text-neutral-600">
								{#if searchTerm}
									Showing <strong class="text-neutral-900">{startRow.toLocaleString()}</strong>–<strong class="text-neutral-900">{endRow.toLocaleString()}</strong> of <strong class="text-neutral-900">{totalRows.toLocaleString()}</strong> result{totalRows !== 1 ? 's' : ''} for "{searchTerm}"
								{:else}
									Showing <strong class="text-neutral-900">{startRow.toLocaleString()}</strong>–<strong class="text-neutral-900">{endRow.toLocaleString()}</strong> of <strong class="text-neutral-900">{totalRows.toLocaleString()}</strong> row{totalRows !== 1 ? 's' : ''}
								{/if}
							</p>
						</div>

						{#if totalRows > pageSize}
							<div class="flex items-center space-x-1">
								<button
									on:click={() => goToPage(1)}
									disabled={currentPage === 1}
									class="px-2 py-1.5 text-sm rounded-lg border border-neutral-200 hover:bg-neutral-50 disabled:opacity-40 disabled:cursor-not-allowed transition-colors"
									title="First page"
								>
									<svg class="w-4 h-4" fill="none" stroke="currentColor" viewBox="0 0 24 24">
										<path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M11 19l-7-7 7-7m8 14l-7-7 7-7" />
									</svg>
								</button>
								<button
									on:click={() => goToPage(currentPage - 1)}
									disabled={currentPage === 1}
									class="px-2 py-1.5 text-sm rounded-lg border border-neutral-200 hover:bg-neutral-50 disabled:opacity-40 disabled:cursor-not-allowed transition-colors"
									title="Previous page"
								>
									<svg class="w-4 h-4" fill="none" stroke="currentColor" viewBox="0 0 24 24">
										<path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M15 19l-7-7 7-7" />
									</svg>
								</button>

								<span class="px-3 py-1.5 text-sm font-medium text-neutral-700">
									{currentPage} / {totalPages.toLocaleString()}
								</span>

								<button
									on:click={() => goToPage(currentPage + 1)}
									disabled={currentPage === totalPages}
									class="px-2 py-1.5 text-sm rounded-lg border border-neutral-200 hover:bg-neutral-50 disabled:opacity-40 disabled:cursor-not-allowed transition-colors"
									title="Next page"
								>
									<svg class="w-4 h-4" fill="none" stroke="currentColor" viewBox="0 0 24 24">
										<path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M9 5l7 7-7 7" />
									</svg>
								</button>
								<button
									on:click={() => goToPage(totalPages)}
									disabled={currentPage === totalPages}
									class="px-2 py-1.5 text-sm rounded-lg border border-neutral-200 hover:bg-neutral-50 disabled:opacity-40 disabled:cursor-not-allowed transition-colors"
									title="Last page"
								>
									<svg class="w-4 h-4" fill="none" stroke="currentColor" viewBox="0 0 24 24">
										<path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M13 5l7 7-7 7M5 5l7 7-7 7" />
									</svg>
								</button>
							</div>
						{/if}

						{#if searchTerm || sortColumn}
							<button
								on:click={() => { searchTerm = ''; sortColumn = null; }}
								class="text-sm text-neutral-600 hover:text-neutral-800 font-semibold bg-white border border-neutral-200 rounded-lg px-3 py-1.5 hover:bg-neutral-50 transition-all duration-300"
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