<script lang="ts">
	import { onMount, onDestroy } from 'svelte';
	import { browser } from '$app/environment';
	import { PUBLIC_MAPBOX_TOKEN } from '$env/static/public';
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
	import { apiUrl } from '$lib/api';
	import { showVariableSelector } from '$lib/stores/interactiveSteps';
	import { US_STATES, getStateNameByCode } from '$lib/constants/states';
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

	// Request management - cancel stale requests
	let currentAbortController: AbortController | null = null;
	let fetchRequestId = 0;
	let fetchDebounceTimer: ReturnType<typeof setTimeout> | null = null;
	
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

	// Geography search state
	let geoSearchQuery = '';
	let geoSearchResults: Array<{ geo_id: string; geo_name: string; state: string }> = [];
	let geoSearchOpen = false;
	let highlightedGeoId: string | null = null;
	let highlightedGeoName: string | null = null;
	let geoSearchInputEl: HTMLInputElement;
	let currentGeoJsonData: any = null; // Keep reference for search

	function getStateName(geoId: string): string {
		const fips = geoId.substring(0, 2);
		return getStateNameByCode(fips) || '';
	}

	function searchGeographies(query: string) {
		if (!query || query.length < 2 || !currentGeoJsonData?.features) {
			geoSearchResults = [];
			return;
		}

		const lower = query.toLowerCase();
		const seen = new Set<string>();
		geoSearchResults = currentGeoJsonData.features
			.filter((f: any) => {
				const name = f.properties?.geo_name || f.properties?.name || '';
				const id = f.properties?.geo_id || '';
				if (seen.has(id)) return false;
				const stateName = getStateName(id);
				const match = name.toLowerCase().includes(lower) || id.includes(lower) || stateName.toLowerCase().includes(lower);
				if (match) seen.add(id);
				return match;
			})
			.slice(0, 20)
			.map((f: any) => {
				const id = f.properties.geo_id;
				return {
					geo_id: id,
					geo_name: f.properties.geo_name || f.properties.name || id,
					state: getStateName(id)
				};
			});
	}

	function selectSearchResult(result: { geo_id: string; geo_name: string; state: string }) {
		highlightedGeoId = result.geo_id;
		highlightedGeoName = result.geo_name;
		applySearchHighlight();
		flyToGeo(result.geo_id);
		geoSearchQuery = '';
		geoSearchResults = [];
		geoSearchOpen = false;
	}

	function clearSearchHighlight() {
		highlightedGeoId = null;
		highlightedGeoName = null;
		applySearchHighlight();
	}

	function applySearchHighlight() {
		if (!map) return;
		if (map.getLayer('search-highlight')) map.removeLayer('search-highlight');
		if (map.getLayer('search-highlight-stroke')) map.removeLayer('search-highlight-stroke');

		if (!highlightedGeoId) return;

		const filterExpr: any = ['==', ['get', 'geo_id'], highlightedGeoId];

		map.addLayer({
			id: 'search-highlight',
			type: 'fill',
			source: 'choropleth-data',
			paint: {
				'fill-color': 'rgba(245, 158, 11, 0.35)',
			},
			filter: filterExpr
		});

		map.addLayer({
			id: 'search-highlight-stroke',
			type: 'line',
			source: 'choropleth-data',
			paint: {
				'line-color': 'rgba(245, 158, 11, 1)',
				'line-width': 2.5,
			},
			filter: filterExpr
		});
	}

	function flyToGeo(geoId: string) {
		if (!map || !currentGeoJsonData?.features) return;

		const feature = currentGeoJsonData.features.find((f: any) => f.properties?.geo_id === geoId);
		if (!feature) return;

		const coords: number[][] = [];
		function extractCoords(geom: any) {
			if (Array.isArray(geom[0]) && Array.isArray(geom[0][0])) {
				geom.forEach(extractCoords);
			} else if (Array.isArray(geom[0])) {
				coords.push(...geom);
			}
		}
		if (feature.geometry?.coordinates) {
			extractCoords(feature.geometry.coordinates);
		}

		if (coords.length > 0) {
			let minLng = Infinity, maxLng = -Infinity, minLat = Infinity, maxLat = -Infinity;
			for (const c of coords) {
				if (c[0] < minLng) minLng = c[0];
				if (c[0] > maxLng) maxLng = c[0];
				if (c[1] < minLat) minLat = c[1];
				if (c[1] > maxLat) maxLat = c[1];
			}
			map.fitBounds([[minLng, minLat], [maxLng, maxLat]], { padding: 80, maxZoom: 12, duration: 1000 });
		}
	}

	$: searchGeographies(geoSearchQuery);

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

	// Handle value filter from legend slider
	function handleValueFilter(event: CustomEvent) {
		if (!map || !map.getLayer('choropleth-layer')) return;

		const filter = event.detail;
		if (filter === null) {
			// Reset to default opacity
			map.setPaintProperty('choropleth-layer', 'fill-opacity', 0.8);
			map.setPaintProperty('choropleth-stroke', 'line-opacity', 0.8);
		} else {
			// Dim features outside the value range
			const opacityExpr: any = [
				'case',
				// No data features: always dim
				['==', ['get', 'bin'], -1], 0.05,
				// Features with value in range: full opacity
				['all',
					['has', 'value'],
					['!=', ['typeof', ['get', 'value']], 'string'],
					['>=', ['get', 'value'], filter.min],
					['<=', ['get', 'value'], filter.max]
				], 0.8,
				// Out of range: very dim
				0.05
			];
			map.setPaintProperty('choropleth-layer', 'fill-opacity', opacityExpr);
			map.setPaintProperty('choropleth-stroke', 'line-opacity', [
				'case',
				['==', ['get', 'bin'], -1], 0.1,
				['all',
					['has', 'value'],
					['!=', ['typeof', ['get', 'value']], 'string'],
					['>=', ['get', 'value'], filter.min],
					['<=', ['get', 'value'], filter.max]
				], 0.8,
				0.1
			]);
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
		if ($currentGeoFilter && $currentGeoFilter.length > 0) {
			const stateNames = $currentGeoFilter.map(code => US_STATES.find(s => s.code === code)?.name || code);
			subtitle += ` (${stateNames.join(', ')})`;
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
	const MAPBOX_TOKEN = PUBLIC_MAPBOX_TOKEN;
	const MAPBOX_STYLE = 'mapbox://styles/jordanabb/cmb5puoou002f01qt4r796okw';
	
	// Choropleth colors (teal sequential palette)
	const CHOROPLETH_PALETTE = [
		'#E4F7F4',  // Teal-10
		'#6DDED1',  // Teal-30
		'#08ACA6',  // Teal-50
		'#027272',  // Teal-70
		'#023A3E'   // Teal-90
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
		if (map) map.remove();
		if (fetchDebounceTimer) clearTimeout(fetchDebounceTimer);
		if (currentAbortController) currentAbortController.abort();
	});
	
	// Debounced map data loader — single reactive block for all filter changes
	function debouncedFetchMap() {
		if (fetchDebounceTimer) clearTimeout(fetchDebounceTimer);
		fetchDebounceTimer = setTimeout(() => {
			if (!browser || !map || !$currentGeoLevel || !$currentPrimaryYear) return;

			let indicatorToDisplay: string | null = null;
			if ($currentPrimaryIndicator && typeof $currentPrimaryIndicator === 'string') {
				indicatorToDisplay = $currentPrimaryIndicator;
			} else if ($currentSelectedIndicators && $currentSelectedIndicators.length > 0) {
				indicatorToDisplay = $currentSelectedIndicators[0];
			}

			const doFetch = () => {
				if (indicatorToDisplay) {
					fetchMapData(indicatorToDisplay, $currentGeoLevel, $currentPrimaryYear);
				} else {
					fetchGeographicBoundaries($currentGeoLevel, $currentPrimaryYear);
				}
			};

			if (map.loaded()) {
				doFetch();
			} else {
				map.once('load', doFetch);
			}
		}, 150);
	}

	// Single reactive statement — triggers on any filter change
	$: if (browser && map && $filtersInitialized && $currentGeoLevel && $currentPrimaryYear) {
		// Touch all reactive dependencies so Svelte tracks them
		void $currentPrimaryIndicator;
		void $currentSelectedIndicators;
		void $currentGeoFilter;
		debouncedFetchMap();
	}
	
	// Function to generate cache key for geometries
	function getGeometryCacheKey(geoLevel: string, year: number, stateFilter: string[]): string {
		return `${geoLevel}_${year}_${stateFilter.length > 0 ? stateFilter.sort().join(',') : 'all'}`;
	}
	
	// Function to fetch geometries (with caching)
	async function fetchGeometries(geoLevel: string, year: number, signal?: AbortSignal): Promise<any> {
		const cacheKey = getGeometryCacheKey(geoLevel, year, $currentGeoFilter);

		// Check if geometries are already cached
		if (geometryCache.has(cacheKey)) {
			return geometryCache.get(cacheKey);
		}

		const params = new URLSearchParams({
			geo_level: geoLevel,
			year: year.toString()
		});

		// Add state filter if selected
		if ($currentGeoFilter && $currentGeoFilter.length > 0) {
			params.set('state_filter', $currentGeoFilter.join(','));
		}

		const response = await fetch(apiUrl(`/api/geometries?${params}`), { signal });

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
	async function fetchIndicatorData(indicator: string, geoLevel: string, year: number, signal?: AbortSignal): Promise<any> {
		const params = new URLSearchParams({
			indicator,
			geo_level: geoLevel,
			year: year.toString()
		});

		// Add state filter if selected
		if ($currentGeoFilter && $currentGeoFilter.length > 0) {
			params.set('state_filter', $currentGeoFilter.join(','));
		}

		const response = await fetch(apiUrl(`/api/indicator-data?${params}`), { signal });

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

		// Cancel any in-flight request
		if (currentAbortController) {
			currentAbortController.abort();
		}
		const abortController = new AbortController();
		currentAbortController = abortController;
		const thisRequestId = ++fetchRequestId;

		isLoading = true;
		error = null;

		try {
			const geometryCacheKey = getGeometryCacheKey(geoLevel, year, $currentGeoFilter);
			const needsNewGeometry = currentGeometryKey !== geometryCacheKey;

			let geometryData: any;

			if (needsNewGeometry) {
				geometryData = await fetchGeometries(geoLevel, year, abortController.signal);
				currentGeometryKey = geometryCacheKey;
				isGeometryCached = true;
			} else {
				geometryData = geometryCache.get(geometryCacheKey);
			}

			// Discard if a newer request has been made
			if (thisRequestId !== fetchRequestId) return;

			const boundariesData = {
				geoJson: geometryData.geoJson,
				data: [],
				legend: []
			};

			mapData = boundariesData;
			legendData = [];
			updateBoundariesOnly(boundariesData);

		} catch (err) {
			if (err instanceof DOMException && err.name === 'AbortError') return;
			if (thisRequestId !== fetchRequestId) return;
			console.error('Error fetching geographic boundaries:', err);
			error = err instanceof Error ? err.message : 'Failed to load geographic boundaries';
			mapData = null;
			legendData = [];
		} finally {
			if (thisRequestId === fetchRequestId) {
				isLoading = false;
			}
		}
	}

	// Optimized function to fetch map data with smart caching
	async function fetchMapData(indicator: string, geoLevel: string, year: number) {
		if (!indicator || !geoLevel || !year) return;

		// Cancel any in-flight request
		if (currentAbortController) {
			currentAbortController.abort();
		}
		const abortController = new AbortController();
		currentAbortController = abortController;
		const thisRequestId = ++fetchRequestId;

		isLoading = true;
		error = null;

		try {
			const geometryCacheKey = getGeometryCacheKey(geoLevel, year, $currentGeoFilter);
			const needsNewGeometry = currentGeometryKey !== geometryCacheKey;

			let geometryData: any;
			let indicatorData: any;

			if (needsNewGeometry) {
				[geometryData, indicatorData] = await Promise.all([
					fetchGeometries(geoLevel, year, abortController.signal),
					fetchIndicatorData(indicator, geoLevel, year, abortController.signal)
				]);
				currentGeometryKey = geometryCacheKey;
				isGeometryCached = true;
			} else {
				geometryData = geometryCache.get(geometryCacheKey);
				indicatorData = await fetchIndicatorData(indicator, geoLevel, year, abortController.signal);
			}

			// Discard if a newer request has been made
			if (thisRequestId !== fetchRequestId) return;

			// Combine geometry and indicator data
			const combinedData = {
				geoJson: geometryData.geoJson,
				data: indicatorData.data,
				legend: indicatorData.legend
			};

			// Update component state
			mapData = combinedData;

			// Generate legend data using the actual map colors
			legendData = generateLegendFromMapColors(indicatorData.legend || []);

			// Update map with new data (only fit bounds when geometry changed)
			updateMapData(combinedData, needsNewGeometry);

		} catch (err) {
			// Ignore aborted requests
			if (err instanceof DOMException && err.name === 'AbortError') return;
			// Ignore if a newer request superseded this one
			if (thisRequestId !== fetchRequestId) return;

			console.error('Error fetching map data:', err);
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
			if (thisRequestId === fetchRequestId) {
				isLoading = false;
			}
		}
	}

	// Function to update map with boundaries only (no data visualization)
	function updateBoundariesOnly(data: any) {
		if (!map || !data) return;

		try {
			// Remove existing layers and sources
			if (map.getLayer('search-highlight')) map.removeLayer('search-highlight');
			if (map.getLayer('search-highlight-stroke')) map.removeLayer('search-highlight-stroke');
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
			currentGeoJsonData = geoJsonWithBoundaries;
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
					if (hoveredFeatureId !== null && hoveredFeatureId !== undefined) {
						map.setFeatureState(
							{ source: 'choropleth-data', id: hoveredFeatureId },
							{ hover: false }
						);
					}
					
					hoveredFeatureId = feature.id;
					if (hoveredFeatureId !== null && hoveredFeatureId !== undefined) {
						map.setFeatureState(
							{ source: 'choropleth-data', id: hoveredFeatureId },
							{ hover: true }
						);
					}
					
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
			
			// Fit map to bounds
			if (geoJsonWithBoundaries.features.length > 0) {
				if ($currentGeoFilter && $currentGeoFilter.length > 0) {
					// State filter active: fit to the state's actual bounds
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
				} else {
					// National view: reset to default US center/zoom
					map.jumpTo({ center: [-98.5, 39.8], zoom: 3 });
				}
			}
			
		} catch (err) {
			console.error('Error updating boundaries:', err);
			error = `Failed to update map boundaries: ${err instanceof Error ? err.message : 'Unknown error'}`;
		}
	}

	// Function to update map with new data
	function updateMapData(data: any, fitToData: boolean = true) {
		if (!map || !data) return;

		try {
			// Remove existing layers and sources
			if (map.getLayer('search-highlight')) map.removeLayer('search-highlight');
			if (map.getLayer('search-highlight-stroke')) map.removeLayer('search-highlight-stroke');
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
			currentGeoJsonData = geoJsonWithData;
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
					if (hoveredFeatureId !== null && hoveredFeatureId !== undefined) {
						map.setFeatureState(
							{ source: 'choropleth-data', id: hoveredFeatureId },
							{ hover: false }
						);
					}
					
					hoveredFeatureId = feature.id;
					if (hoveredFeatureId !== null && hoveredFeatureId !== undefined) {
						map.setFeatureState(
							{ source: 'choropleth-data', id: hoveredFeatureId },
							{ hover: true }
						);
					}
					
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

			// Touch event handler for mobile - show tooltip on tap
			map.on('touchend', 'choropleth-layer', (e: any) => {
				// Prevent if user was panning/zooming (check if touch moved significantly)
				if (e.originalEvent && e.originalEvent.touches && e.originalEvent.touches.length > 0) {
					return; // Multi-touch, likely a gesture
				}

				const features = map.queryRenderedFeatures(e.point, { layers: ['choropleth-layer'] });
				if (features.length > 0) {
					const feature = features[0];
					const rect = mapContainer.getBoundingClientRect();

					// Hide hover tooltip
					hoverTooltip = {
						isVisible: false,
						feature: null,
						position: { x: 0, y: 0 }
					};

					// Show click tooltip at touch position
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

			// Re-apply search highlights if any
			if (highlightedGeoId) {
				applySearchHighlight();
			}

			// Fit map to bounds only when geometry changed (not on indicator switch)
			if (fitToData && geoJsonWithData.features.length > 0) {
				if ($currentGeoFilter && $currentGeoFilter.length > 0) {
					// State filter active: fit to the state's actual bounds
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
				} else {
					// National view: reset to default US center/zoom
					map.jumpTo({ center: [-98.5, 39.8], zoom: 3 });
				}
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
<div class="relative w-full h-full bg-neutral-100 rounded-lg overflow-hidden">
	<!-- Debug Panel -->
	{#if showDebug && debugInfo}
		<div class="absolute top-4 right-4 z-20 bg-white rounded-lg shadow-lg border border-neutral-200 max-w-md">
			<div class="p-4">
				<div class="flex items-center justify-between mb-3">
					<h3 class="font-semibold text-neutral-900">Debug Info</h3>
					<button 
						class="text-neutral-500 hover:text-neutral-700"
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
						<h4 class="font-medium text-neutral-700 mb-1">Request</h4>
						<div class="bg-neutral-50 p-2 rounded text-xs font-mono">
							<div>Indicator: {debugInfo.requestParams?.indicator}</div>
							<div>Geo Level: {debugInfo.requestParams?.geo_level}</div>
							<div>Year: {debugInfo.requestParams?.year}</div>
						</div>
					</div>
					
					<!-- Response Info -->
					{#if debugInfo.responseStatus}
						<div>
							<h4 class="font-medium text-neutral-700 mb-1">Response</h4>
							<div class="bg-neutral-50 p-2 rounded text-xs">
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
							<h4 class="font-medium text-neutral-700 mb-1">Data Matching</h4>
							<div class="bg-neutral-50 p-2 rounded text-xs">
								<div>Matched: {debugInfo.dataMatching.matchedFeatures}/{debugInfo.dataMatching.totalFeatures} ({debugInfo.dataMatching.matchPercentage})</div>
								{#if debugInfo.dataMatching.unmatchedFeatures > 0}
									<div class="mt-1 text-red-600">Unmatched: {debugInfo.dataMatching.unmatchedFeatures}</div>
									<details class="mt-1">
										<summary class="cursor-pointer text-neutral-600">Sample unmatched IDs</summary>
										<div class="mt-1 text-xs text-neutral-500">
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
							<h4 class="font-medium text-neutral-700 mb-1">Sample Data</h4>
							<div class="bg-neutral-50 p-2 rounded text-xs max-h-32 overflow-y-auto">
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
							<h4 class="font-medium text-neutral-700 mb-1">Sample GeoJSON IDs</h4>
							<div class="bg-neutral-50 p-2 rounded text-xs">
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
									<div class="mt-1 text-neutral-700">
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
			class="absolute top-4 right-4 z-20 bg-white rounded-lg shadow-lg border border-neutral-200 px-3 py-2 text-sm font-medium text-neutral-700 hover:bg-neutral-50"
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
				<span class="text-neutral-700 font-medium">Loading map data...</span>
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

	<!-- Geography Search -->
	{#if !isLoading && !error && mapData}
		<div class="absolute top-2 left-2 md:top-4 md:left-4 z-20 w-64">
			<div class="relative">
				<div class="flex items-center bg-white rounded-lg shadow-lg border border-neutral-200 overflow-hidden">
					<svg class="w-4 h-4 text-neutral-400 ml-3 flex-shrink-0" fill="none" stroke="currentColor" viewBox="0 0 24 24">
						<path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M21 21l-6-6m2-5a7 7 0 11-14 0 7 7 0 0114 0z" />
					</svg>
					<input
						type="text"
						bind:value={geoSearchQuery}
						bind:this={geoSearchInputEl}
						on:focus={() => geoSearchOpen = true}
						on:blur={() => setTimeout(() => geoSearchOpen = false, 200)}
						placeholder="Search geographies..."
						class="w-full px-2 py-2 text-sm text-neutral-700 bg-transparent outline-none placeholder-neutral-400"
					/>
					{#if geoSearchQuery || highlightedGeoId}
						<button
							class="mr-2 text-neutral-400 hover:text-neutral-600"
							on:mousedown|preventDefault={() => { geoSearchQuery = ''; geoSearchResults = []; clearSearchHighlight(); }}
						>
							<svg class="w-4 h-4" fill="none" stroke="currentColor" viewBox="0 0 24 24">
								<path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M6 18L18 6M6 6l12 12" />
							</svg>
						</button>
					{/if}
				</div>

				<!-- Search results dropdown -->
				{#if geoSearchOpen && geoSearchResults.length > 0}
					<div class="absolute top-full mt-1 w-full bg-white rounded-lg shadow-lg border border-neutral-200 max-h-60 overflow-y-auto">
						{#each geoSearchResults as result}
							<button
								class="w-full text-left px-3 py-2 hover:bg-amber-50 transition-colors border-b border-neutral-100 last:border-b-0"
								on:mousedown|preventDefault={() => selectSearchResult(result)}
							>
								<div class="text-sm font-medium text-neutral-700">{result.geo_name}</div>
								{#if result.state}
									<div class="text-xs text-neutral-400">{result.state}</div>
								{/if}
							</button>
						{/each}
					</div>
				{/if}
				{#if geoSearchOpen && geoSearchQuery.length >= 2 && geoSearchResults.length === 0}
					<div class="absolute top-full mt-1 w-full bg-white rounded-lg shadow-lg border border-neutral-200 px-3 py-2 text-sm text-neutral-500">
						No results found
					</div>
				{/if}
			</div>

		</div>
	{/if}

	<!-- Legend -->
	{#if legendData.length > 0 && !isLoading && !error}
		<div class="absolute bottom-2 left-2 md:bottom-4 md:left-4 z-10 max-w-[140px] md:max-w-none">
			<Legend legend={legendData} indicatorName={$selectedIndicatorsWithMetadata.find(ind => ind.id === mapDisplayIndicator)?.name || ''} on:filterChange={handleValueFilter} />
		</div>
	{/if}
	
	<!-- Filter validation message - only show if we don't have basic geographic context OR no variables selected -->
	{#if !$currentGeoLevel || !$currentPrimaryYear}
		<div class="absolute inset-0 bg-neutral-50 bg-opacity-95 flex items-center justify-center z-10">
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
		<div class="absolute inset-0 bg-neutral-50 bg-opacity-95 flex items-center justify-center z-10">
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
