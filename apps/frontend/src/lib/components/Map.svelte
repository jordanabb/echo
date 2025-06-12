<script lang="ts">
	import { onMount, onDestroy } from 'svelte';
	import { browser } from '$app/environment';
	import { filters, areFiltersValid } from '$lib/stores/filters';
	import { crossfade } from 'svelte/transition';
	import { quintOut } from 'svelte/easing';
	import Legend from './Legend.svelte';
	
	// Mapbox imports
	let mapboxgl: any;
	
	// Map instance and container
	let mapContainer: HTMLDivElement;
	let map: any;
	
	// Component state
	let isLoading = false;
	let error: string | null = null;
	let mapData: any = null;
	let legendData: any[] = [];
	let debugInfo: any = null;
	let showDebug = false; // Hide debug panel by default
	
	// Mapbox configuration
	const MAPBOX_TOKEN = 'pk.eyJ1Ijoiam9yZGFuYWJiIiwiYSI6ImNtOWx1Y3FsMTAwdWkybXB4ajdmbXRnZHkifQ.VnprPvy-fvxSO05l9c1LOw';
	const MAPBOX_STYLE = 'mapbox://styles/jordanabb/cmb5puoou002f01qt4r796okw';
	
	// Choropleth colors (matching backend)
	const CHOROPLETH_PALETTE = [
		'#f7fbff',
		'#c6dbef', 
		'#6baed6',
		'#2171b5',
		'#08306b'
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
					projection: 'albers'
				});
				
				// Wait for map to load
				map.on('load', () => {
					console.log('Map loaded successfully');
					// Trigger initial data fetch if filters are valid
					if ($areFiltersValid && $filters.indicator && $filters.geoLevel && $filters.year) {
						fetchMapData($filters.indicator, $filters.geoLevel, $filters.year);
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
	
	// Reactive statement to fetch data when filters change
	$: if (browser && map && $areFiltersValid && $filters.indicator && $filters.geoLevel && $filters.year) {
		// Additional validation to ensure we have valid filter values
		const hasValidFilters = $filters.indicator && 
								$filters.geoLevel && 
								$filters.year && 
								typeof $filters.indicator === 'string' && 
								typeof $filters.geoLevel === 'string' && 
								typeof $filters.year === 'number';
		
		if (hasValidFilters) {
			// Ensure map is loaded before fetching data
			if (map.loaded()) {
				fetchMapData($filters.indicator, $filters.geoLevel, $filters.year);
			} else {
				map.once('load', () => {
					fetchMapData($filters.indicator, $filters.geoLevel, $filters.year);
				});
			}
		} else {
			console.warn('Invalid filter values detected:', $filters);
		}
	}
	
	// Function to fetch map data from API
	async function fetchMapData(indicator: string, geoLevel: string, year: number) {
		if (!indicator || !geoLevel || !year) return;
		
		isLoading = true;
		error = null;
		
		try {
			const params = new URLSearchParams({
				indicator,
				geo_level: geoLevel,
				year: year.toString()
			});
			
			// Store debug info
			debugInfo = {
				requestUrl: `/api/map-view?${params}`,
				requestParams: {
					indicator,
					geo_level: geoLevel,
					year
				},
				timestamp: new Date().toISOString()
			};
			
			console.log('Fetching map data:', debugInfo);
			
			const response = await fetch(`/api/map-view?${params}`);
			
			if (!response.ok) {
				if (response.status === 404) {
					throw new Error('No data available for the selected filters');
				}
				throw new Error(`HTTP ${response.status}: ${response.statusText}`);
			}
			
			const data = await response.json();
			
			// Validate that the response data is for the correct geographic level
			if (data.geoJson?.features?.length > 0) {
				// Check a sample of features to ensure they're for the correct geo level
				const sampleFeatures = data.geoJson.features.slice(0, 10);
				const expectedGeoIdLength = getExpectedGeoIdLength(geoLevel);
				
				let invalidFeatures = 0;
				sampleFeatures.forEach((feature: any) => {
					const geoId = String(feature.properties?.geo_id || '');
					if (expectedGeoIdLength && geoId.length !== expectedGeoIdLength) {
						invalidFeatures++;
					}
				});
				
				// If more than half the sample features have incorrect geo_id lengths, 
				// this might indicate wrong geographic level data
				if (invalidFeatures > sampleFeatures.length / 2) {
					console.warn(`Potential geo level mismatch: Expected ${geoLevel} (${expectedGeoIdLength} digits), but got features with different lengths`);
				}
			}
			
			// Update debug info with response
			debugInfo = {
				...debugInfo,
				responseStatus: response.status,
				responseData: data,
				dataCount: data.data?.length || 0,
				geoJsonFeatures: data.geoJson?.features?.length || 0,
				sampleData: data.data?.slice(0, 5) || [],
				sampleGeoJsonIds: data.geoJson?.features?.slice(0, 5).map((f: any) => f.properties?.geo_id) || [],
				hasLegend: !!data.legend,
				legendEntries: data.legend?.length || 0,
				requestedGeoLevel: geoLevel,
				expectedGeoIdLength: getExpectedGeoIdLength(geoLevel)
			};
			
			console.log('Map data received:', debugInfo);
			
			// Update component state
			mapData = data;
			legendData = data.legend || [];
			
			// Update map with new data
			updateMapData(data);
			
		} catch (err) {
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
			isLoading = false;
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
					const normalizedGeoId = normalizeGeoId(String(feature.properties.geo_id), $filters.geoLevel || '');
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
			
			// Add hover effects
			let hoveredFeatureId: string | null = null;
			
			map.on('mouseenter', 'choropleth-layer', (e: any) => {
				map.getCanvas().style.cursor = 'pointer';
				
				if (e.features.length > 0) {
					if (hoveredFeatureId !== null) {
						map.setFeatureState(
							{ source: 'choropleth-data', id: hoveredFeatureId },
							{ hover: false }
						);
					}
					
					hoveredFeatureId = e.features[0].id;
					map.setFeatureState(
						{ source: 'choropleth-data', id: hoveredFeatureId },
						{ hover: true }
					);
				}
			});
			
			map.on('mouseleave', 'choropleth-layer', () => {
				map.getCanvas().style.cursor = '';
				
				if (hoveredFeatureId !== null) {
					map.setFeatureState(
						{ source: 'choropleth-data', id: hoveredFeatureId },
						{ hover: false }
					);
				}
				hoveredFeatureId = null;
			});
			
			// Add click handler for feature details
			map.on('click', 'choropleth-layer', (e: any) => {
				if (e.features.length > 0) {
					const feature = e.features[0];
					const props = feature.properties;
					
					// Create popup content
					const popupContent = `
						<div class="p-3">
							<h3 class="font-semibold text-lg mb-2">${props.geo_name || props.geo_id}</h3>
							<p class="text-sm text-gray-600 mb-1">
								<strong>Value:</strong> ${props.value !== null ? props.value.toLocaleString() : 'No data'}
							</p>
							<p class="text-sm text-gray-600">
								<strong>Geography ID:</strong> ${props.geo_id}
							</p>
						</div>
					`;
					
					new mapboxgl.Popup()
						.setLngLat(e.lngLat)
						.setHTML(popupContent)
						.addTo(map);
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
						if ($areFiltersValid && $filters.indicator && $filters.geoLevel && $filters.year) {
							fetchMapData($filters.indicator, $filters.geoLevel, $filters.year);
						}
					}}
				>
					Retry
				</button>
			</div>
		</div>
	{/if}
	
	<!-- Legend -->
	{#if legendData.length > 0 && !isLoading && !error}
		<div class="absolute bottom-4 left-4 z-10">
			<Legend legend={legendData} />
		</div>
	{/if}
	
	<!-- Filter validation message -->
	{#if !$areFiltersValid && !isLoading}
		<div class="absolute inset-0 bg-gray-50 bg-opacity-95 flex items-center justify-center z-10">
			<div class="text-center p-6">
				<div class="text-gray-400 text-xl mb-2">📊</div>
				<h3 class="text-gray-700 font-semibold mb-2">Select Filters</h3>
				<p class="text-gray-600 text-sm">Please select an indicator, geography level, and year to view the map.</p>
			</div>
		</div>
	{/if}
</div>

<style>
	/* Import Mapbox CSS */
	@import 'mapbox-gl/dist/mapbox-gl.css';
</style>
