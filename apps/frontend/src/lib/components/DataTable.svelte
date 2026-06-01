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
	import { apiUrl } from '$lib/api';
	import { crossfade } from 'svelte/transition';
	import { quintOut } from 'svelte/easing';
	import { formatValueByType } from '$lib/utils';
	import { indicators } from '$lib/stores/metadata';
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

	// State average reference rows
	let showStateAverage = false;
	let stateAverageData: any[] = [];
	
	// Sorting and filtering state
	let sortColumn: string | null = null;
	let sortDirection: 'asc' | 'desc' = 'asc';
	let searchTerm = '';

	// Value range filters: { [column]: { min?: number, max?: number } }
	let valueFilters: Record<string, { min?: number; max?: number }> = {};
	let filterPopoverColumn: string | null = null;
	let filterMinInput: string = '';
	let filterMaxInput: string = '';

	$: activeFilterCount = Object.keys(valueFilters).length;

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
			const response = await fetch(apiUrl(`/api/geo-ids?${params}`));
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

			// Build value_filters array from active filters
			const vfArray = Object.entries(valueFilters).map(([column, range]) => ({
				column,
				...(range.min !== undefined ? { min: range.min } : {}),
				...(range.max !== undefined ? { max: range.max } : {})
			}));

			const requestPayload: any = {
				geo_ids: geoIds,
				indicator_ids: $currentSelectedIndicators,
				years: $currentYears,
				geo_level: $currentGeoLevel,
				page: page ?? currentPage,
				page_size: pageSize,
				...(searchTerm.trim() ? { search: searchTerm.trim() } : {}),
				...(sortColumn ? { sort_column: sortColumn, sort_direction: sortDirection } : {}),
				...(vfArray.length > 0 ? { value_filters: vfArray } : {})
			};

			const response = await fetch(apiUrl('/api/table-data'), {
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

			columns = Object.keys(data[0]).filter(c => c !== 'geo_id');
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

	async function fetchStateAverages() {
		if (!$isAnalysisReady || !$currentGeoLevel || $currentGeoLevel === 'state') {
			stateAverageData = [];
			return;
		}
		try {
			const geoIds = await getGeoIds();
			if (geoIds.length === 0) return;
			const response = await fetch(apiUrl('/api/state-averages'), {
				method: 'POST',
				headers: { 'Content-Type': 'application/json' },
				body: JSON.stringify({
					geo_ids: geoIds,
					indicator_ids: $currentSelectedIndicators,
					years: $currentYears,
					geo_level: $currentGeoLevel
				})
			});
			if (!response.ok) throw new Error('Failed to fetch state averages');
			const result = await response.json();
			stateAverageData = result.data || [];
		} catch (err) {
			console.error('Error fetching state averages:', err);
			stateAverageData = [];
		}
	}

	$: if (showStateAverage && browser && $isAnalysisReady) {
		fetchStateAverages();
	}

	$: if (!showStateAverage) {
		stateAverageData = [];
	}

	function goToPage(page: number) {
		const maxPage = Math.max(1, Math.ceil(totalRows / pageSize));
		currentPage = Math.max(1, Math.min(page, maxPage));
		fetchTableData(currentPage);
	}
	
	// Function to handle sorting — re-fetches from server for global sort
	function handleSort(column: string) {
		if (sortColumn === column) {
			sortDirection = sortDirection === 'asc' ? 'desc' : 'asc';
		} else {
			sortColumn = column;
			sortDirection = 'asc';
		}

		currentPage = 1;
		fetchTableData(1);
	}

	// Filter popover helpers
	function isNumericColumn(column: string): boolean {
		return !['geo_name', 'state_fips', 'year', 'geo_id'].includes(column);
	}

	let filterPopoverPos = { top: 0, left: 0 };
	let popoverEl: HTMLElement | null = null;

	// Portal action: moves element to document.body so it escapes overflow/transform clipping
	function portal(node: HTMLElement) {
		document.body.appendChild(node);
		popoverEl = node;
		return {
			destroy() {
				if (node.parentNode) node.parentNode.removeChild(node);
				popoverEl = null;
			}
		};
	}

	function openFilterPopover(column: string, event: MouseEvent) {
		if (filterPopoverColumn === column) {
			closeFilterPopover();
			return;
		}
		const th = (event.currentTarget as HTMLElement).closest('th');
		if (th) {
			const rect = th.getBoundingClientRect();
			filterPopoverPos = { top: rect.bottom + 4, left: rect.left };
		}
		filterPopoverColumn = column;
		const existing = valueFilters[column];
		filterMinInput = existing?.min !== undefined ? String(existing.min) : '';
		filterMaxInput = existing?.max !== undefined ? String(existing.max) : '';
	}

	function closeFilterPopover() {
		filterPopoverColumn = null;
		filterMinInput = '';
		filterMaxInput = '';
	}

	function applyFilter() {
		if (!filterPopoverColumn) return;
		const minStr = String(filterMinInput ?? '').trim();
		const maxStr = String(filterMaxInput ?? '').trim();
		const min = minStr !== '' && !isNaN(Number(minStr)) ? Number(minStr) : undefined;
		const max = maxStr !== '' && !isNaN(Number(maxStr)) ? Number(maxStr) : undefined;

		if (min === undefined && max === undefined) {
			const { [filterPopoverColumn]: _, ...rest } = valueFilters;
			valueFilters = rest;
		} else {
			valueFilters = { ...valueFilters, [filterPopoverColumn]: { min, max } };
		}

		closeFilterPopover();
		currentPage = 1;
		fetchTableData(1);
	}

	function removeFilter(column: string) {
		const { [column]: _, ...rest } = valueFilters;
		valueFilters = rest;
		currentPage = 1;
		fetchTableData(1);
	}

	function clearAllFilters() {
		valueFilters = {};
		currentPage = 1;
		fetchTableData(1);
	}

	function handleFilterKeydown(e: KeyboardEvent) {
		if (e.key === 'Enter') applyFilter();
		if (e.key === 'Escape') closeFilterPopover();
	}
	
	// Function to export data to CSV — fetches ALL rows (no pagination)
	let isExporting = false;
	async function exportToCSV() {
		if (columns.length === 0) return;

		isExporting = true;
		try {
			const geoIds = await getGeoIds();
			const vfArray = Object.entries(valueFilters).map(([column, range]) => ({
				column,
				...(range.min !== undefined ? { min: range.min } : {}),
				...(range.max !== undefined ? { max: range.max } : {})
			}));
			const requestPayload: any = {
				geo_ids: geoIds,
				indicator_ids: $currentSelectedIndicators,
				years: $currentYears,
				geo_level: $currentGeoLevel,
				...(searchTerm.trim() ? { search: searchTerm.trim() } : {}),
				...(sortColumn ? { sort_column: sortColumn, sort_direction: sortDirection } : {}),
				...(vfArray.length > 0 ? { value_filters: vfArray } : {})
				// No page param → backend returns all rows
			};

			const response = await fetch(apiUrl('/api/table-data'), {
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
	
	// Reactive statement to search server-side when searchTerm changes
	$: if (browser && $isAnalysisReady && searchTerm !== undefined) {
		currentPage = 1;
		debounceApiCall(() => fetchTableData(1), DEBOUNCE_DELAY);
	}

	// Reactive statement to fetch data when analysis filters change — reset to page 1
	$: if (browser && $isAnalysisReady) {
		currentPage = 1;
		debounceApiCall(() => {
			fetchTableData(1);
			if (showStateAverage) fetchStateAverages();
		}, DEBOUNCE_DELAY);
	}

	// Additional reactive statements to ensure data updates when individual filters change
	$: if (browser && $currentYears && $currentYears.length > 0 && $currentSelectedIndicators && $currentSelectedIndicators.length > 0 && $currentGeoLevel) {
		currentPage = 1;
		debounceApiCall(() => {
			fetchTableData(1);
			if (showStateAverage) fetchStateAverages();
		}, DEBOUNCE_DELAY);
	}

	// Reactive statement to refetch data when state filter changes
	$: if (browser && $isAnalysisReady && $currentGeoFilter !== undefined) {
		currentPage = 1;
		debounceApiCall(() => {
			fetchTableData(1);
			if (showStateAverage) fetchStateAverages();
		}, DEBOUNCE_DELAY);
	}
	
	// Close filter popover on click outside (mousedown so it doesn't race with button click)
	function handleClickOutside(e: MouseEvent) {
		if (filterPopoverColumn && !(e.target as HTMLElement).closest('.filter-popover-anchor')) {
			closeFilterPopover();
		}
	}

	onMount(() => {
		document.addEventListener('mousedown', handleClickOutside);

		// Trigger initial data load if filters are already valid
		if ($isAnalysisReady) {
			fetchTableData(1);
		}

		return () => document.removeEventListener('mousedown', handleClickOutside);
	});

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
		const indicator = $selectedIndicatorsWithMetadata?.find(ind => ind.id === columnName)
			|| $indicators?.find(ind => ind.id === columnName);
		if (indicator) {
			indicatorName = indicator.name;
		}
		
		// Use the smart formatting function
		return formatValueByType(value, columnName, indicatorName);
	}
	
	// Function to get column header display name
	function getColumnDisplayName(columnName: string): string {
		// Handle special cases first
		const specialCases: Record<string, string> = {
			'geo_id': 'Geography ID',
			'geo_name': 'Name',
			'state_fips': 'State',
			'year': 'Year'
		};
		
		if (specialCases[columnName]) {
			return specialCases[columnName];
		}
		
		// Try to get the display name from indicator metadata
		const ind = $selectedIndicatorsWithMetadata?.find(i => i.id === columnName)
			|| $indicators?.find(i => i.id === columnName);
		if (ind) {
			return ind.name;
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
						
						<!-- Right controls -->
						<div class="flex items-center gap-3 flex-wrap">
							{#if $currentGeoLevel && $currentGeoLevel !== 'state'}
								<label class="flex items-center gap-2 cursor-pointer select-none text-sm text-neutral-700 font-medium">
									<input
										type="checkbox"
										bind:checked={showStateAverage}
										class="w-4 h-4 rounded border-neutral-300 text-teal-700 focus:ring-teal-500 cursor-pointer"
									/>
									Show state average
								</label>
							{/if}
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

				<!-- Active value filters bar -->
				{#if activeFilterCount > 0}
					<div class="px-4 md:px-6 py-2 border-b border-neutral-200 bg-white flex flex-wrap items-center gap-2">
						<span class="text-xs font-medium text-neutral-500">Filters:</span>
						{#each Object.entries(valueFilters) as [col, range]}
							<span class="inline-flex items-center gap-1 px-2 py-1 bg-neutral-50 border border-neutral-200 rounded-lg text-xs text-neutral-700">
								<span class="font-medium">{getColumnDisplayName(col)}</span>
								{#if range.min !== undefined && range.max !== undefined}
									{range.min} – {range.max}
								{:else if range.min !== undefined}
									&ge; {range.min}
								{:else if range.max !== undefined}
									&le; {range.max}
								{/if}
								<button
									on:click={() => removeFilter(col)}
									class="ml-0.5 text-neutral-400 hover:text-neutral-600"
								>
									<svg class="w-3 h-3" fill="none" stroke="currentColor" viewBox="0 0 24 24">
										<path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M6 18L18 6M6 6l12 12" />
									</svg>
								</button>
							</span>
						{/each}
						<button
							on:click={clearAllFilters}
							class="text-xs text-neutral-500 hover:text-neutral-700 underline ml-1"
						>
							Clear all
						</button>
					</div>
				{/if}
				
				<div class="overflow-x-auto max-h-96">
					<table class="min-w-full divide-y divide-neutral-200">
						<thead>
							<tr>
								{#each columns as column}
									<th class="{getHeaderClasses(column)} relative group">
										<div class="flex items-center space-x-1">
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
											{#if isNumericColumn(column)}
												<button
													on:click|stopPropagation={(e) => openFilterPopover(column, e)}
													class="filter-popover-anchor p-0.5 rounded hover:bg-neutral-200 transition-colors {valueFilters[column] ? 'text-amber-600' : 'text-neutral-400 opacity-0 group-hover:opacity-100'}"
													title="Filter values"
												>
													<svg class="w-3.5 h-3.5" fill="none" stroke="currentColor" viewBox="0 0 24 24">
														<path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M3 4a1 1 0 011-1h16a1 1 0 011 1v2.586a1 1 0 01-.293.707l-6.414 6.414a1 1 0 00-.293.707V17l-4 4v-6.586a1 1 0 00-.293-.707L3.293 7.293A1 1 0 013 6.586V4z" />
													</svg>
												</button>
											{/if}
										</div>
									</th>
								{/each}
							</tr>
						</thead>
						<tbody class="bg-white divide-y divide-neutral-200">
							{#if showStateAverage && stateAverageData.length > 0}
								{#each stateAverageData as avgRow}
									<tr class="bg-teal-50 border-l-2 border-teal-500">
										{#each columns as column}
											<td class="{getColumnClasses(column).replace('bg-white', 'bg-teal-50')}">
												{#if column === 'geo_name'}
													<span class="text-sm font-semibold text-teal-800 italic">State Avg</span>
												{:else}
													<span class="text-sm font-medium text-teal-900">
														{formatCellValue(avgRow[column] ?? null, column)}
													</span>
												{/if}
											</td>
										{/each}
									</tr>
								{/each}
								<tr class="h-0">
									<td colspan={columns.length} class="p-0 border-b-2 border-teal-200"></td>
								</tr>
							{/if}
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

						{#if searchTerm || sortColumn || activeFilterCount > 0}
							<button
								on:click={() => { searchTerm = ''; sortColumn = null; clearAllFilters(); }}
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

{#if filterPopoverColumn}
	<!-- svelte-ignore a11y-click-events-have-key-events -->
	<!-- svelte-ignore a11y-no-static-element-interactions -->
	<div
		use:portal
		class="filter-popover-anchor fixed bg-white border border-neutral-200 rounded-xl shadow-lg p-3 z-[9999] w-56"
		style="top: {filterPopoverPos.top}px; left: {filterPopoverPos.left}px; max-width: calc(100vw - {filterPopoverPos.left}px - 8px);"
		on:mousedown|stopPropagation
	>
		<div class="text-xs font-medium text-neutral-500 mb-2">Filter: {getColumnDisplayName(filterPopoverColumn)}</div>
		<div class="flex items-center gap-2 mb-2">
			<div class="flex-1">
				<label class="text-xs text-neutral-400">Min</label>
				<input
					type="text"
					inputmode="decimal"
					bind:value={filterMinInput}
					on:keydown={handleFilterKeydown}
					placeholder="No min"
					class="w-full px-2 py-1.5 text-sm border border-neutral-200 rounded-lg focus:outline-none focus:ring-1 focus:ring-teal-500"
				/>
			</div>
			<span class="text-neutral-300 mt-4">-</span>
			<div class="flex-1">
				<label class="text-xs text-neutral-400">Max</label>
				<input
					type="text"
					inputmode="decimal"
					bind:value={filterMaxInput}
					on:keydown={handleFilterKeydown}
					placeholder="No max"
					class="w-full px-2 py-1.5 text-sm border border-neutral-200 rounded-lg focus:outline-none focus:ring-1 focus:ring-teal-500"
				/>
			</div>
		</div>
		<div class="flex justify-between items-center">
			<button
				on:click={closeFilterPopover}
				class="text-xs text-neutral-500 hover:text-neutral-700"
			>
				Cancel
			</button>
			<div class="flex items-center gap-2">
				{#if filterPopoverColumn && valueFilters[filterPopoverColumn]}
					<button
						on:click={() => { if (filterPopoverColumn) { removeFilter(filterPopoverColumn); closeFilterPopover(); } }}
						class="text-xs text-red-500 hover:text-red-700"
					>
						Clear
					</button>
				{/if}
				<button
					on:click={applyFilter}
					class="text-xs font-medium text-white bg-teal-700 hover:bg-teal-800 px-3 py-1 rounded-lg transition-colors"
				>
					Apply
				</button>
			</div>
		</div>
	</div>
{/if}
</div>