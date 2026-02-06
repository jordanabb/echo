<script lang="ts">
	import { onMount, onDestroy } from 'svelte';
	import { browser } from '$app/environment';
	import { 
		unifiedFilters,
		currentGeoLevel,
		currentGeoFilter,
		currentPrimaryIndicator,
		currentPrimaryYear,
		currentYears,
		currentSelectedIndicators,
		currentMapDisplayYear,
		currentMapDisplayIndicator,
		selectedIndicatorsWithMetadata,
		areFiltersValid,
		filtersInitialized
	} from '$lib/stores/unifiedFilters';
	import { geographies } from '$lib/stores/metadata';
	import { showVariableSelector } from '$lib/stores/interactiveSteps';
	import { US_STATES } from '$lib/constants/states';
	import { crossfade } from 'svelte/transition';
	import { quintOut } from 'svelte/easing';
	import Legend from './Legend.svelte';
	import MapControlPanel from './MapControlPanel.svelte';
	import MapTooltip from './MapTooltip.svelte';
	import EmptyState from './EmptyState.svelte';
	
	// Mapbox imports
	let mapboxgl: any;
	
	// Map instance and container
	let mapContainer: HTMLDivElement;
	let map: any;

	// Expose resize method for parent components (e.g., when used in tabs)
	export function triggerResize() {
		if (map) map.resize();
	}
	
	// Component state
	let isLoading = false;
	let error: string | null = null;
	let mapData: any = null;
	let legendData: any[] = [];
	let debugInfo: any = null;
	let showDebug = false; // Hide debug panel by default
	
	// Geometry caching for performance optimization
	let geometryCache = new Map<string, any>(); // Cache key: `${geo_level}_${year}_${state_filter || 'all'}`
	let currentGeometryKey: string | null = null;
	let isGeometryCached = false;
	
	// Map display state (separate from global selection)
	let mapDisplayYear: number | null = null;
	let mapDisplayIndicator: string | null = null;
	
	// Tooltip state
	let hoverTooltip = {
		isVisible: false,
		feature: null,
		position: { x: 0, y: 0 }
	};
	
	let clickTooltip = {
		isVisible: false,
		feature: null,
		position: { x: 0, y: 0 }
	};

	// Initialize map display values from store
	$: mapDisplayYear = $currentMapDisplayYear;
	$: mapDisplayIndicator = $currentMapDisplayIndicator;

	// Handle year change from control panel
	function handleYearChange(event: CustomEvent<{ year: number }>) {
		const { year } = event.detail;
		mapDisplayYear = year;
		
		// Fetch new map data for the selected year
		if ($currentGeoLevel && mapDisplayIndicator) {
			fetchMapData(mapDisplayIndicator, $currentGeoLevel, year);
		}
	}

	// Handle indicator change from control panel
	function handleIndicatorChange(event: CustomEvent<{ indicatorId: string }>) {
		const { indicatorId } = event.detail;
		mapDisplayIndicator = indicatorId;
		
		// Fetch new map data for the selected indicator
		if ($currentGeoLevel && mapDisplayYear) {
			fetchMapData(indicatorId, $currentGeoLevel, mapDisplayYear);
		}
	}

	// Handle save map action from control panel
	function handleSaveMap() {
		if (!map) {
			console.error('Map not initialized');
			return;
		}

		try {
			// Wait for map to finish rendering before capturing
			map.once('idle', () => {
				try {
					createCompositeMapImage();
				} catch (error) {
					console.error('Error capturing map canvas:', error);
				}
			});

			// If map is already idle, trigger the save immediately
			if (map.isStyleLoaded() && !map.isMoving()) {
				map.fire('idle');
			}
		} catch (error) {
			console.error('Error saving map:', error);
		}
	}

	// Create a composite image with map, legend, and title
	function createCompositeMapImage() {
		const mapCanvas = map.getCanvas();
		
		// Get indicator name for title
		const indicatorName = $selectedIndicatorsWithMetadata.find(ind => ind.id === mapDisplayIndicator)?.name || mapDisplayIndicator || 'Unknown Indicator';
		const year = mapDisplayYear || 'Unknown Year';
		const title = `${indicatorName} (${year})`;
		
		// Create a new canvas for the composite image
		const compositeCanvas = document.createElement('canvas');
		const ctx = compositeCanvas.getContext('2d');
		
		// Use actual map canvas dimensions
		const mapWidth = mapCanvas.width;
		const mapHeight = mapCanvas.height;
		
		// Set canvas dimensions (add space for title and legend)
		const titleHeight = 80;
		const legendWidth = 300;
		const padding = 20;
		
		compositeCanvas.width = mapWidth + legendWidth + padding * 3;
		compositeCanvas.height = mapHeight + titleHeight + padding * 2;
		
		// Fill background with white
		ctx.fillStyle = '#ffffff';
		ctx.fillRect(0, 0, compositeCanvas.width, compositeCanvas.height);
		
		// Draw title
		ctx.fillStyle = '#1f2937';
		ctx.font = 'bold 24px Arial, sans-serif';
		ctx.textAlign = 'center';
		ctx.fillText(title, compositeCanvas.width / 2, titleHeight / 2 + 8);
		
		// Draw subtitle with geography info
		const geoLevelName = $geographies[$currentGeoLevel || '']?.name || $currentGeoLevel || 'Unknown Geography';
		let subtitle = `Geography: ${geoLevelName}`;
		if ($currentGeoFilter) {
			const stateName = US_STATES.find(state => state.code === $currentGeoFilter)?.name || $currentGeoFilter;
			subtitle += ` (${stateName})`;
		}
		
		ctx.font = '16px Arial, sans-serif';
		ctx.fillStyle = '#6b7280';
		ctx.fillText(subtitle, compositeCanvas.width / 2, titleHeight / 2 + 35);
		
		// Draw map
		ctx.drawImage(mapCanvas, padding, titleHeight + padding);
		
		// Draw legend if available
		if (legendData.length > 0) {
			drawLegendOnCanvas(ctx, mapWidth + padding * 2, titleHeight + padding, legendWidth - padding);
		}
		
		// Create filename and download
		const timestamp = new Date().toISOString().slice(0, 19).replace(/:/g, '-');
		const geoLevel = $currentGeoLevel || 'unknown';
		const indicator = mapDisplayIndicator || 'unknown';
		const yearStr = mapDisplayYear || 'unknown';
		const filename = `echo-map-${geoLevel}-${indicator}-${yearStr}-${timestamp}.png`;
		
		// Convert to blob and download
		compositeCanvas.toBlob((blob) => {
			if (blob) {
				const url = URL.createObjectURL(blob);
				const link = document.createElement('a');
				link.href = url;
				link.download = filename;
				document.body.appendChild(link);
				link.click();
				document.body.removeChild(link);
				URL.revokeObjectURL(url);
				
				console.log('Map saved as:', filename);
			} else {
				console.error('Failed to create blob from composite canvas');
			}
		}, 'image/png');
	}

	// Draw legend on canvas
	function drawLegendOnCanvas(ctx: CanvasRenderingContext2D, x: number, y: number, width: number) {
		const itemHeight = 25;
		const colorBoxSize = 16;
		const padding = 10;
		
		// Draw legend background
		ctx.fillStyle = '#ffffff';
		ctx.strokeStyle = '#e5e7eb';
		ctx.lineWidth = 1;
		const legendHeight = legendData.length * itemHeight + padding * 2 + 30;
		ctx.fillRect(x, y, width, legendHeight);
		ctx.strokeRect(x, y, width, legendHeight);
		
		// Draw legend title
		ctx.fillStyle = '#1f2937';
		ctx.font = 'bold 16px Arial, sans-serif';
		ctx.textAlign = 'left';
		ctx.fillText('Legend', x + padding, y + padding + 16);
		
		// Draw legend items
		legendData.forEach((item, index) => {
			const itemY = y + padding + 30 + (index * itemHeight);
			
			// Draw color box
			ctx.fillStyle = item.color;
			ctx.fillRect(x + padding, itemY, colorBoxSize, colorBoxSize);
			ctx.strokeStyle = '#d1d5db';
			ctx.strokeRect(x + padding, itemY, colorBoxSize, colorBoxSize);
			
			// Draw label
			ctx.fillStyle = '#374151';
			ctx.font = '14px Arial, sans-serif';
			ctx.fillText(item.label, x + padding + colorBoxSize + 8, itemY + 12);
		});
	}
	
	// Mapbox configuration
	const MAPBOX_TOKEN = 'pk.eyJ1Ijoiam9yZGFuYWJiIiwiYSI6ImNtOWx1Y3FsMTAwdWkybXB4ajdmbXRnZHkifQ.VnprPvy-fvxSO05l9c1LOw';
	const MAPBOX_STYLE = 'mapbox://styles/jordanabb/cmb5puoou002f01qt4r796okw';
	
	// Choropleth colors (teal palette to match app theme)
	const CHOROPLETH_PALETTE = [
		'#f0fdfa',
		'#ccfbf1', 
		'#5eead4',
		'#14b8a6',
		'#0f766e'
	];
	const NO_DATA_COLOR = '#999999';
	
	// Crossfade transition for smooth updates
	const [send, receive] = crossfade({
		duration: 300,
		easing: quintOut
	});
	
	// Function to get expected geo_id length for a geographic level
	function getExpectedGeoIdLength(geoLevel: string): number | null {
		const geoIdLengths: Record<string, number> = {
			'county': 5,
			'tract': 11,
			'school_district': 7,
			'sldl': 5,  // State Legislative District Lower
			'sldu': 5   // State Legislative District Upper
		};
		
		return geoIdLengths[geoLevel] || null;
	}

	// Function to normalize geo_ids to ensure consistent formatting
	function normalizeGeoId(geoId: string, geoLevel: string): string {
		// Get the expected length for this geography level
		const expectedLength = getExpectedGeoIdLength(geoLevel);
		
		if (expectedLength === null) {
			// If we don't have a defined length, return as-is
			return String(geoId);
		}
		
		// Convert to string and pad with zeros on the left
		return String(geoId).padStart(expectedLength, '0');
	}
	
	// Function to generate legend data using the actual map colors
	function generateLegendFromMapColors(originalLegend: any[]): any[] {
		if (!originalLegend || originalLegend.length === 0) {
			return [];
		}
		
		// Map the original legend entries to use the actual map colors
		return originalLegend.map((entry, index) => {
			// Check if this is a "no data" entry
			if (entry.label && entry.label.toLowerCase().includes('no data')) {
				return {
					...entry,
					color: NO_DATA_COLOR
				};
			}
			
			// For data entries, use the corresponding color from the choropleth palette
			// The API typically sends legend entries in order from lowest to highest
			const colorIndex = Math.min(index, CHOROPLETH_PALETTE.length - 1);
			return {
				...entry,
				color: CHOROPLETH_PALETTE[colorIndex]
			};
		});
	}
	
	// Initialize Mapbox when component mounts
	onMount(async () => {
		if (browser) {
			try {
				// Dynamic import of Mapbox GL JS
				const mapboxModule = await import('mapbox-gl');
				mapboxgl = mapboxModule.default;
				
				// Set access token
				mapboxgl.accessToken = MAPBOX_TOKEN;
				
				// Initialize map
				map = new mapboxgl.Map({
					container: mapContainer,
					style: MAPBOX_STYLE,
					center: [-98.5, 39.8], // Center of US
					zoom: 3,
					projection: 'albers',
					preserveDrawingBuffer: true // Required for canvas export
				});
				
				// Wait for map to load
				map.on('load', () => {
					console.log('Map loaded successfully');
					// Trigger initial data fetch if filters are valid
					if ($areFiltersValid && $currentPrimaryIndicator && $currentGeoLevel && $currentPrimaryYear) {
						fetchMapData($currentPrimaryIndicator, $currentGeoLevel, $currentPrimaryYear);
					}
				});
				
				map.on('error', (e: any) => {
					console.error('Map error:', e);
					error = 'Failed to load map';
				});
				
			} catch (err) {
				console.error('Failed to initialize Mapbox:', err);
				error = 'Failed to initialize map';
			}
		}
	});
	
	// Clean up map on component destroy
	onDestroy(() => {
		if (map) {
			map.remove();
		}
	});
	
	// Reactive statement to fetch data when filters change (including state filter)
	$: if (browser && map && $filtersInitialized && $currentGeoLevel && $currentPrimaryYear) {
		// Check if we have a valid primary indicator for data visualization
		const hasPrimaryIndicator = $currentPrimaryIndicator && 
									typeof $currentPrimaryIndicator === 'string';
		
		// Check if we have selected indicators (for analysis)
		const hasSelectedIndicators = $currentSelectedIndicators && 
									  $currentSelectedIndicators.length > 0;
		
		// Determine which indicator to display on the map
		let indicatorToDisplay = null;
		if (hasPrimaryIndicator) {
			// Use primary indicator if available
			indicatorToDisplay = $currentPrimaryIndicator;
		} else if (hasSelectedIndicators) {
			// Use first selected indicator if no primary indicator
			indicatorToDisplay = $currentSelectedIndicators[0];
		}
		
		// Check if we have valid geographic and temporal context
		const hasGeoContext = $currentGeoLevel && 
							   $currentPrimaryYear && 
							   typeof $currentGeoLevel === 'string' && 
							   typeof $currentPrimaryYear === 'number';
		
		if (hasGeoContext) {
			console.log('Map: Loading map with context:', {
				primaryIndicator: $currentPrimaryIndicator,
				selectedIndicators: $currentSelectedIndicators,
				indicatorToDisplay,
				geoLevel: $currentGeoLevel,
				year: $currentPrimaryYear,
				stateFilter: $currentGeoFilter
			});
			
			// Ensure map is loaded before fetching data
			if (map.loaded()) {
				if (indicatorToDisplay) {
					// Fetch data with the determined indicator
					fetchMapData(indicatorToDisplay, $currentGeoLevel, $currentPrimaryYear);
				} else {
					// Show just geographic boundaries without data
					fetchGeographicBoundaries($currentGeoLevel, $currentPrimaryYear);
				}
			} else {
				map.once('load', () => {
					if (indicatorToDisplay) {
						fetchMapData(indicatorToDisplay, $currentGeoLevel, $currentPrimaryYear);
					} else {
						fetchGeographicBoundaries($currentGeoLevel, $currentPrimaryYear);
					}
				});
			}
		} else {
			console.warn('Invalid geographic context:', { 
				geoLevel: $currentGeoLevel, 
				year: $currentPrimaryYear 
			});
		}
	}

	// Separate reactive statement for state filter changes to trigger map refresh
	$: if (browser && map && $currentGeoLevel && $currentPrimaryYear && $currentGeoFilter !== undefined) {
		// Determine which indicator to display (same logic as main reactive statement)
		let indicatorToDisplay = null;
		if ($currentPrimaryIndicator) {
			indicatorToDisplay = $currentPrimaryIndicator;
		} else if ($currentSelectedIndicators && $currentSelectedIndicators.length > 0) {
			indicatorToDisplay = $currentSelectedIndicators[0];
		}
		
		// Trigger refresh when state filter changes (including when it's cleared)
		if (map.loaded()) {
			if (indicatorToDisplay) {
				fetchMapData(indicatorToDisplay, $currentGeoLevel, $currentPrimaryYear);
			} else {
				fetchGeographicBoundaries($currentGeoLevel, $currentPrimaryYear);
			}
		}
	}
	
	// Function to generate cache key for geometries
	function getGeometryCacheKey(geoLevel: string, year: number, stateFilter: string | null): string {
		return `${geoLevel}_${year}_${stateFilter || 'all'}`;
	}
	
	// Function to fetch geometries (with caching)
	async function fetchGeometries(geoLevel: string, year: number): Promise<any> {
		const cacheKey = getGeometryCacheKey(geoLevel, year, $currentGeoFilter);
		
		// Check if geometries are already cached
		if (geometryCache.has(cacheKey)) {
			console.log('Using cached geometries for:', cacheKey);
			return geometryCache.get(cacheKey);
		}
		
		console.log('Fetching new geometries for:', cacheKey);
		
		const params = new URLSearchParams({
			geo_level: geoLevel,
			year: year.toString()
		});
		
		// Add state filter if selected
		if ($currentGeoFilter) {
			params.set('state_filter', $currentGeoFilter);
		}
		
		const response = await fetch(`/api/geometries?${params}`);
		
		if (!response.ok) {
			if (response.status === 404) {
				throw new Error('No geographic data available for the selected filters');
			}
			throw new Error(`HTTP ${response.status}: ${response.statusText}`);
		}
		
		const geometryData = await response.json();
		
		// Cache the geometries
		geometryCache.set(cacheKey, geometryData);
		
		// Limit cache size to prevent memory issues
		if (geometryCache.size > 10) {
			const firstKey = geometryCache.keys().next().value;
			geometryCache.delete(firstKey);
		}
		
		return geometryData;
	}
	
	// Function to fetch indicator data only
	async function fetchIndicatorData(indicator: string, geoLevel: string, year: number): Promise<any> {
		console.log('Fetching indicator data for:', indicator);
		
		const params = new URLSearchParams({
			indicator,
			geo_level: geoLevel,
			year: year.toString()
		});
		
		// Add state filter if selected
		if ($currentGeoFilter) {
			params.set('state_filter', $currentGeoFilter);
		}
		
		const response = await fetch(`/api/indicator-data?${params}`);
		
		if (!response.ok) {
			if (response.status === 404) {
				throw new Error('No data available for the selected indicator');
			}
			throw new Error(`HTTP ${response.status}: ${response.statusText}`);
		}
		
		return await response.json();
	}
	
	// Function to fetch just geographic boundaries without indicator data
	async function fetchGeographicBoundaries(geoLevel: string, year: number) {
		if (!geoLevel || !year) return;
		
		isLoading = true;
		error = null;
		
		try {
			const geometryCacheKey = getGeometryCacheKey(geoLevel, year, $currentGeoFilter);
			const needsNewGeometry = currentGeometryKey !== geometryCacheKey;
			
			// Store debug info
			debugInfo = {
				requestParams: {
					indicator: null,
					geo_level: geoLevel,
					year,
					state_filter: $currentGeoFilter || null
				},
				timestamp: new Date().toISOString(),
				cacheInfo: {
					geometryCacheKey,
					currentGeometryKey,
					needsNewGeometry,
					cacheSize: geometryCache.size
				}
			};
			
			console.log('Fetching geographic boundaries only:', debugInfo);
			
			let geometryData: any;
			
			if (needsNewGeometry) {
				// Fetch geometries
				console.log('Fetching new geometries for boundaries');
				geometryData = await fetchGeometries(geoLevel, year);
				currentGeometryKey = geometryCacheKey;
				isGeometryCached = true;
			} else {
				// Use cached geometries
				console.log('Using cached geometries for boundaries');
				geometryData = geometryCache.get(geometryCacheKey);
			}
			
			// Create boundaries-only data (no indicator data)
			const boundariesData = {
				geoJson: geometryData.geoJson,
				data: [], // No indicator data
				legend: [] // No legend
			};
			
			// Update debug info with response
			debugInfo = {
				...debugInfo,
				responseData: {
					geometryFeatures: geometryData.geoJson?.features?.length || 0,
					indicatorDataPoints: 0,
					legendEntries: 0
				},
				performance: {
					usedCache: !needsNewGeometry,
					cacheHit: isGeometryCached && !needsNewGeometry
				}
			};
			
			console.log('Geographic boundaries loaded:', debugInfo);
			
			// Update component state
			mapData = boundariesData;
			legendData = []; // No legend for boundaries-only view
			
			// Update map with boundaries only
			updateBoundariesOnly(boundariesData);
			
		} catch (err) {
			console.error('Error fetching geographic boundaries:', err);
			error = err instanceof Error ? err.message : 'Failed to load geographic boundaries';
			mapData = null;
			legendData = [];
			
			// Update debug info with error
			debugInfo = {
				...debugInfo,
				error: err instanceof Error ? err.message : 'Unknown error',
				errorStack: err instanceof Error ? err.stack : undefined
			};
		} finally {
			isLoading = false;
		}
	}

	// Optimized function to fetch map data with smart caching
	async function fetchMapData(indicator: string, geoLevel: string, year: number) {
		if (!indicator || !geoLevel || !year) return;
		
		isLoading = true;
		error = null;
		
		try {
			const geometryCacheKey = getGeometryCacheKey(geoLevel, year, $currentGeoFilter);
			const needsNewGeometry = currentGeometryKey !== geometryCacheKey;
			
			// Store debug info
			debugInfo = {
				requestParams: {
					indicator,
					geo_level: geoLevel,
					year,
					state_filter: $currentGeoFilter || null
				},
				timestamp: new Date().toISOString(),
				cacheInfo: {
					geometryCacheKey,
					currentGeometryKey,
					needsNewGeometry,
					cacheSize: geometryCache.size
				}
			};
			
			console.log('Optimized map data fetch:', debugInfo);
			
			let geometryData: any;
			let indicatorData: any;
			
			if (needsNewGeometry) {
				// Need to fetch both geometries and indicator data
				console.log('Fetching both geometries and indicator data');
				[geometryData, indicatorData] = await Promise.all([
					fetchGeometries(geoLevel, year),
					fetchIndicatorData(indicator, geoLevel, year)
				]);
				currentGeometryKey = geometryCacheKey;
				isGeometryCached = true;
			} else {
				// Geometries are cached, only fetch indicator data
				console.log('Using cached geometries, fetching only indicator data');
				geometryData = geometryCache.get(geometryCacheKey);
				indicatorData = await fetchIndicatorData(indicator, geoLevel, year);
			}
			
			// Combine geometry and indicator data
			const combinedData = {
				geoJson: geometryData.geoJson,
				data: indicatorData.data,
				legend: indicatorData.legend
			};
			
			// Update debug info with response
			debugInfo = {
				...debugInfo,
				responseData: {
					geometryFeatures: geometryData.geoJson?.features?.length || 0,
					indicatorDataPoints: indicatorData.data?.length || 0,
					legendEntries: indicatorData.legend?.length || 0
				},
				performance: {
					usedCache: !needsNewGeometry,
					cacheHit: isGeometryCached && !needsNewGeometry
				}
			};
			
			console.log('Optimized map data received:', debugInfo);
			
			// Update component state
			mapData = combinedData;
			
			// Generate legend data using the actual map colors
			legendData = generateLegendFromMapColors(indicatorData.legend || []);
			
			// Update map with new data
			updateMapData(combinedData);
			
		} catch (err) {
			console.error('Error fetching optimized map data:', err);
			error = err instanceof Error ? err.message : 'Failed to load map data';
			mapData = null;
			legendData = [];
			
			// Update debug info with error
			debugInfo = {
				...debugInfo,
				error: err instanceof Error ? err.message : 'Unknown error',
				errorStack: err instanceof Error ? err.stack : undefined
			};
		} finally {
			isLoading = false;
		}
	}
	
	// Function to update map with boundaries only (no data visualization)
	function updateBoundariesOnly(data: any) {
		if (!map || !data) return;
		
		try {
			// Remove existing layers and sources
			if (map.getLayer('choropleth-layer')) {
				map.removeLayer('choropleth-layer');
			}
			if (map.getLayer('choropleth-stroke')) {
				map.removeLayer('choropleth-stroke');
			}
			if (map.getSource('choropleth-data')) {
				map.removeSource('choropleth-data');
			}
			
			console.log('Updating map with boundaries only:', {
				totalFeatures: data.geoJson.features.length
			});
			
			// Prepare GeoJSON with normalized geo_ids but no data values
			const geoJsonWithBoundaries = {
				...data.geoJson,
				features: data.geoJson.features.map((feature: any) => {
					// Normalize geo_id to ensure consistent formatting
					const normalizedGeoId = normalizeGeoId(String(feature.properties.geo_id), $currentGeoLevel || '');
					
					return {
						...feature,
						properties: {
							...feature.properties,
							geo_id: normalizedGeoId,
							value: null, // No data values
							bin: -1 // No data bin
						}
					};
				})
			};
			
			// Add source
			map.addSource('choropleth-data', {
				type: 'geojson',
				data: geoJsonWithBoundaries
			});
			
			// Add fill layer with neutral color
			map.addLayer({
				id: 'choropleth-layer',
				type: 'fill',
				source: 'choropleth-data',
				paint: {
					'fill-color': '#e5e7eb', // Light gray for boundaries-only view
					'fill-opacity': 0.3
				}
			});
			
			// Add stroke layer
			map.addLayer({
				id: 'choropleth-stroke',
				type: 'line',
				source: 'choropleth-data',
				paint: {
					'line-color': '#9ca3af', // Darker gray for boundaries
					'line-width': 1,
					'line-opacity': 0.8
				}
			});
			
			// Add basic hover effects (no tooltips since there's no data)
			let hoveredFeatureId: string | null = null;
			
			map.on('mouseenter', 'choropleth-layer', (e: any) => {
				map.getCanvas().style.cursor = 'pointer';
				
				if (e.features.length > 0) {
					const feature = e.features[0];
					
					// Update hover state
					if (hoveredFeatureId !== null) {
						map.setFeatureState(
							{ source: 'choropleth-data', id: hoveredFeatureId },
							{ hover: false }
						);
					}
					
					hoveredFeatureId = feature.id;
					map.setFeatureState(
						{ source: 'choropleth-data', id: hoveredFeatureId },
						{ hover: true }
					);
					
					// Show basic hover tooltip with just geographic info
					const rect = mapContainer.getBoundingClientRect();
					hoverTooltip = {
						isVisible: true,
						feature: feature,
						position: {
							x: e.point.x + rect.left,
							y: e.point.y + rect.top
						}
					};
				}
			});
			
			map.on('mousemove', 'choropleth-layer', (e: any) => {
				if (e.features.length > 0) {
					const feature = e.features[0];
					const rect = mapContainer.getBoundingClientRect();
					
					// Update hover tooltip position
					hoverTooltip = {
						isVisible: true,
						feature: feature,
						position: {
							x: e.point.x + rect.left,
							y: e.point.y + rect.top
						}
					};
					
					// Update hover state if feature changed
					if (hoveredFeatureId !== feature.id) {
						if (hoveredFeatureId !== null) {
							map.setFeatureState(
								{ source: 'choropleth-data', id: hoveredFeatureId },
								{ hover: false }
							);
						}
						
						hoveredFeatureId = feature.id;
						map.setFeatureState(
							{ source: 'choropleth-data', id: hoveredFeatureId },
							{ hover: true }
						);
					}
				}
			});
			
			map.on('mouseleave', 'choropleth-layer', () => {
				map.getCanvas().style.cursor = '';
				
				// Clear hover state
				if (hoveredFeatureId !== null) {
					map.setFeatureState(
						{ source: 'choropleth-data', id: hoveredFeatureId },
						{ hover: false }
					);
				}
				hoveredFeatureId = null;
				
				// Hide hover tooltip
				hoverTooltip = {
					isVisible: false,
					feature: null,
					position: { x: 0, y: 0 }
				};
			});
			
			// Fit map to data bounds
			if (geoJsonWithBoundaries.features.length > 0) {
				const bounds = new mapboxgl.LngLatBounds();
				geoJsonWithBoundaries.features.forEach((feature: any) => {
					if (feature.geometry.type === 'Polygon') {
						feature.geometry.coordinates[0].forEach((coord: number[]) => {
							bounds.extend(coord);
						});
					} else if (feature.geometry.type === 'MultiPolygon') {
						feature.geometry.coordinates.forEach((polygon: number[][][]) => {
							polygon[0].forEach((coord: number[]) => {
								bounds.extend(coord);
							});
						});
					}
				});
				
				map.fitBounds(bounds, { padding: 50 });
			}
			
		} catch (err) {
			console.error('Error updating boundaries:', err);
			error = `Failed to update map boundaries: ${err instanceof Error ? err.message : 'Unknown error'}`;
		}
	}

	// Function to update map with new data
	function updateMapData(data: any) {
		if (!map || !data) return;
		
		try {
			// Remove existing layers and sources
			if (map.getLayer('choropleth-layer')) {
				map.removeLayer('choropleth-layer');
			}
			if (map.getLayer('choropleth-stroke')) {
				map.removeLayer('choropleth-stroke');
			}
			if (map.getSource('choropleth-data')) {
				map.removeSource('choropleth-data');
			}
			
			// Create a lookup map for indicator data
			const dataLookup = new Map();
			data.data.forEach((item: any) => {
				dataLookup.set(item.geo_id, item);
			});
			
			// Debug: Log data mapping
			console.log('Data lookup created:', {
				totalDataItems: data.data.length,
				sampleDataItems: Array.from(dataLookup.entries()).slice(0, 5),
				totalFeatures: data.geoJson.features.length
			});
			
			// Add indicator data to GeoJSON features
			let matchedCount = 0;
			let unmatchedGeoIds: string[] = [];
			
			const geoJsonWithData = {
				...data.geoJson,
				features: data.geoJson.features.map((feature: any) => {
					// Normalize geo_id to ensure consistent formatting
					const normalizedGeoId = normalizeGeoId(String(feature.properties.geo_id), $currentGeoLevel || '');
					const indicatorData = dataLookup.get(normalizedGeoId);
					
					if (indicatorData) {
						matchedCount++;
					} else {
						unmatchedGeoIds.push(normalizedGeoId);
					}
					
					return {
						...feature,
						properties: {
							...feature.properties,
							geo_id: normalizedGeoId, // Update the geo_id in the feature properties
							value: indicatorData?.value || null,
							bin: indicatorData?.bin ?? -1
						}
					};
				})
			};
			
			// Update debug info with matching results
			debugInfo = {
				...debugInfo,
				dataMatching: {
					totalFeatures: data.geoJson.features.length,
					matchedFeatures: matchedCount,
					unmatchedFeatures: unmatchedGeoIds.length,
					sampleUnmatchedGeoIds: unmatchedGeoIds.slice(0, 10),
					matchPercentage: ((matchedCount / data.geoJson.features.length) * 100).toFixed(2) + '%'
				}
			};
			
			console.log('Feature matching results:', debugInfo.dataMatching);
			
			// Add source
			map.addSource('choropleth-data', {
				type: 'geojson',
				data: geoJsonWithData
			});
			
			// Create fill color expression
			const fillColorExpression = [
				'case',
				['==', ['get', 'bin'], -1], NO_DATA_COLOR, // No data
				['==', ['get', 'bin'], 0], CHOROPLETH_PALETTE[0],
				['==', ['get', 'bin'], 1], CHOROPLETH_PALETTE[1],
				['==', ['get', 'bin'], 2], CHOROPLETH_PALETTE[2],
				['==', ['get', 'bin'], 3], CHOROPLETH_PALETTE[3],
				['==', ['get', 'bin'], 4], CHOROPLETH_PALETTE[4],
				NO_DATA_COLOR // fallback
			];
			
			// Add fill layer
			map.addLayer({
				id: 'choropleth-layer',
				type: 'fill',
				source: 'choropleth-data',
				paint: {
					'fill-color': fillColorExpression,
					'fill-opacity': 0.8
				}
			});
			
			// Add stroke layer
			map.addLayer({
				id: 'choropleth-stroke',
				type: 'line',
				source: 'choropleth-data',
				paint: {
					'line-color': '#ffffff',
					'line-width': 0.5,
					'line-opacity': 0.8
				}
			});
			
			// Add hover effects and tooltip functionality
			let hoveredFeatureId: string | null = null;
			
			map.on('mouseenter', 'choropleth-layer', (e: any) => {
				map.getCanvas().style.cursor = 'pointer';
				
				if (e.features.length > 0) {
					const feature = e.features[0];
					
					// Update hover state
					if (hoveredFeatureId !== null) {
						map.setFeatureState(
							{ source: 'choropleth-data', id: hoveredFeatureId },
							{ hover: false }
						);
					}
					
					hoveredFeatureId = feature.id;
					map.setFeatureState(
						{ source: 'choropleth-data', id: hoveredFeatureId },
						{ hover: true }
					);
					
					// Show hover tooltip
					const rect = mapContainer.getBoundingClientRect();
					hoverTooltip = {
						isVisible: true,
						feature: feature,
						position: {
							x: e.point.x + rect.left,
							y: e.point.y + rect.top
						}
					};
				}
			});
			
			map.on('mousemove', 'choropleth-layer', (e: any) => {
				if (e.features.length > 0) {
					const feature = e.features[0];
					const rect = mapContainer.getBoundingClientRect();
					
					// Update hover tooltip with new feature and position
					hoverTooltip = {
						isVisible: true,
						feature: feature,
						position: {
							x: e.point.x + rect.left,
							y: e.point.y + rect.top
						}
					};
					
					// Update hover state if feature changed
					if (hoveredFeatureId !== feature.id) {
						if (hoveredFeatureId !== null) {
							map.setFeatureState(
								{ source: 'choropleth-data', id: hoveredFeatureId },
								{ hover: false }
							);
						}
						
						hoveredFeatureId = feature.id;
						map.setFeatureState(
							{ source: 'choropleth-data', id: hoveredFeatureId },
							{ hover: true }
						);
					}
				}
			});
			
			map.on('mouseleave', 'choropleth-layer', () => {
				map.getCanvas().style.cursor = '';
				
				// Clear hover state
				if (hoveredFeatureId !== null) {
					map.setFeatureState(
						{ source: 'choropleth-data', id: hoveredFeatureId },
						{ hover: false }
					);
				}
				hoveredFeatureId = null;
				
				// Hide hover tooltip
				hoverTooltip = {
					isVisible: false,
					feature: null,
					position: { x: 0, y: 0 }
				};
			});
			
			// Add click handler for detailed tooltip
			map.on('click', 'choropleth-layer', (e: any) => {
				if (e.features.length > 0) {
					const feature = e.features[0];
					const rect = mapContainer.getBoundingClientRect();
					
					// Hide hover tooltip when showing click tooltip
					hoverTooltip = {
						isVisible: false,
						feature: null,
						position: { x: 0, y: 0 }
					};
					
					// Show click tooltip (always replace any existing one)
					clickTooltip = {
						isVisible: true,
						feature: feature,
						position: {
							x: e.point.x + rect.left,
							y: e.point.y + rect.top
						}
					};
				}
			});
			
			// Hide click tooltip when clicking elsewhere on the map
			map.on('click', (e: any) => {
				// Check if click was on a feature
				const features = map.queryRenderedFeatures(e.point, { layers: ['choropleth-layer'] });
				if (features.length === 0) {
					// Clicked on empty area, hide click tooltip
					clickTooltip = {
						isVisible: false,
						feature: null,
						position: { x: 0, y: 0 }
					};
				}
			});
			
			// Fit map to data bounds
			if (geoJsonWithData.features.length > 0) {
				const bounds = new mapboxgl.LngLatBounds();
				geoJsonWithData.features.forEach((feature: any) => {
					if (feature.geometry.type === 'Polygon') {
						feature.geometry.coordinates[0].forEach((coord: number[]) => {
							bounds.extend(coord);
						});
					} else if (feature.geometry.type === 'MultiPolygon') {
						feature.geometry.coordinates.forEach((polygon: number[][][]) => {
							polygon[0].forEach((coord: number[]) => {
								bounds.extend(coord);
							});
						});
					}
				});
				
				map.fitBounds(bounds, { padding: 50 });
			}
			
		} catch (err) {
			console.error('Error updating map data:', err);
			error = `Failed to update map visualization: ${err instanceof Error ? err.message : 'Unknown error'}`;
			
			// Update debug info with detailed error
			debugInfo = {
				...debugInfo,
				mapError: {
					message: err instanceof Error ? err.message : 'Unknown error',
					stack: err instanceof Error ? err.stack : undefined,
					dataInfo: {
						hasData: !!data,
						hasGeoJson: !!data?.geoJson,
						hasFeatures: !!data?.geoJson?.features,
						featureCount: data?.geoJson?.features?.length || 0,
						sampleFeatureGeoIds: data?.geoJson?.features?.slice(0, 5).map((f: any) => f.properties?.geo_id)
					}
				}
			};
		}
	}
</script>

<!-- Map container -->
<div class="relative w-full h-full bg-gray-100 rounded-lg overflow-hidden">
	<!-- Debug Panel -->
	{#if showDebug && debugInfo}
		<div class="absolute top-4 right-4 z-20 bg-white rounded-lg shadow-lg border border-gray-200 max-w-md">
			<div class="p-4">
				<div class="flex items-center justify-between mb-3">
					<h3 class="font-semibold text-gray-900">Debug Info</h3>
					<button 
						class="text-gray-500 hover:text-gray-700"
						on:click={() => showDebug = false}
					>
						<svg class="w-5 h-5" fill="none" stroke="currentColor" viewBox="0 0 24 24">
							<path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M6 18L18 6M6 6l12 12" />
						</svg>
					</button>
				</div>
				
				<div class="space-y-3 text-sm">
					<!-- Request Info -->
					<div>
						<h4 class="font-medium text-gray-700 mb-1">Request</h4>
						<div class="bg-gray-50 p-2 rounded text-xs font-mono">
							<div>Indicator: {debugInfo.requestParams?.indicator}</div>
							<div>Geo Level: {debugInfo.requestParams?.geo_level}</div>
							<div>Year: {debugInfo.requestParams?.year}</div>
						</div>
					</div>
					
					<!-- Response Info -->
					{#if debugInfo.responseStatus}
						<div>
							<h4 class="font-medium text-gray-700 mb-1">Response</h4>
							<div class="bg-gray-50 p-2 rounded text-xs">
								<div>Status: <span class={debugInfo.responseStatus === 200 ? 'text-green-600' : 'text-red-600'}>{debugInfo.responseStatus}</span></div>
								<div>Data Items: {debugInfo.dataCount}</div>
								<div>GeoJSON Features: {debugInfo.geoJsonFeatures}</div>
								<div>Legend Entries: {debugInfo.legendEntries}</div>
							</div>
						</div>
					{/if}
					
					<!-- Data Matching -->
					{#if debugInfo.dataMatching}
						<div>
							<h4 class="font-medium text-gray-700 mb-1">Data Matching</h4>
							<div class="bg-gray-50 p-2 rounded text-xs">
								<div>Matched: {debugInfo.dataMatching.matchedFeatures}/{debugInfo.dataMatching.totalFeatures} ({debugInfo.dataMatching.matchPercentage})</div>
								{#if debugInfo.dataMatching.unmatchedFeatures > 0}
									<div class="mt-1 text-red-600">Unmatched: {debugInfo.dataMatching.unmatchedFeatures}</div>
									<details class="mt-1">
										<summary class="cursor-pointer text-gray-600">Sample unmatched IDs</summary>
										<div class="mt-1 text-xs text-gray-500">
											{debugInfo.dataMatching.sampleUnmatchedGeoIds.join(', ')}
										</div>
									</details>
								{/if}
							</div>
						</div>
					{/if}
					
					<!-- Sample Data -->
					{#if debugInfo.sampleData && debugInfo.sampleData.length > 0}
						<div>
							<h4 class="font-medium text-gray-700 mb-1">Sample Data</h4>
							<div class="bg-gray-50 p-2 rounded text-xs max-h-32 overflow-y-auto">
								{#each debugInfo.sampleData as item}
									<div class="mb-1">
										<span class="font-medium">{item.geo_id}:</span> {item.value !== null ? item.value : 'null'} (bin: {item.bin})
									</div>
								{/each}
							</div>
						</div>
					{/if}
					
					<!-- Sample GeoJSON IDs -->
					{#if debugInfo.sampleGeoJsonIds && debugInfo.sampleGeoJsonIds.length > 0}
						<div>
							<h4 class="font-medium text-gray-700 mb-1">Sample GeoJSON IDs</h4>
							<div class="bg-gray-50 p-2 rounded text-xs">
								{debugInfo.sampleGeoJsonIds.join(', ')}
							</div>
						</div>
					{/if}
					
					<!-- Map Error Details -->
					{#if debugInfo.mapError}
						<div>
							<h4 class="font-medium text-red-700 mb-1">Map Error Details</h4>
							<div class="bg-red-50 p-2 rounded text-xs text-red-600">
								<div class="font-medium">{debugInfo.mapError.message}</div>
								{#if debugInfo.mapError.dataInfo}
									<div class="mt-1 text-gray-700">
										<div>Has Data: {debugInfo.mapError.dataInfo.hasData}</div>
										<div>Has GeoJson: {debugInfo.mapError.dataInfo.hasGeoJson}</div>
										<div>Feature Count: {debugInfo.mapError.dataInfo.featureCount}</div>
										{#if debugInfo.mapError.dataInfo.sampleFeatureGeoIds}
											<div>Sample Feature IDs: {debugInfo.mapError.dataInfo.sampleFeatureGeoIds.join(', ')}</div>
										{/if}
									</div>
								{/if}
							</div>
						</div>
					{/if}
					
					<!-- Error Info -->
					{#if debugInfo.error}
						<div>
							<h4 class="font-medium text-red-700 mb-1">Error</h4>
							<div class="bg-red-50 p-2 rounded text-xs text-red-600">
								{debugInfo.error}
							</div>
						</div>
					{/if}
				</div>
			</div>
		</div>
	{/if}
	
	<!-- Show Debug Button (when hidden) -->
	{#if !showDebug && debugInfo}
		<button 
			class="absolute top-4 right-4 z-20 bg-white rounded-lg shadow-lg border border-gray-200 px-3 py-2 text-sm font-medium text-gray-700 hover:bg-gray-50"
			on:click={() => showDebug = true}
		>
			Show Debug
		</button>
	{/if}
	
	<!-- Map element -->
	<div bind:this={mapContainer} class="w-full h-full"></div>
	
	<!-- Loading overlay -->
	{#if isLoading}
		<div 
			class="absolute inset-0 bg-white bg-opacity-75 flex items-center justify-center z-10"
			in:receive={{ key: 'loading' }}
			out:send={{ key: 'loading' }}
		>
			<div class="flex items-center space-x-3">
				<div class="animate-spin rounded-full h-8 w-8 border-b-2 border-blue-600"></div>
				<span class="text-gray-700 font-medium">Loading map data...</span>
			</div>
		</div>
	{/if}
	
	<!-- Error overlay -->
	{#if error}
		<div 
			class="absolute inset-0 bg-red-50 bg-opacity-95 flex items-center justify-center z-10"
			in:receive={{ key: 'error' }}
			out:send={{ key: 'error' }}
		>
			<div class="text-center p-6">
				<div class="text-red-600 text-xl mb-2">⚠️</div>
				<h3 class="text-red-800 font-semibold mb-2">Map Error</h3>
				<p class="text-red-700 text-sm">{error}</p>
				<button 
					class="mt-4 px-4 py-2 bg-red-600 text-white rounded hover:bg-red-700 transition-colors"
					on:click={() => {
						error = null;
						if ($areFiltersValid && $currentPrimaryIndicator && $currentGeoLevel && $currentPrimaryYear) {
							fetchMapData($currentPrimaryIndicator, $currentGeoLevel, $currentPrimaryYear);
						}
					}}
				>
					Retry
				</button>
			</div>
		</div>
	{/if}
	
	<!-- Map Control Panel -->
	<MapControlPanel
		displayYear={mapDisplayYear}
		displayIndicator={mapDisplayIndicator}
		on:yearChange={handleYearChange}
		on:indicatorChange={handleIndicatorChange}
		on:saveMap={handleSaveMap}
	/>

	<!-- Legend -->
	{#if legendData.length > 0 && !isLoading && !error}
		<div class="absolute bottom-4 left-4 z-10">
			<Legend legend={legendData} />
		</div>
	{/if}
	
	<!-- Filter validation message - only show if we don't have basic geographic context OR no variables selected -->
	{#if !$currentGeoLevel || !$currentPrimaryYear}
		<div class="absolute inset-0 bg-gray-50 bg-opacity-95 flex items-center justify-center z-10">
			<EmptyState 
				variant="selection"
				title="Configure Your Analysis"
				description="Select indicators, geography level, and years to visualize on the map."
				actionText="Open Variable Selector"
				on:click={() => {
					console.log('Map: Opening variable selector');
					showVariableSelector.set(true);
				}}
			/>
		</div>
	{:else if !$currentPrimaryIndicator && (!$currentSelectedIndicators || $currentSelectedIndicators.length === 0)}
		<div class="absolute inset-0 bg-gray-50 bg-opacity-95 flex items-center justify-center z-10">
			<EmptyState 
				variant="selection"
				title="Configure Your Analysis"
				description="Select indicators, geography level, and years to visualize on the map."
				actionText="Open Variable Selector"
				on:click={() => showVariableSelector.set(true)}
			/>
		</div>
	{/if}
	
	<!-- Hover Tooltip -->
	<MapTooltip
		feature={hoverTooltip.feature}
		position={hoverTooltip.position}
		isVisible={hoverTooltip.isVisible}
		isHover={true}
		currentIndicatorId={mapDisplayIndicator}
		currentYear={mapDisplayYear}
		on:close={() => {
			hoverTooltip = {
				isVisible: false,
				feature: null,
				position: { x: 0, y: 0 }
			};
		}}
	/>
	
	<!-- Click Tooltip -->
	<MapTooltip
		feature={clickTooltip.feature}
		position={clickTooltip.position}
		isVisible={clickTooltip.isVisible}
		isHover={false}
		currentIndicatorId={mapDisplayIndicator}
		currentYear={mapDisplayYear}
		on:close={() => {
			clickTooltip = {
				isVisible: false,
				feature: null,
				position: { x: 0, y: 0 }
			};
		}}
	/>
</div>

<style>
	/* Import Mapbox CSS */
	@import 'mapbox-gl/dist/mapbox-gl.css';
</style>
