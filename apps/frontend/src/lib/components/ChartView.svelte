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
	import { crossfade, slide } from 'svelte/transition';
	import { quintOut } from 'svelte/easing';
	import { formatValueByType } from '$lib/utils';
	import { geographies } from '$lib/stores/metadata';
	import { showVariableSelector } from '$lib/stores/interactiveSteps';
	import { getStateNameByCode } from '$lib/constants/states';
	import Card from './Card.svelte';
	import Button from './Button.svelte';
	import GeographicUnitSelector from './GeographicUnitSelector.svelte';
	import YearSelector from './YearSelector.svelte';
	import LoadingSpinner from './LoadingSpinner.svelte';
	import Chart from 'chart.js/auto';
	import 'chartjs-adapter-date-fns';
	
	// Dynamically import zoom plugin to avoid SSR issues
	let zoomPlugin: any = null;
	
	// Ensure Chart.js is properly initialized
	if (browser) {
		Chart.defaults.responsive = true;
		Chart.defaults.maintainAspectRatio = false;
		
		// Dynamically import and register zoom plugin
		import('chartjs-plugin-zoom').then((module) => {
			zoomPlugin = module.default;
			Chart.register(zoomPlugin);
		}).catch((err) => {
			console.warn('Failed to load chartjs-plugin-zoom:', err);
		});
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
			title: 'Compare Values',
			description: 'Compare data values across different locations',
			icon: 'M3 13h8V3H3v10zm0 8h8v-6H3v6zm10 0h8V11h-8v10zm0-18v6h8V3h-8z',
			useCase: 'Bar Chart'
		},
		{
			id: 'scatter',
			title: 'See Relationships Between Variables',
			description: 'Discover correlations and connections between two variables',
			icon: 'M3 21V3h18M6 16a1 1 0 100-2 1 1 0 000 2zM10 12a1 1 0 100-2 1 1 0 000 2zM14 8a1 1 0 100-2 1 1 0 000 2zM18 4a1 1 0 100-2 1 1 0 000 2z',
			useCase: 'Scatter Plot'
		},
		{
			id: 'line',
			title: 'Track Changes Over Time',
			description: 'See data trends and changes over multiple years',
			icon: 'M3 17l6-6 4 4 8-8',
			useCase: 'Line Chart'
		},
		{
			id: 'pie',
			title: 'Show Proportions',
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
	let thirdVariable: string = '';
	let thirdVariableMode: 'color' | 'size' | 'state' = 'color'; // Toggle between color, size, and state
	let selectedYear: number | null = null;
	let selectedGeographies: string[] = [];
	
	// Pie chart specific configuration
	type PieChartType = 'revenue' | 'student_demographics' | 'community_demographics';
	let selectedPieChartType: PieChartType | null = null;
	
	// Search functionality for scatter plot
	let searchTerm: string = '';
	let highlightedGeoId: string | null = null;
	let availableGeoUnitsForSearch: {geo_id: string, geo_name: string}[] = [];
	
	// Trend line functionality for scatter plot
	let showTrendLine: boolean = false;

	// Bar chart options
	let hideBarLabels: boolean = false;
	
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

	// Expanded view state
	let isExpanded = false;

	function toggleExpanded() {
		isExpanded = !isExpanded;
		// Resize chart repeatedly during the transition for smooth redraw
		const start = performance.now();
		const duration = 500;
		function resizeDuringTransition() {
			chartInstance?.resize();
			if (performance.now() - start < duration) {
				requestAnimationFrame(resizeDuringTransition);
			}
		}
		requestAnimationFrame(resizeDuringTransition);
	}
	
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
	async function selectChartType(chartType: ChartType) {
		selectedChartType = chartType;
		isExpanded = false;

		// Reset configuration when changing chart type
		xAxisVariable = '';
		yAxisVariable = '';
		thirdVariable = '';
		thirdVariableMode = 'color';
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
		
		// Fetch available geographic units for line, bar, and pie charts
		if ((chartType === 'line' || chartType === 'bar' || chartType === 'pie') && ($currentGeoLevel || chartType === 'pie')) {
			await fetchAvailableGeoUnits();
		}
		
		// Auto-generate chart if configuration is complete after setting defaults
		setTimeout(() => {
			if (isChartConfigValid()) {
				fetchChartData();
			}
		}, 100); // Small delay to ensure all variables are set
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
			// For pie charts, if no geo level is set, default to county
			const effectiveGeoLevel = geoLevel || 'county';
			
			const params = new URLSearchParams({
				geo_level: effectiveGeoLevel,
				year: year.toString()
			});
			
			// Apply state filter if one is selected
			if ($currentGeoFilter && $currentGeoFilter.length > 0) {
				params.set('state_filter', $currentGeoFilter.join(','));
			}
			
			// Use the geometries endpoint which properly filters by geo_level
			const response = await fetch(`/api/geometries?${params}`);
			
			if (!response.ok) {
				throw new Error(`Failed to fetch geo_ids: ${response.statusText}`);
			}
			
			const data = await response.json();
			
			// Extract geo_ids from the response - geometries endpoint ensures proper geo_level filtering
			const geoIds = data.geoJson?.features?.map((feature: any) => feature.properties?.geo_id) || [];
			
			return geoIds;
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

	// Function to fetch available geographic units for the current geo level
	async function fetchAvailableGeoUnits() {
		const geoLevel = $currentGeoLevel || (selectedChartType === 'pie' ? 'county' : null);
		if (!geoLevel) return;
		
		try {
			// Use the latest year from available years or current years
			const yearToUse = availableYears.length > 0 
				? availableYears[availableYears.length - 1] 
				: ($currentYears.length > 0 ? $currentYears[$currentYears.length - 1] : 2022);
			
			const params = new URLSearchParams({
				geo_level: geoLevel,
				year: yearToUse.toString()
			});
			
			// Apply state filter if one is selected
			if ($currentGeoFilter && $currentGeoFilter.length > 0) {
				params.set('state_filter', $currentGeoFilter.join(','));
			}
			
			console.log('Fetching available geo units with URL:', `/api/geometries?${params}`);
			const response = await fetch(`/api/geometries?${params}`);
			
			if (!response.ok) {
				throw new Error(`Failed to fetch geographic units: ${response.statusText}`);
			}
			
			const data = await response.json();
			
			// Extract geo units from the response
			if (data.geoJson?.features) {
				const units = data.geoJson.features.map((feature: any) => ({
					geo_id: feature.properties?.geo_id || '',
					geo_name: feature.properties?.geo_name || 'Unknown'
				}));
				
				// Sort by name
				availableGeoUnits = units.sort((a: any, b: any) => 
					a.geo_name.localeCompare(b.geo_name)
				);
				
				console.log(`Fetched ${availableGeoUnits.length} geographic units for ${$currentGeoLevel}`);
			}
		} catch (err) {
			console.error('Error fetching available geographic units:', err);
			availableGeoUnits = [];
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
			const geoLevelToUse = selectedChartType === 'pie' && !$currentGeoLevel ? 'county' : $currentGeoLevel;
			
			for (const year of yearsToFetch) {
				const yearGeoIds = await fetchGeoIds(geoLevelToUse, year);
				yearGeoIds.forEach(id => allGeoIds.add(id));
			}
			
			if (allGeoIds.size === 0) {
				throw new Error('No geographic areas found for the selected filters');
			}

			// For pie charts, filter to selected geo units if any are selected
			if (selectedChartType === 'pie' && selectedGeoUnits.length > 0) {
				const filteredIds = new Set(Array.from(allGeoIds).filter(id => selectedGeoUnits.includes(id)));
				allGeoIds.clear();
				filteredIds.forEach(id => allGeoIds.add(id));
				if (allGeoIds.size === 0) {
					throw new Error('No data found for the selected geographic units');
				}
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
			
			// Prepare the request payload for table data API with geo_level
			const requestPayload = {
				geo_ids: Array.from(allGeoIds),
				indicator_ids: indicatorIds,
				years: selectedChartType === 'pie' ? [selectedYear || 2022] : (selectedYear ? [selectedYear] : $currentYears),
				geo_level: geoLevelToUse  // Add geo_level to filter out mixed geographic levels
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
			
			const result = await response.json();
			const data = result.data || result;

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
			
			// Don't extract geographic units from table data - we already have them from fetchGeoIds
			// This ensures we only show units that match the selected geographic level
			
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
					
					// Filter data to only include selected geographic units if any are selected
					if (selectedGeoUnits.length > 0) {
						filteredData = filteredData.filter(row => selectedGeoUnits.includes(row.geo_id));
					}
					
					// Group by geography and get the indicator value
					const geoMap = new Map();
					filteredData.forEach(row => {
						const geoName = row.geo_name || row.geo_id || 'Unknown';
						const indicatorValue = parseFloat(row[yAxisVariable]);

						if (!isNaN(indicatorValue)) {
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
					
					// If no geographic units are selected, limit to 20 for readability
					// If specific units are selected, show all of them
					const resultData = Array.from(geoMap.values());

					// Update available geo units for search
					availableGeoUnitsForSearch = resultData
						.filter(d => d.geo_id && d.geo_name)
						.map(d => ({ geo_id: d.geo_id, geo_name: d.geo_name }))
						.sort((a, b) => a.geo_name.localeCompare(b.geo_name));

					return selectedGeoUnits.length > 0 ? resultData : resultData.slice(0, 20);
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
						const indicatorValue = parseFloat(row[yAxisVariable]);

						if (year && !isNaN(indicatorValue)) {
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
						'#027272',  // Teal-70
						'#08ACA6',  // Teal-50
						'#035656',  // Teal-80
						'#6DDED1',  // Teal-30
						'#023A3E',  // Teal-90
						'#29CAC0',  // Teal-40
						'#068F8C',  // Teal-60
						'#ADEDE4',  // Teal-20
						'#011E20',  // Teal-100
						'#E4F7F4'   // Teal-10
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
					
					// Group by geo_id (not geo_name) to ensure unique points for each geographic unit
					const geoMap = new Map();
					filteredData.forEach(row => {
						const geoId = row.geo_id;
						const geoName = row.geo_name || row.geo_id || 'Unknown';
						
						// Derive state name from geo_id using FIPS code (first 2 digits)
						let stateName = 'Unknown State';
						if (geoId && typeof geoId === 'string' && geoId.length >= 2) {
							const stateFipsCode = geoId.substring(0, 2);
							const derivedStateName = getStateNameByCode(stateFipsCode);
							if (derivedStateName) {
								stateName = derivedStateName;
							}
						}
						
						const xValue = parseFloat(row[xAxisVariable]);
						const yValue = parseFloat(row[yAxisVariable]);
						const thirdValue = thirdVariable ? parseFloat(row[thirdVariable]) : null;
						
						// Use geo_id as the unique key to ensure each geographic unit gets one point
						if (geoId && !isNaN(xValue) && !isNaN(yValue) && isFinite(xValue) && isFinite(yValue)) {
							// Take the first valid entry for each geo_id (no averaging to avoid confusion)
							if (!geoMap.has(geoId)) {
								geoMap.set(geoId, {
									x: xValue,
									y: yValue,
									thirdValue: thirdValue !== null && !isNaN(thirdValue) ? thirdValue : null,
									label: geoName,
									geo_id: geoId,
									geo_name: geoName,
									state_name: stateName
								});
							}
						}
					});
					
					const scatterData = Array.from(geoMap.values()); // Remove artificial limit for census tracts
					
					// Update available geo units for search - ensure no duplicates by using geo_id as key
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
							const rawValue = row[indicator];
							const value = parseFloat(rawValue);
							if (!isNaN(value) && value >= 0) {
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
	
	// Function to calculate linear regression for trend line
	function calculateLinearRegression(data: any[]): {slope: number, intercept: number, r2: number} | null {
		if (!data || data.length < 2) return null;
		
		// Filter out invalid data points
		const validData = data.filter(d => 
			typeof d.x === 'number' && 
			typeof d.y === 'number' && 
			!isNaN(d.x) && 
			!isNaN(d.y) &&
			isFinite(d.x) &&
			isFinite(d.y)
		);
		
		if (validData.length < 2) return null;
		
		const n = validData.length;
		const sumX = validData.reduce((sum, d) => sum + d.x, 0);
		const sumY = validData.reduce((sum, d) => sum + d.y, 0);
		const sumXY = validData.reduce((sum, d) => sum + (d.x * d.y), 0);
		const sumXX = validData.reduce((sum, d) => sum + (d.x * d.x), 0);
		const sumYY = validData.reduce((sum, d) => sum + (d.y * d.y), 0);
		
		// Calculate slope and intercept
		const slope = (n * sumXY - sumX * sumY) / (n * sumXX - sumX * sumX);
		const intercept = (sumY - slope * sumX) / n;
		
		// Calculate R-squared
		const meanY = sumY / n;
		const totalSumSquares = sumYY - n * meanY * meanY;
		const residualSumSquares = validData.reduce((sum, d) => {
			const predicted = slope * d.x + intercept;
			return sum + Math.pow(d.y - predicted, 2);
		}, 0);
		const r2 = 1 - (residualSumSquares / totalSumSquares);
		
		return { slope, intercept, r2 };
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
										const geoName = rawDataPoint?.geo_name || rawDataPoint?.label || `Data Point ${dataPoint.dataIndex + 1}`;
										
										// Add state abbreviation to the title if available
										if (rawDataPoint?.state_name && rawDataPoint.state_name !== 'Unknown State') {
											// Convert state name to abbreviation
											const stateAbbrev = getStateAbbreviation(rawDataPoint.state_name);
											return stateAbbrev ? `${geoName}, ${stateAbbrev}` : geoName;
										}
										
										return geoName;
									case 'line':
										// For line charts, show the geographic unit name and year
										const datasetLabel = dataPoint.dataset.label;
										return `${datasetLabel} - ${dataPoint.parsed.x}`;
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
									const rawDataPoint = context.raw;
									
									const cleanXAxisName = getIndicatorDisplayName(xAxisVariable);
									const cleanYAxisNameScatter = getIndicatorDisplayName(yAxisVariable);
									labels.push(`${cleanXAxisName}: ${formatNumber(dataPoint.x, xAxisVariable)}`);
									labels.push(`${cleanYAxisNameScatter}: ${formatNumber(dataPoint.y, yAxisVariable)}`);
									
									if (thirdVariable && rawDataPoint.thirdValue !== null && rawDataPoint.thirdValue !== undefined) {
										const cleanThirdName = getIndicatorDisplayName(thirdVariable);
										labels.push(`${cleanThirdName}: ${formatNumber(rawDataPoint.thirdValue, thirdVariable)}`);
									}
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
							label: getIndicatorDisplayName(yAxisVariable),
							data: data.map(d => d.value),
							backgroundColor: data.map(d => highlightedGeoId && d.geo_id === highlightedGeoId ? 'rgba(245, 158, 11, 0.8)' : 'rgba(2, 114, 114, 0.6)'),
							borderColor: data.map(d => highlightedGeoId && d.geo_id === highlightedGeoId ? 'rgba(245, 158, 11, 1)' : 'rgba(2, 114, 114, 1)'),
							borderWidth: data.map(d => highlightedGeoId && d.geo_id === highlightedGeoId ? 2 : 1)
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
									display: xAxisVariable !== 'geo_name',
									text: xAxisVariable === 'geo_name' ? '' : getIndicatorDisplayName(xAxisVariable)
								},
								ticks: {
									display: !hideBarLabels
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
				
				// Create datasets based on third variable mode
				let datasets = [];

				if (thirdVariableMode === 'state') {
					// Group data points by state
					const stateGroups = new Map<string, any[]>();
					validScatterData.forEach(d => {
						const state = d.state_name || 'Unknown State';
						if (!stateGroups.has(state)) stateGroups.set(state, []);
						stateGroups.get(state)!.push(d);
					});

					// Distinct colors for states (up to 50+)
					const stateColors = [
						'rgba(2, 114, 114, 0.7)',    'rgba(220, 38, 38, 0.7)',
						'rgba(37, 99, 235, 0.7)',    'rgba(234, 88, 12, 0.7)',
						'rgba(22, 163, 74, 0.7)',    'rgba(147, 51, 234, 0.7)',
						'rgba(202, 138, 4, 0.7)',    'rgba(14, 165, 233, 0.7)',
						'rgba(219, 39, 119, 0.7)',   'rgba(101, 163, 13, 0.7)',
						'rgba(79, 70, 229, 0.7)',    'rgba(245, 158, 11, 0.7)',
						'rgba(6, 182, 212, 0.7)',    'rgba(225, 29, 72, 0.7)',
						'rgba(5, 150, 105, 0.7)',    'rgba(168, 85, 247, 0.7)',
						'rgba(249, 115, 22, 0.7)',   'rgba(59, 130, 246, 0.7)',
						'rgba(16, 185, 129, 0.7)',   'rgba(236, 72, 153, 0.7)',
						'rgba(132, 204, 22, 0.7)',   'rgba(99, 102, 241, 0.7)',
						'rgba(251, 146, 60, 0.7)',   'rgba(34, 211, 238, 0.7)',
						'rgba(244, 63, 94, 0.7)',    'rgba(52, 211, 153, 0.7)',
						'rgba(192, 132, 252, 0.7)',  'rgba(253, 186, 116, 0.7)',
						'rgba(56, 189, 248, 0.7)',   'rgba(251, 113, 133, 0.7)',
						'rgba(74, 222, 128, 0.7)',   'rgba(129, 140, 248, 0.7)',
						'rgba(253, 224, 71, 0.7)',   'rgba(103, 232, 249, 0.7)',
						'rgba(252, 165, 165, 0.7)',  'rgba(110, 231, 183, 0.7)',
						'rgba(196, 181, 253, 0.7)',  'rgba(254, 215, 170, 0.7)',
						'rgba(186, 230, 253, 0.7)',  'rgba(253, 164, 175, 0.7)',
						'rgba(187, 247, 208, 0.7)',  'rgba(165, 180, 252, 0.7)',
						'rgba(254, 240, 138, 0.7)',  'rgba(153, 246, 228, 0.7)',
						'rgba(254, 202, 202, 0.7)',  'rgba(167, 243, 208, 0.7)',
						'rgba(221, 214, 254, 0.7)',  'rgba(255, 228, 196, 0.7)',
						'rgba(191, 219, 254, 0.7)',  'rgba(252, 231, 243, 0.7)',
					];

					const sortedStates = Array.from(stateGroups.keys()).sort();
					sortedStates.forEach((state, i) => {
						const color = stateColors[i % stateColors.length];
						const stateData = stateGroups.get(state)!;
						datasets.push({
							label: state,
							data: stateData.map(d => ({
								...d,
								backgroundColor: highlightedGeoId === d.geo_id ? 'rgba(245, 158, 11, 1)' : color,
								borderColor: highlightedGeoId === d.geo_id ? 'rgba(245, 158, 11, 1)' : color.replace('0.7)', '1)'),
								pointRadius: highlightedGeoId === d.geo_id ? 8 : 4,
								pointHoverRadius: highlightedGeoId === d.geo_id ? 10 : 6
							})),
							backgroundColor: color,
							borderColor: color.replace('0.7)', '1)'),
							borderWidth: 1,
							pointRadius: 4,
							pointHoverRadius: 6
						});
					});
				} else if (thirdVariable && validScatterData.some(d => d.thirdValue !== null && d.thirdValue !== undefined)) {
					if (thirdVariableMode === 'color') {
						// Group by color variable values
						const colorValues = validScatterData
							.filter(d => d.thirdValue !== null && d.thirdValue !== undefined)
							.map(d => d.thirdValue);
						
						if (colorValues.length > 0) {
							const minColor = Math.min(...colorValues);
							const maxColor = Math.max(...colorValues);
							const range = maxColor - minColor;
							
							// Create 5 color groups
							const numGroups = Math.min(5, Math.max(2, Math.ceil(Math.sqrt(colorValues.length))));
							const groupSize = range / numGroups;
							
							const colors = [
								'rgba(2, 114, 114, 0.7)',     // Teal-70
								'rgba(8, 172, 166, 0.7)',     // Teal-50
								'rgba(6, 143, 140, 0.7)',     // Teal-60
								'rgba(41, 202, 192, 0.7)',    // Teal-40
								'rgba(109, 222, 209, 0.7)'    // Teal-30
							];
							
							for (let i = 0; i < numGroups; i++) {
								const groupMin = minColor + (i * groupSize);
								const groupMax = i === numGroups - 1 ? maxColor : minColor + ((i + 1) * groupSize);
								
								const groupData = validScatterData.filter(d => {
									if (d.thirdValue === null || d.thirdValue === undefined) return false;
									return d.thirdValue >= groupMin && d.thirdValue <= groupMax;
								});
								
								if (groupData.length > 0) {
									const color = colors[i % colors.length];
									datasets.push({
										label: `${getIndicatorDisplayName(thirdVariable)}: ${groupMin.toFixed(1)} - ${groupMax.toFixed(1)}`,
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
							
							// Add points without third variable values as a separate group
							const noThirdValueData = validScatterData.filter(d => d.thirdValue === null || d.thirdValue === undefined);
							if (noThirdValueData.length > 0) {
								datasets.push({
									label: 'No data',
									data: noThirdValueData.map(d => ({
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
					} else if (thirdVariableMode === 'size') {
						// Size by third variable - single dataset with varying point sizes
						const sizeValues = validScatterData
							.filter(d => d.thirdValue !== null && d.thirdValue !== undefined)
							.map(d => d.thirdValue);
						
						if (sizeValues.length > 0) {
							const minSize = Math.min(...sizeValues);
							const maxSize = Math.max(...sizeValues);
							const sizeRange = maxSize - minSize;
							
							// Calculate point sizes (3-15 pixel radius range)
							const minRadius = 3;
							const maxRadius = 15;
							const radiusRange = maxRadius - minRadius;
							
							// Calculate point sizes for each data point
							const dataWithSizes = validScatterData.map(d => {
								let pointRadius = 5; // Default size
								
								if (d.thirdValue !== null && d.thirdValue !== undefined && sizeRange > 0) {
									// Scale the size based on the third variable value
									const normalizedValue = (d.thirdValue - minSize) / sizeRange;
									pointRadius = minRadius + (normalizedValue * radiusRange);
								}
								
								return {
									...d,
									backgroundColor: highlightedGeoId === d.geo_id ? 'rgba(245, 158, 11, 0.7)' : 'rgba(2, 114, 114, 0.6)',
									borderColor: highlightedGeoId === d.geo_id ? 'rgba(245, 158, 11, 1)' : 'rgba(2, 114, 114, 1)',
									calculatedRadius: highlightedGeoId === d.geo_id ? pointRadius + 3 : pointRadius
								};
							});

							datasets = [{
								label: `Sized by ${getIndicatorDisplayName(thirdVariable)}`,
								data: dataWithSizes,
								backgroundColor: dataWithSizes.map(d => d.backgroundColor),
								borderColor: dataWithSizes.map(d => d.borderColor),
								pointRadius: dataWithSizes.map(d => d.calculatedRadius),
								pointHoverRadius: dataWithSizes.map(d => d.calculatedRadius + 2),
								borderWidth: 1
							}];
						}
					}
				} else {
					// No third variable - single dataset with highlighting
					datasets = [{
						label: 'Data Points',
						data: validScatterData.map(d => ({
							...d,
							backgroundColor: highlightedGeoId === d.geo_id ? 'rgba(245, 158, 11, 1)' : 'rgba(2, 114, 114, 0.6)',
							borderColor: highlightedGeoId === d.geo_id ? 'rgba(245, 158, 11, 1)' : 'rgba(2, 114, 114, 1)',
							pointRadius: highlightedGeoId === d.geo_id ? 8 : 5,
							pointHoverRadius: highlightedGeoId === d.geo_id ? 10 : 7
						})),
						backgroundColor: 'rgba(2, 114, 114, 0.6)',
						borderColor: 'rgba(2, 114, 114, 1)',
						borderWidth: 1,
						pointRadius: 5,
						pointHoverRadius: 7
					}];
				}
				
				// Add trend line if enabled
				if (showTrendLine && validScatterData.length >= 2) {
					const regression = calculateLinearRegression(validScatterData);
					if (regression) {
						// Calculate the range of x values to draw the trend line across
						const xValues = validScatterData.map(d => d.x);
						const minX = Math.min(...xValues);
						const maxX = Math.max(...xValues);
						
						// Generate trend line points
						const trendLineData = [
							{ x: minX, y: regression.slope * minX + regression.intercept },
							{ x: maxX, y: regression.slope * maxX + regression.intercept }
						];
						
						// Add trend line dataset
						datasets.push({
							label: `Trend Line (R² = ${regression.r2.toFixed(3)})`,
							data: trendLineData,
							type: 'line',
							borderColor: 'rgba(245, 158, 11, 1)', // Amber 500 for trend line
							backgroundColor: 'rgba(245, 158, 11, 0.1)',
							borderWidth: 2,
							pointRadius: 0,
							pointHoverRadius: 0,
							tension: 0,
							fill: false,
							order: 1 // Ensure trend line appears behind scatter points
						});
					}
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
							zoom: {
								limits: {
									x: {min: 'original', max: 'original'},
									y: {min: 'original', max: 'original'}
								},
								pan: {
									enabled: true,
									mode: 'xy',
									modifierKey: null
								},
								zoom: {
									wheel: {
										enabled: true,
										speed: 0.05, // Reduced zoom speed (default is 0.1)
									},
									pinch: {
										enabled: true
									},
									mode: 'xy',
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
								'rgba(2, 114, 114, 0.85)',    // Teal
								'rgba(220, 120, 50, 0.85)',   // Orange
								'rgba(90, 90, 170, 0.85)',    // Indigo
								'rgba(200, 70, 70, 0.85)',    // Red
								'rgba(60, 160, 80, 0.85)',    // Green
								'rgba(180, 140, 50, 0.85)',   // Gold
								'rgba(140, 70, 160, 0.85)',   // Purple
								'rgba(70, 150, 190, 0.85)',   // Sky blue
								'rgba(190, 90, 130, 0.85)',   // Rose
								'rgba(100, 130, 60, 0.85)'    // Olive
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

	// Function to convert state name to abbreviation
	function getStateAbbreviation(stateName: string): string | null {
		const stateAbbreviations: { [key: string]: string } = {
			'Alabama': 'AL',
			'Alaska': 'AK',
			'Arizona': 'AZ',
			'Arkansas': 'AR',
			'California': 'CA',
			'Colorado': 'CO',
			'Connecticut': 'CT',
			'Delaware': 'DE',
			'District of Columbia': 'DC',
			'Florida': 'FL',
			'Georgia': 'GA',
			'Hawaii': 'HI',
			'Idaho': 'ID',
			'Illinois': 'IL',
			'Indiana': 'IN',
			'Iowa': 'IA',
			'Kansas': 'KS',
			'Kentucky': 'KY',
			'Louisiana': 'LA',
			'Maine': 'ME',
			'Maryland': 'MD',
			'Massachusetts': 'MA',
			'Michigan': 'MI',
			'Minnesota': 'MN',
			'Mississippi': 'MS',
			'Missouri': 'MO',
			'Montana': 'MT',
			'Nebraska': 'NE',
			'Nevada': 'NV',
			'New Hampshire': 'NH',
			'New Jersey': 'NJ',
			'New Mexico': 'NM',
			'New York': 'NY',
			'North Carolina': 'NC',
			'North Dakota': 'ND',
			'Ohio': 'OH',
			'Oklahoma': 'OK',
			'Oregon': 'OR',
			'Pennsylvania': 'PA',
			'Rhode Island': 'RI',
			'South Carolina': 'SC',
			'South Dakota': 'SD',
			'Tennessee': 'TN',
			'Texas': 'TX',
			'Utah': 'UT',
			'Vermont': 'VT',
			'Virginia': 'VA',
			'Washington': 'WA',
			'West Virginia': 'WV',
			'Wisconsin': 'WI',
			'Wyoming': 'WY',
			'Puerto Rico': 'PR'
		};
		
		return stateAbbreviations[stateName] || null;
	}

	// Function to get display name for geographic levels (plural)
	function getGeoLevelDisplayName(geoLevel: string): string {
		if (!geoLevel) return 'geographic units';

		switch (geoLevel) {
			case 'counties':
				return 'counties';
			case 'school_districts':
				return 'school districts';
			case 'legislative_districts':
				return 'legislative districts';
			case 'census_tracts':
				return 'census tracts';
			default:
				return geoLevel.replace(/_/g, ' ');
		}
	}

	// Function to get singular display name for geographic levels
	function getGeoLevelSingularName(geoLevel: string): string {
		if (!geoLevel) return 'geographic unit';

		switch (geoLevel) {
			case 'counties':
				return 'county';
			case 'school_districts':
				return 'school district';
			case 'legislative_districts':
				return 'legislative district';
			case 'census_tracts':
				return 'census tract';
			default:
				return geoLevel.replace(/_/g, ' ');
		}
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
				return 'Choose the elements of your scatter plot to explore relationships between variables.';
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
		// Re-fetch available geographic units when geo level changes
		if ((selectedChartType === 'line' || selectedChartType === 'bar' || selectedChartType === 'pie') && ($currentGeoLevel || selectedChartType === 'pie')) {
			fetchAvailableGeoUnits();
		}
		if (isChartConfigValid()) {
			debounceApiCall(fetchChartData, DEBOUNCE_DELAY);
		}
	}
	
	$: if (browser && selectedChartType && $currentGeoFilter !== undefined) {
		// Re-fetch available geographic units when state filter changes
		if ((selectedChartType === 'line' || selectedChartType === 'bar' || selectedChartType === 'pie') && ($currentGeoLevel || selectedChartType === 'pie')) {
			fetchAvailableGeoUnits();
		}
		if (isChartConfigValid()) {
			debounceApiCall(fetchChartData, DEBOUNCE_DELAY);
		}
	}
	
	// Auto-generate charts when configuration changes
	$: if (browser && selectedChartType && xAxisVariable && yAxisVariable && selectedYear && isChartConfigValid()) {
		debounceApiCall(fetchChartData, DEBOUNCE_DELAY);
	}
	
	// Auto-generate pie charts when configuration changes
	$: if (browser && selectedChartType === 'pie' && selectedPieChartType && selectedYear && isChartConfigValid()) {
		debounceApiCall(fetchChartData, DEBOUNCE_DELAY);
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
					} else if (chartInstance && selectedChartType === 'bar') {
						// Find the matching bar by label
						const labels = chartInstance.data.labels || [];
						const barIndex = labels.findIndex((label: any) => {
							const labelStr = String(label).toLowerCase();
							return labelStr.includes(matchingUnit.geo_name.toLowerCase());
						});

						if (barIndex !== -1) {
							// Highlight the bar and show tooltip
							chartInstance.tooltip.setActiveElements([{
								datasetIndex: 0,
								index: barIndex
							}], {
								x: 0,
								y: 0
							});
							chartInstance.setActiveElements([{
								datasetIndex: 0,
								index: barIndex
							}]);
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

<div class="bg-white rounded-2xl border border-neutral-200">
	<div class="relative">
		<!-- Header -->
		<div class="px-6 py-5 border-b border-neutral-200 bg-white rounded-t-2xl">
			<div class="flex items-center justify-between">
				<div class="flex items-center space-x-3">
					<div class="w-10 h-10 rounded-xl bg-teal-700 flex items-center justify-center">
						<svg class="w-5 h-5 text-white" fill="none" stroke="currentColor" viewBox="0 0 24 24">
							<path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M9 19v-6a2 2 0 00-2-2H5a2 2 0 00-2 2v6a2 2 0 002 2h2a2 2 0 002-2zm0 0V9a2 2 0 012-2h2a2 2 0 012 2v10m-6 0a2 2 0 002 2h2a2 2 0 002-2m0 0V5a2 2 0 012-2h2a2 2 0 012 2v14a2 2 0 01-2 2h-2a2 2 0 01-2-2z"/>
						</svg>
					</div>
					<div>
						<h3 class="text-xl font-bold text-neutral-900">Chart Selector</h3>
						<p class="text-sm text-neutral-600 mt-0.5">
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
				<div class="p-12 text-center">
					<div class="w-20 h-20 bg-teal-700 rounded-3xl mx-auto mb-8 flex items-center justify-center">
						<svg class="w-10 h-10 text-white" fill="none" stroke="currentColor" viewBox="0 0 24 24">
							<path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M12 6V4m0 2a2 2 0 100 4m0-4a2 2 0 110 4m-6 8a2 2 0 100-4m0 4a2 2 0 100 4m0-4v2m0-6V4m6 6v10m6-2a2 2 0 100-4m0 4a2 2 0 100 4m0-4v2m0-6V4"/>
						</svg>
					</div>
					<h4 class="text-2xl font-bold text-neutral-900 mb-4">Configure Your Analysis</h4>
					<p class="text-neutral-600 text-lg mb-8 max-w-md mx-auto leading-relaxed">
						Select indicators, geography level, and years to view the data table.
					</p>
					<Button
						variant="primary"
						size="lg"
						on:click={() => showVariableSelector.set(true)}
					>
						<svg class="w-5 h-5 mr-3" fill="none" stroke="currentColor" viewBox="0 0 24 24">
							<path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M9 5H7a2 2 0 00-2 2v12a2 2 0 002 2h10a2 2 0 002-2V7a2 2 0 00-2-2h-2M9 5a2 2 0 002 2h2a2 2 0 002-2M9 5a2 2 0 012-2h2a2 2 0 012 2" />
						</svg>
						Open Variable Selector
					</Button>
				</div>
			{/if}
			
			<!-- Chart type selection -->
			{#if !selectedChartType}
				<div class="p-4 md:p-6">

					<div class="grid grid-cols-1 sm:grid-cols-2 gap-4 md:gap-6 max-w-4xl mx-auto">
						{#each chartOptions as option}
							<button
								class="p-4 md:p-6 bg-white border border-neutral-200 rounded-xl hover:bg-neutral-50 hover:border-neutral-300 transition-all duration-300 text-left group {option.disabled ? 'opacity-50 cursor-not-allowed' : 'cursor-pointer'}"
								on:click={() => !option.disabled && selectChartType(option.id)}
								disabled={option.disabled}
							>
								<div class="flex items-start space-x-3 md:space-x-4">
									<div class="w-10 h-10 md:w-12 md:h-12 rounded-xl bg-teal-700 flex items-center justify-center flex-shrink-0">
										<svg class="w-5 h-5 md:w-6 md:h-6 text-white" fill="currentColor" viewBox="0 0 24 24">
											<path d="{option.icon}"/>
										</svg>
									</div>
									<div class="flex-1 min-w-0">
										<h5 class="text-base md:text-lg font-bold text-neutral-900 mb-1 md:mb-2 group-hover:text-neutral-800">
											{option.title}
										</h5>
										<p class="text-xs md:text-sm text-neutral-600 mb-2 md:mb-3 leading-relaxed line-clamp-2">
											{option.description}
										</p>
										<div class="inline-flex items-center text-xs md:text-sm font-semibold text-teal-800 bg-teal-50 px-2 md:px-3 py-1 md:py-1.5 rounded-full border-2 border-teal-700">
											<span class="truncate">{option.useCase}</span>
											{#if !option.disabled}
												<svg class="w-3 h-3 md:w-4 md:h-4 ml-1 md:ml-2 group-hover:tranneutral-x-1 transition-transform flex-shrink-0" fill="none" stroke="currentColor" viewBox="0 0 24 24">
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
				<div class="p-4 md:p-6">
					<div class="grid grid-cols-1 {isExpanded ? '' : 'lg:grid-cols-3'} gap-4 md:gap-8">
						<!-- Configuration Panel -->
						{#if !isExpanded}
						<div class="lg:col-span-1" transition:slide={{ duration: 400, easing: quintOut }}>
							<Card variant="outline">
								<div class="p-4">
									<h4 class="text-lg font-semibold text-neutral-900 mb-3">
										Chart Elements
									</h4>
									<p class="text-sm text-neutral-600 mb-6">
										{getChartInstructions(selectedChartType)}
									</p>
									
									<div class="space-y-4">
										<!-- Pie Chart Type Selection -->
										{#if selectedChartType === 'pie'}
											<div>
												<label class="block text-sm font-medium text-neutral-700 mb-2">
													Pie Chart Type
												</label>
												<select
													bind:value={selectedPieChartType}
													on:change={handleConfigChange}
													class="block w-full px-3 py-2 border border-neutral-300 rounded-md shadow-sm focus:outline-none focus:ring-blue-500 focus:border-blue-500 text-sm"
												>
													<option value="">Select breakdown type</option>
													<option value="revenue">Per Pupil Revenue Breakdown</option>
													<option value="student_demographics">Student Demographics Breakdown</option>
													<option value="community_demographics">Community Demographics Breakdown</option>
												</select>
												<p class="text-xs text-neutral-500 mt-1">
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

										<!-- Geographic Unit Selection for Line, Bar, and Pie Charts -->
										{#if (selectedChartType === 'line' || selectedChartType === 'bar' || selectedChartType === 'pie') && availableGeoUnits.length > 0}
											<div>
												<label class="block text-sm font-medium text-neutral-700 mb-2">
													Geographic Units {selectedChartType === 'pie' ? '(Optional)' : 'to Display'}
												</label>
												<GeographicUnitSelector
													availableUnits={availableGeoUnits}
													bind:selectedUnits={selectedGeoUnits}
													on:change={handleConfigChange}
													placeholder="Search geographic units..."
												/>
												<p class="text-xs text-neutral-500 mt-1">
													{#if selectedChartType === 'pie'}
														Leave empty to aggregate every {getGeoLevelSingularName($currentGeoLevel) || 'county'}, or select specific ones
													{:else if selectedChartType === 'line'}
														Select which {getGeoLevelDisplayName($currentGeoLevel)} to show as separate lines on the chart
													{:else if selectedChartType === 'bar'}
														Select which {getGeoLevelDisplayName($currentGeoLevel)} to include in the bar chart
													{/if}
												</p>
											</div>
										{/if}

										<!-- Bar Chart Options -->
										{#if selectedChartType === 'bar'}
											<div>
												<label class="flex items-center">
													<input
														type="checkbox"
														bind:checked={hideBarLabels}
														on:change={handleConfigChange}
														class="h-4 w-4 text-teal-600 focus:ring-teal-500 border-neutral-300 rounded"
													/>
													<span class="ml-2 text-sm text-neutral-700">Hide unit name labels</span>
												</label>
												<p class="text-xs text-neutral-500 mt-1">
													Remove geographic unit names from the x-axis
												</p>
											</div>
										{/if}

										<!-- X-Axis Variable (only shown for scatter charts) -->
										{#if selectedChartType === 'scatter'}
											<div>
												<label class="block text-sm font-medium text-neutral-700 mb-2">
													X-Axis Variable
												</label>
												<select
													bind:value={xAxisVariable}
													on:change={handleConfigChange}
													class="block w-full px-3 py-2 border border-neutral-300 rounded-md shadow-sm focus:outline-none focus:ring-blue-500 focus:border-blue-500 text-sm"
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
												<label class="block text-sm font-medium text-neutral-700 mb-2">
													Y-Axis Variable
												</label>
												<select
													bind:value={yAxisVariable}
													on:change={handleConfigChange}
													class="block w-full px-3 py-2 border border-neutral-300 rounded-md shadow-sm focus:outline-none focus:ring-blue-500 focus:border-blue-500 text-sm"
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
												<label class="block text-sm font-medium text-neutral-700 mb-2">
													Years to Display
												</label>
												<YearSelector
													selectedYears={$currentYears}
													mode="dropdown"
													placeholder="Select years for chart..."
													on:change={(event) => setYears(event.detail.selectedYears)}
												/>
												<p class="text-xs text-neutral-500 mt-1">
													Line charts will show trends across the selected years
												</p>
											</div>
										{/if}
										
										<!-- Third Variable Configuration for Scatter Plot -->
										{#if selectedChartType === 'scatter'}
											<!-- Toggle between Color By and Size By -->
											<div>
												<label class="block text-sm font-medium text-neutral-700 mb-3">
													Third Variable Mode
												</label>
												<div class="flex flex-wrap gap-3 mb-3">
													<label class="flex items-center">
														<input
															type="radio"
															bind:group={thirdVariableMode}
															value="color"
															on:change={handleConfigChange}
															class="h-4 w-4 text-blue-600 focus:ring-blue-500 border-neutral-300"
														/>
														<span class="ml-2 text-sm text-neutral-700">Color by variable</span>
													</label>
													<label class="flex items-center">
														<input
															type="radio"
															bind:group={thirdVariableMode}
															value="size"
															on:change={handleConfigChange}
															class="h-4 w-4 text-blue-600 focus:ring-blue-500 border-neutral-300"
														/>
														<span class="ml-2 text-sm text-neutral-700">Size by variable</span>
													</label>
													<label class="flex items-center">
														<input
															type="radio"
															bind:group={thirdVariableMode}
															value="state"
															on:change={handleConfigChange}
															class="h-4 w-4 text-blue-600 focus:ring-blue-500 border-neutral-300"
														/>
														<span class="ml-2 text-sm text-neutral-700">Color by state</span>
													</label>
												</div>
												<p class="text-xs text-neutral-500 mb-3">
													{#if thirdVariableMode === 'color'}
														Points will be colored based on the selected variable's values
													{:else if thirdVariableMode === 'state'}
														Each state gets a distinct color
													{:else}
														Point sizes will vary based on the selected variable's values
													{/if}
												</p>
											</div>

											<!-- Third Variable Selector (hidden when coloring by state) -->
											{#if thirdVariableMode !== 'state'}
												<div>
													<label class="block text-sm font-medium text-neutral-700 mb-2">
														{thirdVariableMode === 'color' ? 'Color By' : 'Size By'} (Optional)
													</label>
													<select
														bind:value={thirdVariable}
														on:change={handleConfigChange}
														class="block w-full px-3 py-2 border border-neutral-300 rounded-md shadow-sm focus:outline-none focus:ring-blue-500 focus:border-blue-500 text-sm"
													>
														<option value="">No {thirdVariableMode === 'color' ? 'color grouping' : 'size variation'}</option>
														{#each availableVariables as variable}
															<option value={variable}>{getIndicatorDisplayName(variable)}</option>
														{/each}
													</select>
												</div>
											{/if}

											<!-- Trend Line Toggle -->
											<div>
												<label class="flex items-center">
													<input
														type="checkbox"
														bind:checked={showTrendLine}
														on:change={handleConfigChange}
														class="h-4 w-4 text-blue-600 focus:ring-blue-500 border-neutral-300 rounded"
													/>
													<span class="ml-2 text-sm font-medium text-neutral-700">Show Trend Line</span>
												</label>
												<p class="text-xs text-neutral-500 mt-1">
													Displays a linear regression line showing the relationship between variables
												</p>
											</div>
										{/if}
										
										<!-- Year Selection -->
										{#if selectedChartType !== 'line'}
											<div>
												<label class="block text-sm font-medium text-neutral-700 mb-2">
													Year
												</label>
												<select
													bind:value={selectedYear}
													on:change={handleConfigChange}
													class="block w-full px-3 py-2 border border-neutral-300 rounded-md shadow-sm focus:outline-none focus:ring-blue-500 focus:border-blue-500 text-sm"
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
						{/if}

						<!-- Chart Display Area -->
						<div class="{isExpanded ? '' : 'lg:col-span-2'}">
							<Card variant="outline">
								<div class="p-4">
								<div class="flex items-center justify-between mb-4">
									<h4 class="text-lg font-semibold text-neutral-900">
										{chartOptions.find(opt => opt.id === selectedChartType)?.useCase}
									</h4>
									<Button
										variant="outline"
										size="sm"
										on:click={toggleExpanded}
									>
										{#if isExpanded}
											<svg class="w-4 h-4 mr-2" fill="none" stroke="currentColor" viewBox="0 0 24 24">
												<path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M9 9V4.5M9 9H4.5M9 9L3.5 3.5M15 9h4.5M15 9V4.5M15 9l5.5-5.5M9 15v4.5M9 15H4.5M9 15l-5.5 5.5M15 15h4.5M15 15v4.5m0-4.5l5.5 5.5" />
											</svg>
											Collapse
										{:else}
											<svg class="w-4 h-4 mr-2" fill="none" stroke="currentColor" viewBox="0 0 24 24">
												<path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M3.75 3.75v4.5m0-4.5h4.5m-4.5 0L9 9M3.75 20.25v-4.5m0 4.5h4.5m-4.5 0L9 15M20.25 3.75h-4.5m4.5 0v4.5m0-4.5L15 9m5.25 11.25h-4.5m4.5 0v-4.5m0 4.5L15 15" />
											</svg>
											Expand
										{/if}
									</Button>
								</div>

									{#if !isChartConfigValid()}
										<div class="h-64 flex items-center justify-center bg-neutral-50 rounded-lg border-2 border-dashed border-neutral-300">
											<div class="text-center">
												<div class="w-12 h-12 bg-teal-700 rounded-xl mx-auto mb-4 flex items-center justify-center">
													<svg class="w-6 h-6 text-white" fill="none" stroke="currentColor" viewBox="0 0 24 24">
														{#if selectedChartType === 'bar'}
															<path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M9 19v-6a2 2 0 00-2-2H5a2 2 0 00-2 2v6a2 2 0 002 2h2a2 2 0 002-2zm0 0V9a2 2 0 012-2h2a2 2 0 012 2v10m-6 0a2 2 0 002 2h2a2 2 0 002-2m0 0V5a2 2 0 012-2h2a2 2 0 012 2v14a2 2 0 01-2 2h-2a2 2 0 01-2-2z"/>
														{:else if selectedChartType === 'scatter'}
															<path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M7 12l3-3 3 3 4-4M8 21l4-4 4 4M3 4h18M4 4h16v12a1 1 0 01-1 1H5a1 1 0 01-1-1V4z"/>
														{:else if selectedChartType === 'line'}
															<path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M7 12l3-3 3 3 4-4M8 21l4-4 4 4M3 4h18M4 4h16v12a1 1 0 01-1 1H5a1 1 0 01-1-1V4z"/>
														{:else if selectedChartType === 'pie'}
															<path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M11 3.055A9.001 9.001 0 1020.945 13H11V3.055z"/>
														{:else}
															<path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M9 19v-6a2 2 0 00-2-2H5a2 2 0 00-2 2v6a2 2 0 002 2h2a2 2 0 002-2zm0 0V9a2 2 0 012-2h2a2 2 0 012 2v10m-6 0a2 2 0 002 2h2a2 2 0 002-2m0 0V5a2 2 0 012-2h2a2 2 0 012 2v14a2 2 0 01-2 2h-2a2 2 0 01-2-2z"/>
														{/if}
													</svg>
												</div>
												<p class="text-neutral-900 font-semibold text-sm mb-2">
													{#if selectedChartType === 'bar'}
														Configure Bar Chart Settings
													{:else if selectedChartType === 'scatter'}
														Configure Scatter Plot Settings
													{:else if selectedChartType === 'line'}
														Configure Line Chart Settings
													{:else if selectedChartType === 'pie'}
														Configure Pie Chart Settings
													{:else}
														Configure Chart Settings
													{/if}
												</p>
												<p class="text-neutral-600 text-sm">
													{#if selectedChartType === 'bar'}
														Select a variable and year to compare values across geographies
													{:else if selectedChartType === 'scatter'}
														Select X and Y axis variables and a year to explore relationships
													{:else if selectedChartType === 'line'}
														Select a variable and geographic units to track changes over time
													{:else if selectedChartType === 'pie'}
														Select a breakdown type and year to show composition
													{:else}
														Complete the configuration to see your visualization
													{/if}
												</p>
											</div>
										</div>
									{:else if (selectedChartType === 'line' || selectedChartType === 'bar') && selectedGeoUnits.length === 0 && availableGeoUnits.length > 0}
										<div class="h-64 flex items-center justify-center bg-neutral-50 rounded-lg border-2 border-dashed border-neutral-300">
											<div class="text-center">
												<div class="w-12 h-12 mx-auto mb-4 rounded-xl bg-teal-700 flex items-center justify-center">
													<svg class="w-6 h-6 text-white" fill="none" stroke="currentColor" viewBox="0 0 24 24">
														<path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M17.657 16.657L13.414 20.9a1.998 1.998 0 01-2.827 0l-4.244-4.243a8 8 0 1111.314 0z"/>
														<path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M15 11a3 3 0 11-6 0 3 3 0 016 0z"/>
													</svg>
												</div>
												<p class="text-neutral-600 text-sm mb-2">
													{#if selectedChartType === 'line'}
														Select geographic units from the panel to display trend lines
													{:else if selectedChartType === 'bar'}
														Select geographic units from the panel to include in the bar chart
													{/if}
												</p>
												<p class="text-neutral-500 text-xs">
													Use the "Geographic Units to Display" selector in the configuration panel
												</p>
											</div>
										</div>
									{:else if !isLoading && isChartConfigValid() && chartData.length === 0}
										<div class="h-64 flex items-center justify-center bg-neutral-50 rounded-lg border-2 border-dashed border-neutral-300">
											<div class="text-center">
												<div class="w-12 h-12 bg-teal-700 rounded-xl mx-auto mb-4 flex items-center justify-center">
													<svg class="w-6 h-6 text-white" fill="none" stroke="currentColor" viewBox="0 0 24 24">
														<path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M9.172 16.172a4 4 0 015.656 0M9 12h6m-6 4h6m2 5H7a2 2 0 01-2-2V5a2 2 0 012-2h5.586a1 1 0 01.707.293l5.414 5.414a1 1 0 01.293.707V19a2 2 0 01-2 2z"/>
													</svg>
												</div>
												<p class="text-neutral-900 font-semibold text-sm mb-2">
													No Data Available
												</p>
												<p class="text-neutral-600 text-sm max-w-sm mx-auto">
													{#if selectedChartType === 'bar'}
														No data found for the selected variable and year in the chosen geographic units
													{:else if selectedChartType === 'scatter'}
														No data found for the selected variables and year in the current geographic area
													{:else if selectedChartType === 'line'}
														No data found for the selected variable and years in the chosen geographic units
													{:else if selectedChartType === 'pie'}
														No data found for the selected breakdown type and year in the current geographic area
													{:else}
														No data found for the current selection
													{/if}
												</p>
											</div>
										</div>
									{:else if chartData.length > 0}
										<!-- Search Bar for Scatter Plot and Bar Chart -->
										{#if (selectedChartType === 'scatter' || selectedChartType === 'bar') && availableGeoUnitsForSearch.length > 0}
											<div class="mb-4">
												<label class="block text-sm font-medium text-neutral-700 mb-2">
													Search {$currentGeoLevel && $geographies[$currentGeoLevel] ? $geographies[$currentGeoLevel].name : 'Geographic Units'}
												</label>
												<div class="relative">
													<input
														type="text"
														bind:value={searchTerm}
														on:input={handleSearch}
														placeholder="Search for a geographic unit..."
														class="block w-full px-3 py-2 pr-10 border border-neutral-300 rounded-md shadow-sm focus:outline-none focus:ring-blue-500 focus:border-blue-500 text-sm"
													/>
													{#if searchTerm}
														<button
															type="button"
															on:click={clearSearch}
															class="absolute inset-y-0 right-0 pr-3 flex items-center"
														>
															<svg class="h-4 w-4 text-neutral-400 hover:text-neutral-600" fill="none" stroke="currentColor" viewBox="0 0 24 24">
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
																	class="w-full text-left px-3 py-2 hover:bg-neutral-50 focus:bg-neutral-50 focus:outline-none"
																	on:click={() => {
																		searchTerm = unit.geo_name;
																		handleSearch();
																	}}
																>
																	<div class="flex justify-between items-center">
																		<span class="text-neutral-900">{unit.geo_name}</span>
																		<span class="text-xs text-neutral-500">{unit.geo_id}</span>
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
										<div class="relative w-full transition-all duration-500 ease-in-out {isExpanded ? 'h-[75vh]' : 'h-64 sm:h-80 md:h-96'}">
											<!-- Loading overlay for chart area only -->
											{#if isLoading}
												<div 
													class="absolute inset-0 bg-white bg-opacity-90 backdrop-blur-sm flex items-center justify-center z-30 rounded-lg"
													in:receive={{ key: 'loading' }}
													out:send={{ key: 'loading' }}
												>
													<LoadingSpinner 
														variant="ring" 
														size="lg" 
														color="primary" 
														text="Loading chart data..." 
													/>
												</div>
											{/if}
											<canvas
												bind:this={chartCanvas}
												class="w-full h-full"
											></canvas>
										</div>
										{#if chartData.length > 0 && !chartInstance}
											<div class="mt-4 text-center text-sm text-amber-600">
												Chart data loaded but visualization not rendered. Check console for errors.
											</div>
										{/if}
										
										<!-- Chart Controls -->
										{#if chartInstance && chartData.length > 0}
											<div class="mt-4 flex justify-between items-center">
												<!-- Zoom Instructions for Scatter Plot -->
												{#if selectedChartType === 'scatter'}
													<div class="text-xs text-neutral-500">
														<p class="mb-1">🖱️ <strong>Mouse wheel:</strong> Zoom in/out</p>
														<p>🖱️ <strong>Click & drag:</strong> Move the chart window</p>
													</div>
												{:else}
													<div></div>
												{/if}
												
												<div class="flex space-x-2">
													<!-- Reset Zoom Button (only for scatter plots) -->
													{#if selectedChartType === 'scatter'}
														<Button
															variant="outline"
															size="sm"
															on:click={() => chartInstance?.resetZoom()}
														>
															<svg class="w-4 h-4 mr-2" fill="none" stroke="currentColor" viewBox="0 0 24 24">
																<path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M4 4v5h.582m15.356 2A8.001 8.001 0 004.582 9m0 0H9m11 11v-5h-.581m0 0a8.003 8.003 0 01-15.357-2m15.357 2H15" />
															</svg>
															Reset Zoom
														</Button>
													{/if}
													
													<!-- Export Button -->
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
