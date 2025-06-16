<script lang="ts">
	import { onMount, onDestroy } from 'svelte';
	import { browser } from '$app/environment';
	import { 
		unifiedFilters,
		currentGeoLevel,
		currentGeoFilter,
		currentPrimaryYear,
		currentYears,
		currentSelectedIndicators,
		selectedIndicatorsWithMetadata,
		isAnalysisReady,
		setYears
	} from '$lib/stores/unifiedFilters';
	import { crossfade } from 'svelte/transition';
	import { quintOut } from 'svelte/easing';
	import { formatValueByType } from '$lib/utils';
	import Card from './Card.svelte';
	import Button from './Button.svelte';
	import GeographicUnitSelector from './GeographicUnitSelector.svelte';
	import YearSelector from './YearSelector.svelte';
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
			icon: 'M3 13h8V3H3v10zm0 8h8v-6H3v6zm10 0h8V11h-8v10zm0-18v6h8V3h-8z',
			useCase: 'Bar Chart'
		},
		{
			id: 'scatter',
			title: 'Explore Relationship Between Variables',
			description: 'Discover correlations and patterns between two indicators',
			icon: 'M12 2l3.09 6.26L22 9.27l-5 4.87 1.18 6.88L12 17.77l-6.18 3.25L7 14.14 2 9.27l6.91-1.01L12 2z',
			useCase: 'Scatter Plot'
		},
		{
			id: 'line',
			title: 'Track Changes Over Time',
			description: 'Visualize trends and changes in indicators across years',
			icon: 'M3 17l6-6 4 4 8-8',
			useCase: 'Line Chart'
		},
		{
			id: 'pie',
			title: 'Show Composition Breakdowns',
			description: 'Display revenue sources, student demographics, or community demographics as parts of a whole',
			icon: 'M21.21 15.89A10 10 0 118 2.83M22 12A10 10 0 0012 2v10z',
			useCase: 'Pie Chart'
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
	
	// Pie chart specific configuration
	type PieChartType = 'revenue' | 'student_demographics' | 'community_demographics';
	let selectedPieChartType: PieChartType | null = null;
	
	// Search functionality for scatter plot
	let searchTerm: string = '';
	let highlightedGeoId: string | null = null;
	let availableGeoUnitsForSearch: {geo_id: string, geo_name: string}[] = [];
	
	// Geographic unit selection for line charts
	let availableGeoUnits: {geo_id: string, geo_name: string}[] = [];
	let selectedGeoUnits: string[] = [];
	
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
		selectedGeoUnits = [];
		availableGeoUnits = [];
		selectedPieChartType = null;
		
		// Set default configurations based on chart type
		if (chartType === 'bar' && availableVariables.length > 0) {
			xAxisVariable = 'geo_name';
			yAxisVariable = availableVariables[0];
		} else if (chartType === 'scatter' && availableVariables.length >= 2) {
			xAxisVariable = availableVariables[0];
			yAxisVariable = availableVariables[1];
		} else if (chartType === 'line' && availableVariables.length > 0) {
			// For line charts, always use year as X-axis
			xAxisVariable = 'year';
			yAxisVariable = availableVariables[0];
		} else if (chartType === 'pie') {
			// For pie charts, set default to revenue breakdown
			selectedPieChartType = 'revenue';
		}
		
		// Set default year if available (not needed for line charts since they use all years)
		if (chartType !== 'line') {
			if (chartType === 'pie') {
				// For pie charts, always default to 2022 if no year is available
				selectedYear = 2022;
				// Update available years immediately for pie charts
				updateAvailableOptions();
			} else if (availableYears.length > 0) {
				selectedYear = availableYears[availableYears.length - 1]; // Latest year
			}
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
			// For pie charts, if no geo level is set, default to counties
			const effectiveGeoLevel = geoLevel || 'counties';
			
			const params = new URLSearchParams({
				indicator: 'total_population', // Use a common indicator to get all geo_ids
				geo_level: effectiveGeoLevel,
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

	// Function to get required indicators for pie chart types
	function getPieChartIndicators(pieChartType: PieChartType): string[] {
		switch (pieChartType) {
			case 'revenue':
				return ['federal_revenue_pp', 'state_revenue_pp', 'local_revenue_pp'];
			case 'student_demographics':
				return ['asian_students', 'black_students', 'latino_students', 'native_students', 'pacific_islander_students', 'two_or_more_races_students'];
			case 'community_demographics':
				return ['asian_population', 'black_population', 'native_population', 'pacific_islander_population', 'two_or_more_races_population', 'other_race_population'];
			default:
				return [];
		}
	}

	// Function to fetch chart data
	async function fetchChartData() {
		if (!selectedChartType) {
			return;
		}
		
		// For pie charts, we don't need isAnalysisReady since we fetch specific indicators
		if (selectedChartType !== 'pie' && !$isAnalysisReady) {
			return;
		}
		
		// Additional validation for pie charts
		if (selectedChartType === 'pie' && (!selectedPieChartType || !selectedYear)) {
			return;
		}
		
		isLoading = true;
		error = null;
		
		try {
			// First, get all geo_ids for the selected geography level and years
			const allGeoIds = new Set<string>();
			
			// For pie charts, ensure we have a valid year
			const yearsToFetch = selectedChartType === 'pie' && selectedYear 
				? [selectedYear] 
				: (selectedYear ? [selectedYear] : $currentYears);
			
			// Ensure we have at least one year
			if (yearsToFetch.length === 0) {
				// For pie charts, default to 2022 if no year is available
				if (selectedChartType === 'pie') {
					yearsToFetch.push(2022);
				} else {
					throw new Error('No year selected for chart generation');
				}
			}
			
			// Fetch geo_ids for each year (in case different years have different geographies)
			// For pie charts, use a default geo level if none is selected
			const geoLevelToUse = selectedChartType === 'pie' && !$currentGeoLevel ? 'counties' : $currentGeoLevel;
			
			for (const year of yearsToFetch) {
				const yearGeoIds = await fetchGeoIds(geoLevelToUse, year);
				yearGeoIds.forEach(id => allGeoIds.add(id));
			}
			
			if (allGeoIds.size === 0) {
				throw new Error('No geographic areas found for the selected filters');
			}
			
			// Determine which indicators to fetch
			let indicatorIds: string[];
			if (selectedChartType === 'pie' && selectedPieChartType) {
				indicatorIds = getPieChartIndicators(selectedPieChartType);
			} else {
				indicatorIds = $currentSelectedIndicators;
			}
			
			if (indicatorIds.length === 0) {
				throw new Error('No indicators available for the selected chart configuration');
			}
			
			// Prepare the request payload for table data API
			const requestPayload = {
				geo_ids: Array.from(allGeoIds),
				indicator_ids: indicatorIds,
				years: selectedChartType === 'pie' ? [selectedYear || 2022] : (selectedYear ? [selectedYear] : $currentYears)
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
				yAxisVariable,
				selectedPieChartType
			});
			
			// Extract available geographic units from the data
			if (selectedChartType === 'line') {
				const uniqueGeoUnits = [...new Map(
					data.map(row => [row.geo_id, {geo_id: row.geo_id, geo_name: row.geo_name}])
				).values()];
				availableGeoUnits = uniqueGeoUnits.sort((a, b) => a.geo_name.localeCompare(b.geo_name));
				
				// If no units are selected yet, select all by default
				if (selectedGeoUnits.length === 0) {
					selectedGeoUnits = availableGeoUnits.map(unit => unit.geo_id);
				}
			}
			
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
				// For line charts, show trend over time for selected geographic units
				if (xAxisVariable === 'year' && yAxisVariable) {
					// Filter data to only include selected geographic units
					const filteredData = rawData.filter(row => 
						selectedGeoUnits.length === 0 || selectedGeoUnits.includes(row.geo_id)
					);
					
					// Group by geographic unit and year
					const geoYearMap = new Map();
					filteredData.forEach(row => {
						const geoId = row.geo_id;
						const geoName = row.geo_name || geoId || 'Unknown';
						const year = row.year;
						const indicatorValue = row[yAxisVariable];
						
						if (year && indicatorValue !== null && indicatorValue !== undefined) {
							if (!geoYearMap.has(geoId)) {
								geoYearMap.set(geoId, {
									geo_id: geoId,
									geo_name: geoName,
									data: new Map()
								});
							}
							
							const geoData = geoYearMap.get(geoId);
							geoData.data.set(year, {
								x: year,
								y: indicatorValue
							});
						}
					});
					
					// Convert to array format for Chart.js with separate datasets per geographic unit
					const datasets = [];
					const colors = [
						'rgba(59, 130, 246, 1)',    // Blue
						'rgba(16, 185, 129, 1)',    // Green
						'rgba(245, 158, 11, 1)',    // Orange
						'rgba(239, 68, 68, 1)',     // Red
						'rgba(139, 92, 246, 1)',    // Purple
						'rgba(236, 72, 153, 1)',    // Pink
						'rgba(14, 165, 233, 1)',    // Sky
						'rgba(34, 197, 94, 1)',     // Emerald
						'rgba(251, 146, 60, 1)',    // Amber
						'rgba(168, 85, 247, 1)'     // Violet
					];
					
					let colorIndex = 0;
					for (const [geoId, geoInfo] of geoYearMap) {
						const sortedData = Array.from(geoInfo.data.values()).sort((a, b) => a.x - b.x);
						const color = colors[colorIndex % colors.length];
						
						datasets.push({
							label: geoInfo.geo_name,
							data: sortedData,
							borderColor: color,
							backgroundColor: color.replace('1)', '0.1)'),
							tension: 0.1,
							pointRadius: 4,
							pointHoverRadius: 6
						});
						
						colorIndex++;
					}
					
					return datasets;
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
					
					// Group by geography and get both indicator values - use geo_id as the primary key
					const geoMap = new Map();
					filteredData.forEach(row => {
						const geoId = row.geo_id;
						const geoName = row.geo_name || row.geo_id || 'Unknown';
						const xValue = parseFloat(row[xAxisVariable]);
						const yValue = parseFloat(row[yAxisVariable]);
						const colorValue = colorVariable ? parseFloat(row[colorVariable]) : null;
						
						// Only use geo_id as key to avoid duplicates, and only if we have valid data
						if (geoId && !isNaN(xValue) && !isNaN(yValue) && isFinite(xValue) && isFinite(yValue)) {
							// Take the first valid entry for each geo_id (no averaging to avoid confusion)
							if (!geoMap.has(geoId)) {
								geoMap.set(geoId, {
									x: xValue,
									y: yValue,
									colorValue: colorValue !== null && !isNaN(colorValue) ? colorValue : null,
									label: geoName,
									geo_id: geoId,
									geo_name: geoName
								});
							}
						}
					});
					
					const scatterData = Array.from(geoMap.values()).slice(0, 50); // Limit for performance
					
					// Update available geo units for search - ensure no duplicates
					const uniqueGeoUnits = new Map();
					scatterData.forEach(d => {
						if (d.geo_id && d.geo_name) {
							uniqueGeoUnits.set(d.geo_id, {
								geo_id: d.geo_id,
								geo_name: d.geo_name
							});
						}
					});
					availableGeoUnitsForSearch = Array.from(uniqueGeoUnits.values())
						.sort((a, b) => a.geo_name.localeCompare(b.geo_name));
					
					console.log('Scatter plot data points:', scatterData.length, 'Sample:', scatterData.slice(0, 5));
					console.log('Available geo units for search:', availableGeoUnitsForSearch.length);
					return scatterData;
				}
				break;
				
			case 'pie':
				// For pie charts, aggregate data based on the selected pie chart type
				if (selectedPieChartType && selectedYear) {
					// Filter data for the selected year
					const filteredData = rawData.filter(row => row.year === selectedYear);
					
					if (filteredData.length === 0) {
						return [];
					}
					
					// Get the indicators for this pie chart type
					const indicators = getPieChartIndicators(selectedPieChartType);
					
					// Aggregate values across all geographies for each indicator
					const aggregatedData = new Map();
					
					indicators.forEach(indicator => {
						let totalValue = 0;
						let validDataCount = 0;
						
						filteredData.forEach(row => {
							const value = row[indicator];
							if (value !== null && value !== undefined && !isNaN(value) && value >= 0) {
								totalValue += value;
								validDataCount++;
							}
						});
						
						if (validDataCount > 0) {
							// Get a clean display name for the indicator
							let displayName = indicator;
							switch (indicator) {
								case 'federal_revenue_pp':
									displayName = 'Federal Revenue';
									break;
								case 'state_revenue_pp':
									displayName = 'State Revenue';
									break;
								case 'local_revenue_pp':
									displayName = 'Local Revenue';
									break;
								case 'asian_students':
									displayName = 'Asian Students';
									break;
								case 'black_students':
									displayName = 'Black Students';
									break;
								case 'latino_students':
									displayName = 'Latino Students';
									break;
								case 'native_students':
									displayName = 'Native Students';
									break;
								case 'pacific_islander_students':
									displayName = 'Pacific Islander Students';
									break;
								case 'two_or_more_races_students':
									displayName = 'Two or More Races Students';
									break;
								case 'asian_population':
									displayName = 'Asian Population';
									break;
								case 'black_population':
									displayName = 'Black Population';
									break;
								case 'native_population':
									displayName = 'Native Population';
									break;
								case 'pacific_islander_population':
									displayName = 'Pacific Islander Population';
									break;
								case 'two_or_more_races_population':
									displayName = 'Two or More Races Population';
									break;
								case 'other_race_population':
									displayName = 'Other Race Population';
									break;
								default:
									displayName = indicator.replace(/_/g, ' ').replace(/\b\w/g, l => l.toUpperCase());
							}
							
							aggregatedData.set(indicator, {
								label: displayName,
								value: selectedPieChartType === 'revenue' ? totalValue : totalValue / validDataCount, // Average for percentages, sum for revenue
								indicator_id: indicator
							});
						}
					});
					
					// Convert to array and sort by value
					const result = Array.from(aggregatedData.values())
						.filter(item => item.value > 0)
						.sort((a, b) => b.value - a.value);
					
					console.log('Pie chart data transformation result:', {
						pieChartType: selectedPieChartType,
						indicators,
						result
					});
					
					return result;
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
					text: chartType === 'scatter' && xAxisVariable && yAxisVariable 
						? `${getIndicatorDisplayName(yAxisVariable)} vs ${getIndicatorDisplayName(xAxisVariable)}`
						: chartType === 'pie' && selectedPieChartType
							? selectedPieChartType === 'revenue' 
								? 'Per Pupil Revenue Breakdown'
								: selectedPieChartType === 'student_demographics'
									? 'Student Demographics Breakdown'
									: 'Community Demographics Breakdown'
							: `${getIndicatorDisplayName(yAxisVariable)} ${chartType === 'line' ? 'Over Time' : chartType === 'bar' ? 'by Geography' : 'Analysis'}`
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
								
								// For different chart types, extract geography name differently
								switch (chartType) {
									case 'bar':
										// Use the geography name from the transformed data
										const dataIndex = dataPoint.dataIndex;
										const barDataItem = data[dataIndex];
										return barDataItem?.geo_name || barDataItem?.label || 'Unknown Geography';
									case 'scatter':
										// For scatter plots, get the geo_name directly from the raw data point
										const rawDataPoint = dataPoint.raw;
										return rawDataPoint?.geo_name || rawDataPoint?.label || `Data Point ${dataPoint.dataIndex + 1}`;
									case 'line':
										return `Year ${dataPoint.parsed.x}`;
									case 'pie':
										// Use the geography name from the transformed data
										const pieDataIndex = dataPoint.dataIndex;
										const pieDataItem = data[pieDataIndex];
										return pieDataItem?.geo_name || pieDataItem?.label || 'Unknown Geography';
									default:
										return dataPoint.label || 'Data Point';
								}
							},
						label: function(context: any) {
							const dataPoint = context.parsed;
							const labels = [];
							
							// Helper function to format numbers using standardized formatting
							const formatNumber = (value: any, indicatorId?: string) => {
								if (value == null || isNaN(value)) return 'N/A';
								
								// Use standardized formatting if indicator ID is provided
								if (indicatorId) {
									const indicator = $selectedIndicatorsWithMetadata.find(ind => ind.id === indicatorId);
									const indicatorName = indicator ? indicator.name : '';
									return formatValueByType(value, indicatorId, indicatorName);
								}
								
								// Fallback to basic number formatting
								return Number(value).toLocaleString(undefined, { 
									minimumFractionDigits: 2, 
									maximumFractionDigits: 2 
								});
							};
							
							switch (chartType) {
								case 'bar':
									const cleanYAxisName = getIndicatorDisplayName(yAxisVariable);
									labels.push(`${cleanYAxisName}: ${formatNumber(dataPoint.y || context.raw, yAxisVariable)}`);
									break;
								case 'scatter':
									const cleanXAxisName = getIndicatorDisplayName(xAxisVariable);
									const cleanYAxisNameScatter = getIndicatorDisplayName(yAxisVariable);
									labels.push(`${cleanXAxisName}: ${formatNumber(dataPoint.x, xAxisVariable)}`);
									labels.push(`${cleanYAxisNameScatter}: ${formatNumber(dataPoint.y, yAxisVariable)}`);
									break;
								case 'line':
									const cleanYAxisNameLine = getIndicatorDisplayName(yAxisVariable);
									labels.push(`${cleanYAxisNameLine}: ${formatNumber(dataPoint.y || context.raw, yAxisVariable)}`);
									break;
								case 'pie':
									const percentage = ((context.raw / data.reduce((sum, item) => sum + item.value, 0)) * 100).toFixed(2);
									const pieDataItem = data[context.dataIndex];
									const indicatorId = pieDataItem?.indicator_id;
									const formattedValue = formatNumber(context.raw, indicatorId);
									
									labels.push(`Value: ${formattedValue}`);
									labels.push(`Share: ${percentage}%`);
									break;
								default:
									labels.push(`Value: ${formatNumber(context.raw)}`);
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
						datasets: data // data is already an array of datasets for line charts
					},
					options: {
						...baseConfig,
						scales: {
							x: {
								type: 'linear' as const,
								title: {
									display: true,
									text: xAxisVariable === 'year' ? 'Year' : getIndicatorDisplayName(xAxisVariable)
								},
								ticks: {
									stepSize: 1,
									callback: function(value: any) {
										// Format years as integers without decimals
										return Math.round(value).toString();
									}
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
				
				// Create datasets based on color variable
				let datasets = [];
				
				if (colorVariable && validScatterData.some(d => d.colorValue !== null && d.colorValue !== undefined)) {
					// Group by color variable value ranges
					const colorValues = validScatterData
						.filter(d => d.colorValue !== null && d.colorValue !== undefined)
						.map(d => d.colorValue);
					
					if (colorValues.length > 0) {
						const minColor = Math.min(...colorValues);
						const maxColor = Math.max(...colorValues);
						const range = maxColor - minColor;
						
						// Create 5 color groups
						const numGroups = Math.min(5, Math.max(2, Math.ceil(Math.sqrt(colorValues.length))));
						const groupSize = range / numGroups;
						
						const colors = [
							'rgba(59, 130, 246, 0.7)',    // Blue
							'rgba(16, 185, 129, 0.7)',    // Green
							'rgba(245, 158, 11, 0.7)',    // Orange
							'rgba(239, 68, 68, 0.7)',     // Red
							'rgba(139, 92, 246, 0.7)'     // Purple
						];
						
						for (let i = 0; i < numGroups; i++) {
							const groupMin = minColor + (i * groupSize);
							const groupMax = i === numGroups - 1 ? maxColor : minColor + ((i + 1) * groupSize);
							
							const groupData = validScatterData.filter(d => {
								if (d.colorValue === null || d.colorValue === undefined) return false;
								return d.colorValue >= groupMin && d.colorValue <= groupMax;
							});
							
							if (groupData.length > 0) {
								const color = colors[i % colors.length];
								datasets.push({
									label: `${getIndicatorDisplayName(colorVariable)}: ${groupMin.toFixed(1)} - ${groupMax.toFixed(1)}`,
									data: groupData.map(d => ({
										...d,
										backgroundColor: highlightedGeoId === d.geo_id ? 'rgba(245, 158, 11, 1)' : color,
										borderColor: highlightedGeoId === d.geo_id ? 'rgba(245, 158, 11, 1)' : color.replace('0.7)', '1)'),
										pointRadius: highlightedGeoId === d.geo_id ? 8 : 5,
										pointHoverRadius: highlightedGeoId === d.geo_id ? 10 : 7
									})),
									backgroundColor: color,
									borderColor: color.replace('0.7)', '1)'),
									borderWidth: 1,
									pointRadius: 5,
									pointHoverRadius: 7
								});
							}
						}
						
						// Add points without color values as a separate group
						const noColorData = validScatterData.filter(d => d.colorValue === null || d.colorValue === undefined);
						if (noColorData.length > 0) {
							datasets.push({
								label: 'No data',
								data: noColorData.map(d => ({
									...d,
									backgroundColor: highlightedGeoId === d.geo_id ? 'rgba(245, 158, 11, 1)' : 'rgba(156, 163, 175, 0.7)',
									borderColor: highlightedGeoId === d.geo_id ? 'rgba(245, 158, 11, 1)' : 'rgba(156, 163, 175, 1)',
									pointRadius: highlightedGeoId === d.geo_id ? 8 : 5,
									pointHoverRadius: highlightedGeoId === d.geo_id ? 10 : 7
								})),
								backgroundColor: 'rgba(156, 163, 175, 0.7)',
								borderColor: 'rgba(156, 163, 175, 1)',
								borderWidth: 1,
								pointRadius: 5,
								pointHoverRadius: 7
							});
						}
					}
				} else {
					// No color grouping - single dataset with highlighting
					datasets = [{
						label: 'Data Points',
						data: validScatterData.map(d => ({
							...d,
							backgroundColor: highlightedGeoId === d.geo_id ? 'rgba(245, 158, 11, 1)' : 'rgba(59, 130, 246, 0.6)',
							borderColor: highlightedGeoId === d.geo_id ? 'rgba(245, 158, 11, 1)' : 'rgba(59, 130, 246, 1)',
							pointRadius: highlightedGeoId === d.geo_id ? 8 : 5,
							pointHoverRadius: highlightedGeoId === d.geo_id ? 10 : 7
						})),
						backgroundColor: 'rgba(59, 130, 246, 0.6)',
						borderColor: 'rgba(59, 130, 246, 1)',
						borderWidth: 1,
						pointRadius: 5,
						pointHoverRadius: 7
					}];
				}
				
				return {
					type: 'scatter' as const,
					data: { datasets },
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
						},
						plugins: {
							...baseConfig.plugins,
							tooltip: {
								...baseConfig.plugins.tooltip,
								callbacks: {
									...baseConfig.plugins.tooltip.callbacks,
									title: function(context: any) {
										const dataPoint = context[0];
										// For scatter plots, get the geo_name directly from the raw data point
										const rawDataPoint = dataPoint.raw;
										return rawDataPoint?.geo_name || rawDataPoint?.label || `Data Point ${dataPoint.dataIndex + 1}`;
									},
									label: function(context: any) {
										const dataPoint = context.parsed;
										const rawDataPoint = context.raw;
										const labels = [];
										
										// Helper function to format numbers to 2 decimal places
										const formatNumber = (value: any) => {
											if (value == null || isNaN(value)) return 'N/A';
											return Number(value).toLocaleString(undefined, { 
												minimumFractionDigits: 2, 
												maximumFractionDigits: 2 
											});
										};
										
										const cleanXAxisName = getIndicatorDisplayName(xAxisVariable);
										const cleanYAxisName = getIndicatorDisplayName(yAxisVariable);
										labels.push(`${cleanXAxisName}: ${formatNumber(dataPoint.x)}`);
										labels.push(`${cleanYAxisName}: ${formatNumber(dataPoint.y)}`);
										
										if (colorVariable && rawDataPoint.colorValue !== null && rawDataPoint.colorValue !== undefined) {
											const cleanColorName = getIndicatorDisplayName(colorVariable);
											labels.push(`${cleanColorName}: ${formatNumber(rawDataPoint.colorValue)}`);
										}
										
										return labels;
									}
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
								'rgba(139, 92, 246, 0.8)',
								'rgba(236, 72, 153, 0.8)'
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
		// For pie charts, we use current years from unified filters or default years
		if (selectedChartType === 'pie') {
			availableYears = $currentYears.length > 0 
				? [...$currentYears].sort((a, b) => a - b)
				: [2020, 2021, 2022]; // Default years if none selected
			return;
		}
		
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
				return !!yAxisVariable; // Bar charts only need y variable, x is always geographic unit
			case 'scatter':
				return !!(xAxisVariable && yAxisVariable && xAxisVariable !== yAxisVariable);
			case 'line':
				return !!(xAxisVariable && yAxisVariable);
			case 'pie':
				return !!(selectedPieChartType && selectedYear);
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
	$: if (browser) {
		updateAvailableOptions();
	}
	
	// Watch for changes in unified filters and trigger chart rerender
	$: if (browser && selectedChartType && isChartConfigValid()) {
		debounceApiCall(fetchChartData, DEBOUNCE_DELAY);
	}
	
	// Additional reactive statements to ensure chart updates when filters change
	$: if (browser && selectedChartType && $currentSelectedIndicators) {
		updateAvailableOptions();
		if (isChartConfigValid()) {
			debounceApiCall(fetchChartData, DEBOUNCE_DELAY);
		}
	}
	
	$: if (browser && selectedChartType && $currentYears) {
		updateAvailableOptions();
		if (isChartConfigValid()) {
			debounceApiCall(fetchChartData, DEBOUNCE_DELAY);
		}
	}
	
	$: if (browser && selectedChartType && $currentGeoLevel) {
		updateAvailableOptions();
		if (isChartConfigValid()) {
			debounceApiCall(fetchChartData, DEBOUNCE_DELAY);
		}
	}
	
	$: if (browser && selectedChartType && $currentGeoFilter) {
		if (isChartConfigValid()) {
			debounceApiCall(fetchChartData, DEBOUNCE_DELAY);
		}
	}
	
	// Function to handle configuration changes and trigger rerender
	function handleConfigChange() {
		if (selectedChartType && isChartConfigValid()) {
			debounceApiCall(fetchChartData, DEBOUNCE_DELAY);
		}
	}
	
	// Function to handle search and highlighting
	function handleSearch() {
		if (!searchTerm.trim()) {
			highlightedGeoId = null;
			if (chartInstance) {
				renderChart(); // Re-render to remove highlighting
			}
			return;
		}
		
		// Find matching geographic unit
		const matchingUnit = availableGeoUnitsForSearch.find(unit => 
			unit.geo_name.toLowerCase().includes(searchTerm.toLowerCase()) ||
			unit.geo_id.toLowerCase().includes(searchTerm.toLowerCase())
		);
		
		if (matchingUnit) {
			highlightedGeoId = matchingUnit.geo_id;
			
			// Re-render chart with highlighting
			if (chartInstance) {
				renderChart();
				
				// Find the data point and trigger tooltip
				setTimeout(() => {
					if (chartInstance && selectedChartType === 'scatter') {
						const datasets = chartInstance.data.datasets;
						let pointIndex = -1;
						let datasetIndex = -1;
						
						// Find the highlighted point across all datasets
						for (let i = 0; i < datasets.length; i++) {
							const dataset = datasets[i];
							pointIndex = dataset.data.findIndex((point: any) => point.geo_id === highlightedGeoId);
							if (pointIndex !== -1) {
								datasetIndex = i;
								break;
							}
						}
						
						if (pointIndex !== -1 && datasetIndex !== -1) {
							// Show tooltip for the highlighted point
							chartInstance.tooltip.setActiveElements([{
								datasetIndex: datasetIndex,
								index: pointIndex
							}], {
								x: 0,
								y: 0
							});
							chartInstance.update('none');
						}
					}
				}, 100);
			}
		} else {
			highlightedGeoId = null;
			if (chartInstance) {
				renderChart(); // Re-render to remove highlighting
			}
		}
	}
	
	// Function to clear search
	function clearSearch() {
		searchTerm = '';
		highlightedGeoId = null;
		if (chartInstance) {
			renderChart(); // Re-render to remove highlighting
		}
	}
	
	// Filtered search results for dropdown
	$: filteredSearchResults = searchTerm.trim() 
		? availableGeoUnitsForSearch.filter(unit => 
			unit.geo_name.toLowerCase().includes(searchTerm.toLowerCase()) ||
			unit.geo_id.toLowerCase().includes(searchTerm.toLowerCase())
		).slice(0, 10) // Limit to 10 results
		: [];
	
	// Function to export chart as PNG
	function exportChartAsPNG() {
		if (!chartInstance || !chartCanvas) {
			console.error('No chart instance or canvas available for export');
			return;
		}
		
		try {
			// Get the chart as a base64 encoded PNG
			const url = chartInstance.toBase64Image('image/png', 1.0);
			
			// Create a temporary link element to trigger download
			const link = document.createElement('a');
			link.download = generateChartFileName();
			link.href = url;
			
			// Trigger the download
			document.body.appendChild(link);
			link.click();
			document.body.removeChild(link);
		} catch (error) {
			console.error('Error exporting chart:', error);
			// Fallback: try using canvas toDataURL directly
			try {
				const url = chartCanvas.toDataURL('image/png');
				const link = document.createElement('a');
				link.download = generateChartFileName();
				link.href = url;
				document.body.appendChild(link);
				link.click();
				document.body.removeChild(link);
			} catch (fallbackError) {
				console.error('Fallback export also failed:', fallbackError);
				alert('Failed to export chart. Please try again.');
			}
		}
	}
	
	// Function to generate a descriptive filename for the exported chart
	function generateChartFileName(): string {
		const timestamp = new Date().toISOString().slice(0, 19).replace(/:/g, '-');
		const chartTypeLabel = chartOptions.find(opt => opt.id === selectedChartType)?.useCase || 'Chart';
		
		let filename = `${chartTypeLabel.replace(/\s+/g, '_')}_${timestamp}`;
		
		// Add specific details based on chart type
		if (selectedChartType === 'pie' && selectedPieChartType) {
			const pieTypeLabel = selectedPieChartType.replace(/_/g, '_');
			filename = `${pieTypeLabel}_breakdown_${timestamp}`;
		} else if (selectedChartType === 'scatter' && xAxisVariable && yAxisVariable) {
			const xLabel = getIndicatorDisplayName(xAxisVariable).replace(/\s+/g, '_');
			const yLabel = getIndicatorDisplayName(yAxisVariable).replace(/\s+/g, '_');
			filename = `${yLabel}_vs_${xLabel}_${timestamp}`;
		} else if (selectedChartType === 'line' && yAxisVariable) {
			const yLabel = getIndicatorDisplayName(yAxisVariable).replace(/\s+/g, '_');
			filename = `${yLabel}_over_time_${timestamp}`;
		} else if (selectedChartType === 'bar' && yAxisVariable) {
			const yLabel = getIndicatorDisplayName(yAxisVariable).replace(/\s+/g, '_');
			filename = `${yLabel}_by_geography_${timestamp}`;
		}
		
		// Add year information if applicable
		if (selectedYear && selectedChartType !== 'line') {
			filename += `_${selectedYear}`;
		}
		
		return `${filename}.png`;
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

<div class="bg-gradient-to-br from-white via-white to-teal-50/30 rounded-2xl shadow-floating border border-teal-200/30 backdrop-blur-sm">
	<div class="relative">
		<!-- Header -->
		<div class="px-6 py-5 border-b border-teal-200/40 bg-gradient-to-r from-white via-teal-50/20 to-white rounded-t-2xl">
			<div class="flex items-center justify-between">
				<div class="flex items-center space-x-3">
					<div class="w-10 h-10 rounded-xl bg-gradient-to-br from-teal-100 to-teal-200 flex items-center justify-center shadow-elegant">
						<svg class="w-5 h-5 text-teal-700" fill="none" stroke="currentColor" viewBox="0 0 24 24">
							<path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M9 19v-6a2 2 0 00-2-2H5a2 2 0 00-2 2v6a2 2 0 002 2h2a2 2 0 002-2zm0 0V9a2 2 0 012-2h2a2 2 0 012 2v10m-6 0a2 2 0 002 2h2a2 2 0 002-2m0 0V5a2 2 0 012-2h2a2 2 0 012 2v14a2 2 0 01-2 2h-2a2 2 0 01-2-2z"/>
						</svg>
					</div>
					<div>
						<h3 class="text-xl font-bold text-teal-900">Chart Visualization</h3>
						<p class="text-sm text-teal-700 mt-0.5">
							{#if selectedChartType}
								Creating a {chartOptions.find(opt => opt.id === selectedChartType)?.useCase.toLowerCase()}
							{:else if $isAnalysisReady || selectedChartType === 'pie'}
								Choose how you'd like to visualize your data
							{:else}
								Select indicators, geography level, and years to create charts
							{/if}
						</p>
					</div>
				</div>
				
				{#if selectedChartType}
					<Button
						variant="outline"
						size="sm"
						on:click={goBackToSelection}
					>
						<svg class="w-4 h-4 mr-1.5" fill="none" stroke="currentColor" viewBox="0 0 24 24">
							<path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M10 19l-7-7m0 0l7-7m-7 7h18"/>
						</svg>
						Back to Chart Types
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
			{#if !$isAnalysisReady && selectedChartType !== 'pie' && !isLoading}
				<div class="p-8 text-center">
					<div class="text-gray-400 text-xl mb-2">📊</div>
					<h4 class="text-gray-700 font-semibold mb-2">Ready to Visualize</h4>
					<p class="text-gray-600 text-sm">
						Please select indicators, geography level, and years to start creating charts.
					</p>
				</div>
			{/if}
			
			<!-- Chart type selection -->
			{#if !selectedChartType}
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
								class="p-6 bg-white/80 backdrop-blur-sm border border-teal-200/60 rounded-xl hover:bg-white hover:shadow-luxury hover:border-teal-300 transition-all duration-300 text-left group {option.disabled ? 'opacity-50 cursor-not-allowed' : 'cursor-pointer'} shadow-elegant"
								on:click={() => !option.disabled && selectChartType(option.id)}
								disabled={option.disabled}
							>
								<div class="flex items-start space-x-4">
									<div class="w-12 h-12 rounded-xl bg-gradient-to-br from-teal-100 to-teal-200 flex items-center justify-center shadow-elegant group-hover:shadow-luxury transition-all duration-300">
										<svg class="w-6 h-6 text-teal-700" fill="currentColor" viewBox="0 0 24 24">
											<path d="{option.icon}"/>
										</svg>
									</div>
									<div class="flex-1">
										<h5 class="text-lg font-bold text-teal-900 mb-2 group-hover:text-teal-800">
											{option.title}
										</h5>
										<p class="text-sm text-teal-700 mb-3 leading-relaxed">
											{option.description}
										</p>
										<div class="inline-flex items-center text-sm font-semibold text-teal-600 bg-gradient-to-r from-teal-100 to-teal-200 px-3 py-1.5 rounded-full border border-teal-300/50">
											<span>{option.useCase}</span>
											{#if !option.disabled}
												<svg class="w-4 h-4 ml-2 group-hover:translate-x-1 transition-transform" fill="none" stroke="currentColor" viewBox="0 0 24 24">
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
			{#if (selectedChartType === 'pie' || $isAnalysisReady) && selectedChartType}
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
										<!-- Pie Chart Type Selection -->
										{#if selectedChartType === 'pie'}
											<div>
												<label class="block text-sm font-medium text-gray-700 mb-2">
													Pie Chart Type
												</label>
												<select
													bind:value={selectedPieChartType}
													on:change={handleConfigChange}
													class="block w-full px-3 py-2 border border-gray-300 rounded-md shadow-sm focus:outline-none focus:ring-blue-500 focus:border-blue-500 text-sm"
												>
													<option value="">Select breakdown type...</option>
													<option value="revenue">Per Pupil Revenue Breakdown</option>
													<option value="student_demographics">Student Demographics Breakdown</option>
													<option value="community_demographics">Community Demographics Breakdown</option>
												</select>
												<p class="text-xs text-gray-500 mt-1">
													{#if selectedPieChartType === 'revenue'}
														Shows federal, state, and local revenue per pupil
													{:else if selectedPieChartType === 'student_demographics'}
														Shows student population by race/ethnicity
													{:else if selectedPieChartType === 'community_demographics'}
														Shows community population by race/ethnicity
													{:else}
														Choose the type of breakdown to display
													{/if}
												</p>
											</div>
										{/if}
										
										<!-- X-Axis Variable (only shown for scatter charts) -->
										{#if selectedChartType === 'scatter'}
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
													{#each availableVariables as variable}
														<option value={variable}>{getIndicatorDisplayName(variable)}</option>
													{/each}
												</select>
											</div>
										{/if}
										
										<!-- Y-Axis Variable (hidden for pie charts since they use predefined indicators) -->
										{#if selectedChartType !== 'pie'}
											<div>
												<label class="block text-sm font-medium text-gray-700 mb-2">
													Y-Axis Variable
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
										{/if}
										
										<!-- Year Selection for Line Charts -->
										{#if selectedChartType === 'line'}
											<div>
												<label class="block text-sm font-medium text-gray-700 mb-2">
													Years to Display
												</label>
												<YearSelector
													selectedYears={$currentYears}
													mode="dropdown"
													placeholder="Select years for chart..."
													on:change={(event) => setYears(event.detail.selectedYears)}
												/>
												<p class="text-xs text-gray-500 mt-1">
													Line charts will show trends across the selected years
												</p>
											</div>
										{/if}

										<!-- Geographic Unit Selection for Line Charts -->
										{#if selectedChartType === 'line' && availableGeoUnits.length > 0}
											<div>
												<label class="block text-sm font-medium text-gray-700 mb-2">
													Geographic Units to Display
												</label>
												<GeographicUnitSelector
													availableUnits={availableGeoUnits}
													bind:selectedUnits={selectedGeoUnits}
													on:change={handleConfigChange}
													placeholder="Search geographic units..."
												/>
												<p class="text-xs text-gray-500 mt-1">
													Select which {$currentGeoLevel}s to show as separate lines on the chart
												</p>
											</div>
										{/if}
										
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
														<option value={variable}>{getIndicatorDisplayName(variable)}</option>
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
										<!-- Search Bar for Scatter Plot -->
										{#if selectedChartType === 'scatter' && availableGeoUnitsForSearch.length > 0}
											<div class="mb-4">
												<label class="block text-sm font-medium text-gray-700 mb-2">
													Search Geographic Units
												</label>
												<div class="relative">
													<input
														type="text"
														bind:value={searchTerm}
														on:input={handleSearch}
														placeholder="Search for a geographic unit..."
														class="block w-full px-3 py-2 pr-10 border border-gray-300 rounded-md shadow-sm focus:outline-none focus:ring-blue-500 focus:border-blue-500 text-sm"
													/>
													{#if searchTerm}
														<button
															type="button"
															on:click={clearSearch}
															class="absolute inset-y-0 right-0 pr-3 flex items-center"
														>
															<svg class="h-4 w-4 text-gray-400 hover:text-gray-600" fill="none" stroke="currentColor" viewBox="0 0 24 24">
																<path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M6 18L18 6M6 6l12 12" />
															</svg>
														</button>
													{/if}
													
													<!-- Search Results Dropdown -->
													{#if filteredSearchResults.length > 0}
														<div class="absolute z-50 mt-1 w-full bg-white shadow-lg max-h-60 rounded-md py-1 text-base ring-1 ring-black ring-opacity-5 overflow-auto focus:outline-none text-sm">
															{#each filteredSearchResults as unit}
																<button
																	type="button"
																	class="w-full text-left px-3 py-2 hover:bg-gray-50 focus:bg-gray-50 focus:outline-none"
																	on:click={() => {
																		searchTerm = unit.geo_name;
																		handleSearch();
																	}}
																>
																	<div class="flex justify-between items-center">
																		<span class="text-gray-900">{unit.geo_name}</span>
																		<span class="text-xs text-gray-500">{unit.geo_id}</span>
																	</div>
																</button>
															{/each}
														</div>
													{/if}
												</div>
												{#if highlightedGeoId}
													<p class="text-xs text-amber-600 mt-1">
														Highlighting: {availableGeoUnitsForSearch.find(u => u.geo_id === highlightedGeoId)?.geo_name || highlightedGeoId}
													</p>
												{/if}
											</div>
										{/if}
										
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
										
										<!-- Export Button -->
										{#if chartInstance && chartData.length > 0}
											<div class="mt-4 flex justify-end">
												<Button
													variant="outline"
													size="sm"
													on:click={exportChartAsPNG}
												>
													<svg class="w-4 h-4 mr-2" fill="none" stroke="currentColor" viewBox="0 0 24 24">
														<path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M4 16v1a3 3 0 003 3h10a3 3 0 003-3v-1m-4-4l-4 4m0 0l-4-4m4 4V4" />
													</svg>
													Export as PNG
												</Button>
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
</div>
