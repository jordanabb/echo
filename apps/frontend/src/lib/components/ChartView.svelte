<script lang="ts">
	import { onMount, onDestroy } from 'svelte';
	import { browser } from '$app/environment';
	import { 
		unifiedFilters,
		currentGeoLevel,
		currentPrimaryYear,
		currentYears,
		currentSelectedIndicators,
		selectedIndicatorsWithMetadata,
		isAnalysisReady
	} from '$lib/stores/unifiedFilters';
	import { crossfade } from 'svelte/transition';
	import { quintOut } from 'svelte/easing';
	import Card from './Card.svelte';
	import Button from './Button.svelte';
	import Chart from 'chart.js/auto';
	import 'chartjs-adapter-date-fns';
	
	// Ensure Chart.js is properly initialized
	if (browser) {
		Chart.defaults.responsive = true;
		Chart.defaults.maintainAspectRatio = false;
	}
	
	// Chart type definitions
	type ChartType = 'bar' | 'scatter' | 'line' | 'pie';
	
	interface ChartOption {
		id: ChartType;
		title: string;
		description: string;
		icon: string;
		useCase: string;
		disabled?: boolean;
	}
	
	// Chart options with guided descriptions
	const chartOptions: ChartOption[] = [
		{
			id: 'bar',
			title: 'Compare Values Across Geographies',
			description: 'Perfect for comparing indicator values between different locations',
			icon: '📊',
			useCase: 'Bar Chart'
		},
		{
			id: 'scatter',
			title: 'Explore Relationship Between Variables',
			description: 'Discover correlations and patterns between two indicators',
			icon: '🔍',
			useCase: 'Scatter Plot'
		},
		{
			id: 'line',
			title: 'Track Changes Over Time',
			description: 'Visualize trends and changes in indicators across years',
			icon: '📈',
			useCase: 'Line Chart'
		},
		{
			id: 'pie',
			title: 'Show Composition of a Whole',
			description: 'Display how parts contribute to the total (coming soon)',
			icon: '🥧',
			useCase: 'Pie Chart',
			disabled: true
		}
	];
	
	// Component state
	let selectedChartType: ChartType | null = null;
	let isLoading = false;
	let error: string | null = null;
	let chartData: any[] = [];
	let debounceTimer: NodeJS.Timeout | null = null;
	
	// Chart configuration state
	let xAxisVariable: string = '';
	let yAxisVariable: string = '';
	let colorVariable: string = '';
	let selectedYear: number | null = null;
	let selectedGeographies: string[] = [];
	
	// Available variables for chart configuration
	let availableVariables: string[] = [];
	let availableYears: number[] = [];
	let availableGeographies: string[] = [];
	
	// Chart.js instance and canvas reference
	let chartCanvas: HTMLCanvasElement;
	let chartInstance: Chart | null = null;
	
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
	
	// Function to handle chart type selection
	function selectChartType(chartType: ChartType) {
		selectedChartType = chartType;
		
		// Reset configuration when changing chart type
		xAxisVariable = '';
		yAxisVariable = '';
		colorVariable = '';
		selectedYear = null;
		selectedGeographies = [];
		
		// Set default configurations based on chart type
		if (chartType === 'bar' && availableVariables.length > 0) {
			xAxisVariable = 'geo_name';
			yAxisVariable = availableVariables[0];
		} else if (chartType === 'scatter' && availableVariables.length >= 2) {
			xAxisVariable = availableVariables[0];
			yAxisVariable = availableVariables[1];
		} else if (chartType === 'line' && availableVariables.length > 0) {
			xAxisVariable = 'year';
			yAxisVariable = availableVariables[0];
		}
		
		// Set default year if available
		if (availableYears.length > 0) {
			selectedYear = availableYears[availableYears.length - 1]; // Latest year
		}
	}
	
	// Function to go back to chart type selection
	function goBackToSelection() {
		selectedChartType = null;
		error = null;
		chartData = [];
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

	// Function to fetch chart data
	async function fetchChartData() {
		if (!$isAnalysisReady || !selectedChartType) {
			return;
		}
		
		isLoading = true;
		error = null;
		
		try {
			// First, get all geo_ids for the selected geography level and years
			const allGeoIds = new Set<string>();
			
			// Fetch geo_ids for each year (in case different years have different geographies)
			for (const year of selectedYear ? [selectedYear] : $currentYears) {
				const yearGeoIds = await fetchGeoIds($currentGeoLevel, year);
				yearGeoIds.forEach(id => allGeoIds.add(id));
			}
			
			if (allGeoIds.size === 0) {
				throw new Error('No geographic areas found for the selected filters');
			}
			
			// Prepare the request payload for table data API
			const requestPayload = {
				geo_ids: Array.from(allGeoIds),
				indicator_ids: $currentSelectedIndicators,
				years: selectedYear ? [selectedYear] : $currentYears
			};
			
			console.log('Fetching chart data with payload:', requestPayload);
			
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
				chartData = [];
				return;
			}
			
			console.log('Raw chart data received:', {
				rows: data.length,
				sampleRow: data[0],
				columns: Object.keys(data[0] || {}),
				xAxisVariable,
				yAxisVariable
			});
			
			// Transform the data based on chart type
			chartData = transformDataForChart(data, selectedChartType);
			
			console.log('Transformed chart data:', {
				chartType: selectedChartType,
				dataLength: chartData.length,
				sampleData: chartData.slice(0, 3)
			});
			
			// Render the chart after data is loaded
			if (chartCanvas && chartData.length > 0) {
				// Small delay to ensure canvas is properly mounted
				setTimeout(() => {
					renderChart();
				}, 100);
			}
			
		} catch (err) {
			console.error('Error fetching chart data:', err);
			error = err instanceof Error ? err.message : 'Failed to load chart data';
			chartData = [];
		} finally {
			isLoading = false;
		}
	}
	
	// Function to transform real API data for chart visualization
	function transformDataForChart(rawData: any[], chartType: ChartType): any[] {
		if (!rawData || rawData.length === 0) {
			return [];
		}
		
		console.log('Transforming data for chart type:', chartType, {
			rawDataLength: rawData.length,
			sampleRow: rawData[0],
			xAxisVariable,
			yAxisVariable,
			selectedYear
		});
		
		switch (chartType) {
			case 'bar':
				// For bar charts, group by geography and use the selected indicator
				if (xAxisVariable === 'geo_name' && yAxisVariable) {
					// Filter data for the selected year if specified
					let filteredData = rawData;
					if (selectedYear) {
						filteredData = rawData.filter(row => row.year === selectedYear);
					}
					
					// Group by geography and get the indicator value
					const geoMap = new Map();
					filteredData.forEach(row => {
						const geoName = row.geo_name || row.geo_id || 'Unknown';
						const indicatorValue = row[yAxisVariable];
						
						if (indicatorValue !== null && indicatorValue !== undefined) {
							// If multiple years, take the average or latest value
							if (geoMap.has(geoName)) {
								const existing = geoMap.get(geoName);
								geoMap.set(geoName, {
									label: geoName,
									value: (existing.value + indicatorValue) / 2,
									geo_id: row.geo_id,
									geo_name: geoName
								});
							} else {
								geoMap.set(geoName, {
									label: geoName,
									value: indicatorValue,
									geo_id: row.geo_id,
									geo_name: geoName
								});
							}
						}
					});
					
					return Array.from(geoMap.values()).slice(0, 20); // Limit to 20 for readability
				}
				break;
				
			case 'line':
				// For line charts, show trend over time for a specific geography or aggregate
				if (xAxisVariable === 'year' && yAxisVariable) {
					// Group by year and aggregate the indicator values
					const yearMap = new Map();
					rawData.forEach(row => {
						const year = row.year;
						const indicatorValue = row[yAxisVariable];
						
						if (year && indicatorValue !== null && indicatorValue !== undefined) {
							if (yearMap.has(year)) {
								const existing = yearMap.get(year);
								yearMap.set(year, {
									x: year,
									y: (existing.y + indicatorValue) / 2, // Average
									count: existing.count + 1
								});
							} else {
								yearMap.set(year, {
									x: year,
									y: indicatorValue,
									count: 1
								});
							}
						}
					});
					
					return Array.from(yearMap.values()).sort((a, b) => a.x - b.x);
				}
				break;
				
			case 'scatter':
				// For scatter plots, need two different indicators
				if (xAxisVariable && yAxisVariable && xAxisVariable !== yAxisVariable) {
					// Filter data for the selected year if specified
					let filteredData = rawData;
					if (selectedYear) {
						filteredData = rawData.filter(row => row.year === selectedYear);
					}
					
					// Group by geography and get both indicator values
					const geoMap = new Map();
					filteredData.forEach(row => {
						const geoKey = row.geo_id || row.geo_name;
						const geoName = row.geo_name || row.geo_id || 'Unknown';
						const xValue = parseFloat(row[xAxisVariable]);
						const yValue = parseFloat(row[yAxisVariable]);
						
						// Check if values are valid numbers
						if (!isNaN(xValue) && !isNaN(yValue) && isFinite(xValue) && isFinite(yValue)) {
							if (geoMap.has(geoKey)) {
								const existing = geoMap.get(geoKey);
								geoMap.set(geoKey, {
									x: (existing.x + xValue) / 2,
									y: (existing.y + yValue) / 2,
									label: geoName,
									geo_id: row.geo_id,
									geo_name: geoName
								});
							} else {
								geoMap.set(geoKey, {
									x: xValue,
									y: yValue,
									label: geoName,
									geo_id: row.geo_id,
									geo_name: geoName
								});
							}
						}
					});
					
					const scatterData = Array.from(geoMap.values()).slice(0, 50); // Limit for performance
					console.log('Scatter plot data points:', scatterData.length, 'Sample:', scatterData.slice(0, 5));
					return scatterData;
				}
				break;
				
			case 'pie':
				// For pie charts, group by geography and use the selected indicator
				if (yAxisVariable) {
					// Filter data for the selected year if specified
					let filteredData = rawData;
					if (selectedYear) {
						filteredData = rawData.filter(row => row.year === selectedYear);
					}
					
					// Group by geography and get the indicator value
					const geoMap = new Map();
					filteredData.forEach(row => {
						const geoName = row.geo_name || row.geo_id || 'Unknown';
						const indicatorValue = row[yAxisVariable];
						
						if (indicatorValue !== null && indicatorValue !== undefined && indicatorValue > 0) {
							if (geoMap.has(geoName)) {
								const existing = geoMap.get(geoName);
								geoMap.set(geoName, {
									label: geoName,
									value: existing.value + indicatorValue,
									geo_id: row.geo_id,
									geo_name: geoName
								});
							} else {
								geoMap.set(geoName, {
									label: geoName,
									value: indicatorValue,
									geo_id: row.geo_id,
									geo_name: geoName
								});
							}
						}
					});
					
					// Sort by value and take top 10 for pie chart
					return Array.from(geoMap.values())
						.sort((a, b) => b.value - a.value)
						.slice(0, 10);
				}
				break;
		}
		
		// Fallback: return empty array if transformation fails
		console.warn('Failed to transform data for chart type:', chartType);
		return [];
	}
	
	// Function to render the chart using Chart.js
	function renderChart() {
		if (!chartCanvas || !selectedChartType || chartData.length === 0) {
			console.warn('Cannot render chart:', {
				hasCanvas: !!chartCanvas,
				chartType: selectedChartType,
				dataLength: chartData.length,
				chartCanvas
			});
			return;
		}
		
		console.log('Rendering chart:', {
			type: selectedChartType,
			dataLength: chartData.length,
			sampleData: chartData.slice(0, 3),
			canvasElement: chartCanvas
		});
		
		// Destroy existing chart instance
		if (chartInstance) {
			console.log('Destroying existing chart instance');
			chartInstance.destroy();
			chartInstance = null;
		}
		
		const ctx = chartCanvas.getContext('2d');
		if (!ctx) {
			console.error('Failed to get 2D context from canvas');
			return;
		}
		
		// Configure chart based on type
		const chartConfig = getChartConfig(selectedChartType, chartData);
		console.log('Chart configuration:', chartConfig);
		
		try {
			// Create new chart instance
			chartInstance = new Chart(ctx, chartConfig);
			console.log('Chart instance created successfully:', chartInstance);
		} catch (err) {
			console.error('Error creating chart instance:', err);
			error = err instanceof Error ? err.message : 'Failed to create chart';
		}
	}
	
	// Function to get Chart.js configuration based on chart type
	function getChartConfig(chartType: ChartType, data: any[]) {
		const baseConfig = {
			responsive: true,
			maintainAspectRatio: false,
			plugins: {
				legend: {
					position: 'top' as const,
				},
				title: {
					display: true,
					text: `${getIndicatorDisplayName(yAxisVariable)} ${chartType === 'line' ? 'Over Time' : chartType === 'bar' ? 'by Geography' : 'Analysis'}`
				},
				tooltip: {
					backgroundColor: 'rgba(0, 0, 0, 0.8)',
					titleColor: 'white',
					bodyColor: 'white',
					borderColor: 'rgba(255, 255, 255, 0.2)',
					borderWidth: 1,
					cornerRadius: 6,
					displayColors: true,
					callbacks: {
						title: function(context: any) {
							const dataPoint = context[0];
							const dataIndex = dataPoint.dataIndex;
							
							// For different chart types, extract geography name differently
							switch (chartType) {
								case 'bar':
									// Use the geography name from the transformed data
									const barDataItem = data[dataIndex];
									return barDataItem?.geo_name || barDataItem?.label || 'Unknown Geography';
								case 'scatter':
									// Use the geography name from the transformed data
									const scatterDataItem = data[dataIndex];
									return scatterDataItem?.geo_name || scatterDataItem?.label || `Data Point ${dataIndex + 1}`;
								case 'line':
									return `Year ${dataPoint.parsed.x}`;
								case 'pie':
									// Use the geography name from the transformed data
									const pieDataItem = data[dataIndex];
									return pieDataItem?.geo_name || pieDataItem?.label || 'Unknown Geography';
								default:
									return dataPoint.label || 'Data Point';
							}
						},
						label: function(context: any) {
							const dataPoint = context.parsed;
							const labels = [];
							
							switch (chartType) {
								case 'bar':
									const cleanYAxisName = getIndicatorDisplayName(yAxisVariable);
									labels.push(`${cleanYAxisName}: ${dataPoint.y?.toLocaleString() || context.raw?.toLocaleString() || 'N/A'}`);
									break;
								case 'scatter':
									const cleanXAxisName = getIndicatorDisplayName(xAxisVariable);
									const cleanYAxisNameScatter = getIndicatorDisplayName(yAxisVariable);
									labels.push(`${cleanXAxisName}: ${dataPoint.x?.toLocaleString() || 'N/A'}`);
									labels.push(`${cleanYAxisNameScatter}: ${dataPoint.y?.toLocaleString() || 'N/A'}`);
									break;
								case 'line':
									const cleanYAxisNameLine = getIndicatorDisplayName(yAxisVariable);
									labels.push(`${cleanYAxisNameLine}: ${dataPoint.y?.toLocaleString() || context.raw?.toLocaleString() || 'N/A'}`);
									break;
								case 'pie':
									const percentage = ((context.raw / data.reduce((sum, item) => sum + item.value, 0)) * 100).toFixed(1);
									const cleanYAxisNamePie = getIndicatorDisplayName(yAxisVariable);
									labels.push(`${cleanYAxisNamePie}: ${context.raw?.toLocaleString() || 'N/A'}`);
									labels.push(`Percentage: ${percentage}%`);
									break;
								default:
									labels.push(`Value: ${context.raw?.toLocaleString() || 'N/A'}`);
							}
							
							return labels;
						}
					}
				}
			}
		};
		
		switch (chartType) {
			case 'bar':
				return {
					type: 'bar' as const,
					data: {
						labels: data.map(d => d.label),
						datasets: [{
							label: yAxisVariable,
							data: data.map(d => d.value),
							backgroundColor: 'rgba(59, 130, 246, 0.6)',
							borderColor: 'rgba(59, 130, 246, 1)',
							borderWidth: 1
						}]
					},
					options: {
						...baseConfig,
						scales: {
							y: {
								beginAtZero: true,
								title: {
									display: true,
									text: getIndicatorDisplayName(yAxisVariable)
								}
							},
							x: {
								title: {
									display: true,
									text: xAxisVariable === 'geo_name' ? 'Geography' : getIndicatorDisplayName(xAxisVariable)
								}
							}
						}
					}
				};
			
			case 'line':
				return {
					type: 'line' as const,
					data: {
						datasets: [{
							label: yAxisVariable,
							data: data,
							borderColor: 'rgba(59, 130, 246, 1)',
							backgroundColor: 'rgba(59, 130, 246, 0.1)',
							tension: 0.1
						}]
					},
					options: {
						...baseConfig,
						scales: {
							x: {
								type: 'linear' as const,
								title: {
									display: true,
									text: xAxisVariable === 'year' ? 'Year' : getIndicatorDisplayName(xAxisVariable)
								}
							},
							y: {
								beginAtZero: true,
								title: {
									display: true,
									text: getIndicatorDisplayName(yAxisVariable)
								}
							}
						}
					}
				};
			
			case 'scatter':
				// Ensure data points have numeric x and y values
				const validScatterData = data.filter(d => 
					typeof d.x === 'number' && 
					typeof d.y === 'number' && 
					!isNaN(d.x) && 
					!isNaN(d.y)
				);
				
				console.log('Scatter plot config - valid data points:', validScatterData.length);
				
				return {
					type: 'scatter' as const,
					data: {
						datasets: [{
							label: 'Data Points',
							data: validScatterData,
							backgroundColor: 'rgba(59, 130, 246, 0.6)',
							borderColor: 'rgba(59, 130, 246, 1)',
							borderWidth: 1,
							pointRadius: 5,
							pointHoverRadius: 7
						}]
					},
					options: {
						...baseConfig,
						scales: {
							x: {
								type: 'linear' as const,
								title: {
									display: true,
									text: getIndicatorDisplayName(xAxisVariable)
								}
							},
							y: {
								type: 'linear' as const,
								title: {
									display: true,
									text: getIndicatorDisplayName(yAxisVariable)
								}
							}
						}
					}
				};
			
			case 'pie':
				return {
					type: 'pie' as const,
					data: {
						labels: data.map(d => d.label),
						datasets: [{
							data: data.map(d => d.value),
							backgroundColor: [
								'rgba(59, 130, 246, 0.8)',
								'rgba(16, 185, 129, 0.8)',
								'rgba(245, 158, 11, 0.8)',
								'rgba(239, 68, 68, 0.8)',
								'rgba(139, 92, 246, 0.8)'
							],
							borderWidth: 2,
							borderColor: '#ffffff'
						}]
					},
					options: baseConfig
				};
			
			default:
				return {
					type: 'bar' as const,
					data: { labels: [], datasets: [] },
					options: baseConfig
				};
		}
	}
	
	// Function to get clean indicator name from metadata
	function getIndicatorDisplayName(indicatorId: string): string {
		const indicator = $selectedIndicatorsWithMetadata.find(ind => ind.id === indicatorId);
		return indicator ? indicator.name : indicatorId.replace(/_/g, ' ').replace(/\b\w/g, l => l.toUpperCase());
	}

	// Function to update available options based on analysis filters
	function updateAvailableOptions() {
		if (!$isAnalysisReady) {
			availableVariables = [];
			availableYears = [];
			availableGeographies = [];
			return;
		}
		
		// Use the actual indicator IDs as variable names for data access
		availableVariables = [...$currentSelectedIndicators];
		
		availableYears = [...$currentYears].sort((a, b) => a - b);
		
		// This would be populated from actual geography data
		availableGeographies = ['All Geographies']; // Placeholder
	}
	
	// Function to check if chart configuration is valid
	function isChartConfigValid(): boolean {
		if (!selectedChartType) return false;
		
		switch (selectedChartType) {
			case 'bar':
				return !!(xAxisVariable && yAxisVariable);
			case 'scatter':
				return !!(xAxisVariable && yAxisVariable && xAxisVariable !== yAxisVariable);
			case 'line':
				return !!(xAxisVariable && yAxisVariable);
			case 'pie':
				return !!(yAxisVariable);
			default:
				return false;
		}
	}
	
	// Function to get chart type specific instructions
	function getChartInstructions(chartType: ChartType): string {
		switch (chartType) {
			case 'bar':
				return 'Configure your bar chart to compare values across different geographies or categories.';
			case 'scatter':
				return 'Set up your scatter plot to explore relationships between two different indicators.';
			case 'line':
				return 'Configure your line chart to track how indicators change over time.';
			case 'pie':
				return 'Set up your pie chart to show how different parts contribute to the whole.';
			default:
				return 'Configure your chart settings below.';
		}
	}
	
	// Reactive statements
	$: if (browser && $isAnalysisReady) {
		updateAvailableOptions();
	}
	
	// Watch for changes in unified filters and trigger chart rerender
	$: if (browser && selectedChartType && isChartConfigValid()) {
		debounceApiCall(fetchChartData, DEBOUNCE_DELAY);
	}
	
	// Function to handle configuration changes and trigger rerender
	function handleConfigChange() {
		if (selectedChartType && isChartConfigValid()) {
			debounceApiCall(fetchChartData, DEBOUNCE_DELAY);
		}
	}
	
	// Clean up debounce timer and chart instance on component destroy
	onDestroy(() => {
		if (debounceTimer) {
			clearTimeout(debounceTimer);
		}
		if (chartInstance) {
			chartInstance.destroy();
		}
	});
</script>

<Card variant="default" padding="none">
	<div class="relative">
		<!-- Header -->
		<div class="px-6 py-4 border-b border-gray-200">
			<div class="flex items-center justify-between">
				<div>
					<h3 class="text-lg font-semibold text-gray-900">Chart Visualization</h3>
					<p class="text-sm text-gray-600 mt-1">
						{#if selectedChartType}
							Creating a {chartOptions.find(opt => opt.id === selectedChartType)?.useCase.toLowerCase()}
						{:else if $isAnalysisReady}
							Choose how you'd like to visualize your data
						{:else}
							Select indicators, geography level, and years to create charts
						{/if}
					</p>
				</div>
				
				{#if selectedChartType}
					<Button
						variant="outline"
						size="sm"
						on:click={goBackToSelection}
					>
						← Back to Chart Types
					</Button>
				{/if}
			</div>
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
						<span class="text-gray-700 font-medium">Generating chart...</span>
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
					<h4 class="text-red-800 font-semibold mb-2">Error Creating Chart</h4>
					<p class="text-red-700 text-sm mb-4">{error}</p>
					<button 
						class="px-4 py-2 bg-red-600 text-white rounded hover:bg-red-700 transition-colors"
						on:click={fetchChartData}
					>
						Retry
					</button>
				</div>
			{/if}
			
			<!-- Selection prompt -->
			{#if !$isAnalysisReady && !isLoading}
				<div class="p-8 text-center">
					<div class="text-gray-400 text-xl mb-2">📊</div>
					<h4 class="text-gray-700 font-semibold mb-2">Ready to Visualize</h4>
					<p class="text-gray-600 text-sm">
						Please select indicators, geography level, and years to start creating charts.
					</p>
				</div>
			{/if}
			
			<!-- Chart type selection -->
			{#if $isAnalysisReady && !selectedChartType}
				<div class="p-6">
					<div class="text-center mb-8">
						<h4 class="text-xl font-semibold text-gray-900 mb-2">
							How would you like to visualize your data?
						</h4>
						<p class="text-gray-600">
							Choose the visualization that best fits your analytical goal
						</p>
					</div>
					
					<div class="grid grid-cols-1 md:grid-cols-2 gap-6 max-w-4xl mx-auto">
						{#each chartOptions as option}
							<button
								class="p-6 border-2 border-gray-200 rounded-lg hover:border-blue-300 hover:bg-blue-50 transition-all duration-200 text-left group {option.disabled ? 'opacity-50 cursor-not-allowed' : 'cursor-pointer'}"
								on:click={() => !option.disabled && selectChartType(option.id)}
								disabled={option.disabled}
							>
								<div class="flex items-start space-x-4">
									<div class="text-3xl">{option.icon}</div>
									<div class="flex-1">
										<h5 class="text-lg font-semibold text-gray-900 mb-2 group-hover:text-blue-700">
											{option.title}
										</h5>
										<p class="text-sm text-gray-600 mb-3">
											{option.description}
										</p>
										<div class="inline-flex items-center text-sm font-medium text-blue-600">
											<span>{option.useCase}</span>
											{#if !option.disabled}
												<svg class="w-4 h-4 ml-1 group-hover:translate-x-1 transition-transform" fill="none" stroke="currentColor" viewBox="0 0 24 24">
													<path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M9 5l7 7-7 7" />
												</svg>
											{/if}
										</div>
									</div>
								</div>
							</button>
						{/each}
					</div>
				</div>
			{/if}
			
			<!-- Chart configuration -->
			{#if $isAnalysisReady && selectedChartType}
				<div class="p-6">
					<div class="grid grid-cols-1 lg:grid-cols-3 gap-8">
						<!-- Configuration Panel -->
						<div class="lg:col-span-1">
							<Card variant="outline">
								<div class="p-4">
									<h4 class="text-lg font-semibold text-gray-900 mb-3">
										Chart Configuration
									</h4>
									<p class="text-sm text-gray-600 mb-6">
										{getChartInstructions(selectedChartType)}
									</p>
									
									<div class="space-y-4">
										<!-- X-Axis Variable -->
										{#if selectedChartType !== 'pie'}
											<div>
												<label class="block text-sm font-medium text-gray-700 mb-2">
													X-Axis Variable
												</label>
												<select
													bind:value={xAxisVariable}
													on:change={handleConfigChange}
													class="block w-full px-3 py-2 border border-gray-300 rounded-md shadow-sm focus:outline-none focus:ring-blue-500 focus:border-blue-500 text-sm"
												>
													<option value="">Select variable...</option>
													{#if selectedChartType === 'bar'}
														<option value="geo_name">Geography Name</option>
													{/if}
													{#if selectedChartType === 'line'}
														<option value="year">Year</option>
													{/if}
													{#each availableVariables as variable}
														<option value={variable}>{getIndicatorDisplayName(variable)}</option>
													{/each}
												</select>
											</div>
										{/if}
										
										<!-- Y-Axis Variable -->
										<div>
											<label class="block text-sm font-medium text-gray-700 mb-2">
												{selectedChartType === 'pie' ? 'Value Variable' : 'Y-Axis Variable'}
											</label>
											<select
												bind:value={yAxisVariable}
												on:change={handleConfigChange}
												class="block w-full px-3 py-2 border border-gray-300 rounded-md shadow-sm focus:outline-none focus:ring-blue-500 focus:border-blue-500 text-sm"
											>
												<option value="">Select variable...</option>
												{#each availableVariables as variable}
													<option value={variable}>{getIndicatorDisplayName(variable)}</option>
												{/each}
											</select>
										</div>
										
										<!-- Color Variable (optional) -->
										{#if selectedChartType === 'scatter'}
											<div>
												<label class="block text-sm font-medium text-gray-700 mb-2">
													Color By (Optional)
												</label>
												<select
													bind:value={colorVariable}
													on:change={handleConfigChange}
													class="block w-full px-3 py-2 border border-gray-300 rounded-md shadow-sm focus:outline-none focus:ring-blue-500 focus:border-blue-500 text-sm"
												>
													<option value="">No color grouping</option>
													{#each availableVariables as variable}
														<option value={variable}>{variable}</option>
													{/each}
												</select>
											</div>
										{/if}
										
										<!-- Year Selection -->
										{#if selectedChartType !== 'line'}
											<div>
												<label class="block text-sm font-medium text-gray-700 mb-2">
													Year
												</label>
												<select
													bind:value={selectedYear}
													on:change={handleConfigChange}
													class="block w-full px-3 py-2 border border-gray-300 rounded-md shadow-sm focus:outline-none focus:ring-blue-500 focus:border-blue-500 text-sm"
												>
													<option value={null}>Select year...</option>
													{#each availableYears as year}
														<option value={year}>{year}</option>
													{/each}
												</select>
											</div>
										{/if}
									</div>
									
									<!-- Generate Chart Button -->
									<div class="mt-6">
										<Button
											variant="primary"
											size="sm"
											disabled={!isChartConfigValid()}
											on:click={fetchChartData}
										>
											Generate Chart
										</Button>
									</div>
								</div>
							</Card>
						</div>
						
						<!-- Chart Display Area -->
						<div class="lg:col-span-2">
							<Card variant="outline">
								<div class="p-4">
									<h4 class="text-lg font-semibold text-gray-900 mb-4">
										{chartOptions.find(opt => opt.id === selectedChartType)?.useCase}
									</h4>
									
									{#if !isChartConfigValid()}
										<div class="h-64 flex items-center justify-center bg-gray-50 rounded-lg border-2 border-dashed border-gray-300">
											<div class="text-center">
												<div class="text-gray-400 text-xl mb-2">📊</div>
												<p class="text-gray-600 text-sm">
													Configure your chart settings to see the visualization
												</p>
											</div>
										</div>
									{:else if chartData.length === 0 && !isLoading}
										<div class="h-64 flex items-center justify-center bg-gray-50 rounded-lg border-2 border-dashed border-gray-300">
											<div class="text-center">
												<div class="text-gray-400 text-xl mb-2">🎯</div>
												<p class="text-gray-600 text-sm">
													Click "Generate Chart" to create your visualization
												</p>
											</div>
										</div>
									{:else}
										<!-- Chart Canvas -->
										<div class="relative h-96 w-full">
											<canvas 
												bind:this={chartCanvas}
												class="w-full h-full"
												style="max-height: 384px;"
											></canvas>
										</div>
										{#if chartData.length > 0 && !chartInstance}
											<div class="mt-4 text-center text-sm text-amber-600">
												Chart data loaded but visualization not rendered. Check console for errors.
											</div>
										{/if}
									{/if}
								</div>
							</Card>
						</div>
					</div>
				</div>
			{/if}
		</div>
	</div>
</Card>
