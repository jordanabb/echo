<script lang="ts">
	import { AnalysisPane, Button, Card, DataTable, UnifiedContextBar } from '$lib/components';
	import { 
		theme, 
		isLoading
	} from '$lib/stores';
	import { 
		unifiedFilters,
		currentGeoLevel,
		currentGeoFilter,
		currentPrimaryYear,
		currentPrimaryIndicator,
		selectedIndicatorCount,
		selectedIndicatorsWithMetadata,
		areFiltersValid,
		isAnalysisReady,
		currentUrl,
		currentSelectionDescription,
		updateFilter,
		updateFilters
	} from '$lib/stores/unifiedFilters';
	import { 
		indicators,
		geographies,
		latestYear
	} from '$lib/stores/metadata';
	import { formatDate } from '$lib/utils';
	import { 
		showVariableSelector, 
		selectedView, 
		selectView, 
		allStepsCompleted,
		stepCompletion,
		navigateToView,
		type ViewType
	} from '$lib/stores/interactiveSteps';
	import { US_STATES, getStateNameByCode } from '$lib/constants/states';
	import { fly, fade } from 'svelte/transition';
	import { quintOut } from 'svelte/easing';

	let loading = false;

	function handleGetStarted() {
		// Smooth scroll to dashboard section
		const dashboardSection = document.getElementById('dashboard-section');
		if (dashboardSection) {
			dashboardSection.scrollIntoView({ behavior: 'smooth' });
		}
	}

	function toggleTheme() {
		theme.update(t => t === 'light' ? 'dark' : 'light');
	}

	const currentDate = formatDate(new Date());
	
	// Handle geography level change from step 1
	function handleGeoLevelChange(event: Event) {
		const target = event.target as HTMLSelectElement;
		const geoLevel = target.value || null;
		// Keep state filter when geography level changes
		updateFilter('geoLevel', geoLevel);
	}

	// Handle state filter toggle from step 1
	function toggleStateFilter(code: string) {
		const current = $currentGeoFilter || [];
		if (current.includes(code)) {
			updateFilter('geoFilter', current.filter((c: string) => c !== code));
		} else {
			updateFilter('geoFilter', [...current, code]);
		}
	}

	let showPageStateDropdown = false;
	let pageStateDropdownRef: HTMLDivElement;

	function handlePageClickOutside(event: MouseEvent) {
		if (showPageStateDropdown && pageStateDropdownRef && !pageStateDropdownRef.contains(event.target as Node)) {
			showPageStateDropdown = false;
		}
	}
	
	// Get display text for selected variables
	function getVariableDisplayText(): string {
		if ($selectedIndicatorCount === 0) {
			return 'Select variables';
		}
		
		if ($selectedIndicatorCount === 1) {
			return $selectedIndicatorsWithMetadata[0]?.name || 'Unknown';
		}
		
		const firstName = $selectedIndicatorsWithMetadata[0]?.name || 'Unknown';
		return `${firstName} (+${$selectedIndicatorCount - 1} more)`;
	}
	
	// Auto-navigate when all steps are completed
	$: if ($allStepsCompleted && $selectedView) {
		navigateToView($selectedView);
	}
</script>

<svelte:window on:click={handlePageClickOutside} />

<svelte:head>
	<title>ECHO Data Dashboard - Education, Community, and Housing Open Data</title>
	<meta name="description" content="Education, Community, and Housing Open Data Dashboard - Explore comprehensive data across multiple geographic levels" />
</svelte:head>

<!-- Hero Landing Section -->
<div class="h-screen bg-white relative overflow-hidden">
	<!-- Subtle Background Pattern -->
	<div class="absolute inset-0 bg-grid-pattern opacity-5"></div>
	
	<!-- Hero Content -->
	<div class="relative z-10 min-h-screen flex items-center justify-center px-4 sm:px-6 lg:px-8">
		<div class="text-center max-w-6xl mx-auto">
			<!-- Dramatic Main Title -->
			<h1 class="text-4xl sm:text-5xl md:text-7xl lg:text-9xl font-display font-black mb-4 md:mb-8 tracking-tight leading-none text-teal-800">
				ECHO
			</h1>

			<!-- Subtitle -->
			<p class="text-lg sm:text-xl md:text-2xl lg:text-3xl text-neutral-700 font-light mb-2 md:mb-4 max-w-4xl mx-auto leading-relaxed">
				Education, Community, and Housing Open Data Dashboard
			</p>
			<p class="text-sm sm:text-base md:text-lg lg:text-xl text-neutral-500 italic mb-4 md:mb-6">
				Updated and Re-Released March 2026
			</p>

			<!-- Attribution -->
			<p class="text-sm sm:text-base md:text-lg lg:text-xl text-neutral-600 font-medium mb-6 md:mb-10">
				A Product of New America's Education Funding Equity Initiative
			</p>
		</div>
	</div>

	<!-- Elegant Scroll Indicator -->
	<div class="absolute bottom-16 left-1/2 transform -tranneutral-x-1/2 animate-bounce">
		<svg class="w-8 h-8 text-neutral-400" fill="none" stroke="currentColor" viewBox="0 0 24 24">
			<path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M19 14l-7 7m0 0l-7-7m7 7V3" />
		</svg>
	</div>
</div>

<!-- Main Dashboard Homepage -->
<div class="bg-neutral-50" id="dashboard-section">

	<!-- Content Sections -->
	<div class="max-w-7xl mx-auto px-4 sm:px-6 lg:px-8 py-12">
		<!-- About Section -->
		<section class="mb-16">
			<div class="text-center mb-8 md:mb-16">
				<h2 class="text-3xl sm:text-4xl lg:text-5xl font-display font-bold text-neutral-900 mb-4 md:mb-6">
					About the ECHO Dashboard
				</h2>
				<div class="w-32 h-1.5 bg-neutral-400 mx-auto rounded-full"></div>
			</div>

			<div class="max-w-5xl mx-auto">
				<Card variant="outlined" padding="xl">
					<div class="text-neutral-700 text-base md:text-xl leading-relaxed space-y-4 md:space-y-8">
						<p class="text-lg md:text-2xl font-light text-neutral-800 leading-relaxed">
							This dashboard includes a wide range of national data related to education, housing, and community
							demographics and welfare. This data is intended for use by policymakers, advocates, journalists, and anyone
							who seeks to understand and shape social policy in their states and communities.
						</p>
						<p class="text-base md:text-lg">
							The data is presented at four geographic levels: school districts, state legislative districts, counties, and census tracts. 
							The data can be viewed in maps or data tables, and can be used to generate several kinds of charts.
						</p>
						<div class="bg-neutral-50 border-l-4 border-neutral-400 p-8 rounded-r-2xl">
							<div class="flex items-start">
								<div class="flex-shrink-0 mr-4">
									<div class="w-8 h-8 bg-neutral-600 rounded-full flex items-center justify-center">
										<svg class="w-4 h-4 text-white" fill="none" stroke="currentColor" viewBox="0 0 24 24">
											<path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M13 16h-1v-4h-1m1-4h.01M21 12a9 9 0 11-18 0 9 9 0 0118 0z" />
										</svg>
									</div>
								</div>
								<p class="font-semibold text-neutral-800 text-lg">
									Note: The dashboard is not compatible with mobile at this time. Please use a personal computer.
								</p>
							</div>
						</div>
					</div>
				</Card>
			</div>
		</section>

		<!-- How to Use Section -->
		<section class="mb-16">
			<div class="text-center mb-12">
				<h2 class="text-3xl sm:text-4xl lg:text-5xl font-display font-bold text-neutral-900">
					Explore and Analyze the Data:
				</h2>
			</div>
			
			<div class="grid grid-cols-1 md:grid-cols-3 gap-8 md:gap-16">
				<!-- Step 1: Interactive Geographic Level Selection -->
				<div
					in:fly={{ y: 50, duration: 600, delay: 100 }}
					class="transform"
				>
					<div class="bg-white rounded-2xl border border-neutral-200 p-8 hover:border-neutral-300 transition-all duration-300 group">
					<div class="text-center">
						<div class="relative mb-10">
							<div class="w-24 h-24 sm:w-32 sm:h-32 lg:w-40 lg:h-40 bg-teal-50 rounded-3xl mx-auto mb-8 flex items-center justify-center border border-teal-500">
								<svg class="w-12 h-12 sm:w-16 sm:h-16 lg:w-20 lg:h-20 text-teal-700" fill="none" stroke="currentColor" viewBox="0 0 24 24">
									<path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M17.657 16.657L13.414 20.9a1.998 1.998 0 01-2.827 0l-4.244-4.243a8 8 0 1111.314 0z"/>
									<path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M15 11a3 3 0 11-6 0 3 3 0 016 0z"/>
								</svg>
							</div>
							<div class="w-12 h-12 sm:w-14 sm:h-14 lg:w-16 lg:h-16 bg-neutral-800 text-white rounded-xl flex items-center justify-center mx-auto mb-8 font-bold text-2xl relative">
								1
								{#if $stepCompletion.step1}
									<div class="absolute -top-2 -right-2 w-6 h-6 bg-teal-700 rounded-full flex items-center justify-center">
										<svg class="w-4 h-4 text-white" fill="none" stroke="currentColor" viewBox="0 0 24 24">
											<path stroke-linecap="round" stroke-linejoin="round" stroke-width="3" d="M5 13l4 4L19 7" />
										</svg>
									</div>
								{/if}
							</div>
						</div>
						<h3 class="text-3xl font-bold text-neutral-900 mb-6">Select Geographic Unit</h3>
						<p class="text-neutral-600 leading-relaxed text-lg mb-8 font-medium">
							Choose to view data by school districts, counties, legislative districts, or census tracts
						</p>
						
						<!-- Interactive Geographic Selection -->
						<div class="mt-6 space-y-4">
							<select
								class="w-full text-lg font-medium bg-white border-2 border-neutral-200 focus:ring-4 focus:ring-neutral-300/40 focus:border-neutral-400 rounded-xl px-4 py-3 cursor-pointer hover:border-neutral-300 transition-all"
								value={$currentGeoLevel || ''}
								on:change={handleGeoLevelChange}
							>
								<option value="">Select geographic unit...</option>
								{#each Object.keys($geographies) as level}
									<option value={level}>{$geographies[level]?.name || level}</option>
								{/each}
							</select>

							<!-- Optional State Filter -->
							{#if $currentGeoLevel}
								<div class="pt-2">
									<label class="block text-sm font-medium text-neutral-600 mb-2">
										State (Optional)
									</label>
									<div class="relative" bind:this={pageStateDropdownRef}>
										<button
											type="button"
											class="w-full text-lg font-medium bg-white border-2 border-neutral-200 rounded-xl px-4 py-3 cursor-pointer hover:border-neutral-300 transition-all text-left flex items-center justify-between"
											on:click={() => showPageStateDropdown = !showPageStateDropdown}
										>
											<span>{$currentGeoFilter.length === 0 ? 'All States' : $currentGeoFilter.length === 1 ? (getStateNameByCode($currentGeoFilter[0]) || $currentGeoFilter[0]) : `${$currentGeoFilter.length} States`}</span>
											<svg class="w-5 h-5 ml-2" fill="none" stroke="currentColor" viewBox="0 0 24 24"><path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M19 9l-7 7-7-7"/></svg>
										</button>
										{#if showPageStateDropdown}
											<div class="absolute z-50 mt-1 w-full bg-white border border-neutral-200 rounded-xl shadow-lg max-h-60 overflow-y-auto">
													<button type="button" class="w-full text-left px-4 py-2 text-sm font-semibold border-b border-neutral-100 {$currentGeoFilter.length === 0 ? 'bg-teal-50 text-teal-700' : 'text-neutral-700 hover:bg-teal-50'}" on:click={() => updateFilter('geoFilter', [])}>All States</button>
												{#each US_STATES as state}
													<label class="flex items-center px-4 py-2 hover:bg-neutral-50 cursor-pointer text-sm">
														<input type="checkbox" checked={$currentGeoFilter.includes(state.code)} on:change={() => toggleStateFilter(state.code)} class="h-4 w-4 text-teal-600 border-neutral-300 rounded mr-3" />
														{state.name}
													</label>
												{/each}
											</div>
										{/if}
									</div>
									{#if $currentGeoFilter.length > 0}
										<p class="mt-2 text-sm text-neutral-700 font-medium">
											Filtering to {$currentGeoFilter.length} state{$currentGeoFilter.length !== 1 ? 's' : ''}
										</p>
									{:else}
										<p class="mt-2 text-sm text-neutral-500">
											Showing all states nationwide
										</p>
									{/if}
								</div>
							{/if}
						</div>
					</div>
					</div>
				</div>

				<!-- Step 2: Variable Selection -->
				<div
					in:fly={{ y: 50, duration: 600, delay: 200 }}
					class="transform"
				>
					<div class="bg-white rounded-2xl border border-neutral-200 p-8 hover:border-neutral-300 transition-all duration-300 group">
					<div class="text-center">
						<div class="relative mb-10">
							<div class="w-24 h-24 sm:w-32 sm:h-32 lg:w-40 lg:h-40 bg-teal-50 rounded-3xl mx-auto mb-8 flex items-center justify-center border border-teal-500">
								<svg class="w-12 h-12 sm:w-16 sm:h-16 lg:w-20 lg:h-20 text-teal-700" fill="none" stroke="currentColor" viewBox="0 0 24 24">
									<path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M9 19v-6a2 2 0 00-2-2H5a2 2 0 00-2 2v6a2 2 0 002 2h2a2 2 0 002-2zm0 0V9a2 2 0 012-2h2a2 2 0 012 2v10m-6 0a2 2 0 002 2h2a2 2 0 002-2m0 0V5a2 2 0 012-2h2a2 2 0 012 2v14a2 2 0 01-2 2h-2a2 2 0 01-2-2z"/>
								</svg>
							</div>
							<div class="w-12 h-12 sm:w-14 sm:h-14 lg:w-16 lg:h-16 bg-neutral-800 text-white rounded-xl flex items-center justify-center mx-auto mb-8 font-bold text-2xl relative">
								2
								{#if $stepCompletion.step2}
									<div class="absolute -top-2 -right-2 w-6 h-6 bg-teal-700 rounded-full flex items-center justify-center">
										<svg class="w-4 h-4 text-white" fill="none" stroke="currentColor" viewBox="0 0 24 24">
											<path stroke-linecap="round" stroke-linejoin="round" stroke-width="3" d="M5 13l4 4L19 7" />
										</svg>
									</div>
								{/if}
							</div>
						</div>
						<h3 class="text-3xl font-bold text-neutral-900 mb-6">Select Variables</h3>
						<p class="text-neutral-600 leading-relaxed text-lg mb-8 font-medium">
							Choose the data items you want to explore
						</p>
						
						<!-- Variable Selection Button -->
						<div class="mt-6">
							<button
								class="w-full text-lg font-medium bg-white text-neutral-800 border-2 border-neutral-300 rounded-xl px-6 py-3 hover:bg-neutral-50 hover:border-neutral-400 transition-all duration-200 flex items-center justify-center"
								on:click={() => $showVariableSelector = true}
							>
								<svg class="w-5 h-5 mr-2" fill="none" stroke="currentColor" viewBox="0 0 24 24">
									<path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M9 5H7a2 2 0 00-2 2v12a2 2 0 002 2h10a2 2 0 002-2V7a2 2 0 00-2-2h-2M9 5a2 2 0 002 2h2a2 2 0 002-2M9 5a2 2 0 012-2h2a2 2 0 012 2" />
								</svg>
								Select Variables
							</button>
							{#if $selectedIndicatorCount > 0}
								<p class="mt-2 text-sm text-neutral-700 font-medium">
									{$selectedIndicatorCount} variable{$selectedIndicatorCount === 1 ? '' : 's'} selected
								</p>
							{/if}
						</div>
					</div>
					</div>
				</div>

				<!-- Step 3: View Selection -->
				<div
					in:fly={{ y: 50, duration: 600, delay: 300 }}
					class="transform"
				>
					<div class="bg-white rounded-2xl border border-neutral-200 p-8 hover:border-neutral-300 transition-all duration-300 group">
					<div class="text-center">
						<div class="relative mb-10">
							<div class="w-24 h-24 sm:w-32 sm:h-32 lg:w-40 lg:h-40 bg-teal-50 rounded-3xl mx-auto mb-8 flex items-center justify-center border border-teal-500">
								<svg class="w-20 h-20 text-teal-700" fill="none" stroke="currentColor" viewBox="0 0 24 24">
									<path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M15 12a3 3 0 11-6 0 3 3 0 016 0z"/>
									<path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M2.458 12C3.732 7.943 7.523 5 12 5c4.478 0 8.268 2.943 9.542 7-1.274 4.057-5.064 7-9.542 7-4.477 0-8.268-2.943-9.542-7z"/>
								</svg>
							</div>
							<div class="w-12 h-12 sm:w-14 sm:h-14 lg:w-16 lg:h-16 bg-neutral-800 text-white rounded-xl flex items-center justify-center mx-auto mb-8 font-bold text-2xl relative">
								3
								{#if $stepCompletion.step3}
									<div class="absolute -top-2 -right-2 w-6 h-6 bg-teal-700 rounded-full flex items-center justify-center">
										<svg class="w-4 h-4 text-white" fill="none" stroke="currentColor" viewBox="0 0 24 24">
											<path stroke-linecap="round" stroke-linejoin="round" stroke-width="3" d="M5 13l4 4L19 7" />
										</svg>
									</div>
								{/if}
							</div>
						</div>
						<h3 class="text-3xl font-bold text-neutral-900 mb-6">Select View</h3>
						<p class="text-neutral-700 leading-relaxed text-lg mb-8 font-medium">
							Choose how you want to display and analyze your data
						</p>
						
						<!-- View Selection Buttons -->
						<div class="mt-6 space-y-3">
							<button
								class="w-full text-left p-4 bg-white border border-neutral-200 rounded-xl hover:border-neutral-300 hover:bg-neutral-50 transition-all duration-300 {$selectedView === 'map' ? 'border-neutral-500 bg-neutral-50' : ''}"
								on:click={() => selectView('map')}
							>
								<div class="flex items-center">
									<div class="w-8 h-8 rounded-lg bg-teal-700 flex items-center justify-center mr-3">
										<svg class="w-4 h-4 text-white" fill="none" stroke="currentColor" viewBox="0 0 24 24">
											<path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M17.657 16.657L13.414 20.9a1.998 1.998 0 01-2.827 0l-4.244-4.243a8 8 0 1111.314 0z"/>
											<path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M15 11a3 3 0 11-6 0 3 3 0 016 0z"/>
										</svg>
									</div>
									<div class="flex-1">
										<div class="font-semibold text-neutral-900">Map View</div>
										<div class="text-sm text-neutral-500">Interactive, color-coded maps</div>
									</div>
									{#if $selectedView === 'map'}
										<svg class="w-5 h-5 text-neutral-600 ml-auto" fill="currentColor" viewBox="0 0 20 20">
											<path fill-rule="evenodd" d="M16.707 5.293a1 1 0 010 1.414l-8 8a1 1 0 01-1.414 0l-4-4a1 1 0 011.414-1.414L8 12.586l7.293-7.293a1 1 0 011.414 0z" clip-rule="evenodd" />
										</svg>
									{/if}
								</div>
							</button>

							<button
								class="w-full text-left p-4 bg-white border border-neutral-200 rounded-xl hover:border-neutral-300 hover:bg-neutral-50 transition-all duration-300 {$selectedView === 'table' ? 'border-neutral-500 bg-neutral-50' : ''}"
								on:click={() => selectView('table')}
							>
								<div class="flex items-center">
									<div class="w-8 h-8 rounded-lg bg-teal-700 flex items-center justify-center mr-3">
										<svg class="w-4 h-4 text-white" fill="none" stroke="currentColor" viewBox="0 0 24 24">
											<path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M3 10h18M3 14h18m-9-4v8m-7 0V4a1 1 0 011-1h12a1 1 0 011 1v16a1 1 0 01-1 1H4a1 1 0 01-1-1z"/>
										</svg>
									</div>
									<div class="flex-1">
										<div class="font-semibold text-neutral-900">Table View</div>
										<div class="text-sm text-neutral-500">Comprehensive data tables</div>
									</div>
									{#if $selectedView === 'table'}
										<svg class="w-5 h-5 text-neutral-600 ml-auto" fill="currentColor" viewBox="0 0 20 20">
											<path fill-rule="evenodd" d="M16.707 5.293a1 1 0 010 1.414l-8 8a1 1 0 01-1.414 0l-4-4a1 1 0 011.414-1.414L8 12.586l7.293-7.293a1 1 0 011.414 0z" clip-rule="evenodd" />
										</svg>
									{/if}
								</div>
							</button>

							<button
								class="w-full text-left p-4 bg-white border border-neutral-200 rounded-xl hover:border-neutral-300 hover:bg-neutral-50 transition-all duration-300 {$selectedView === 'chart' ? 'border-neutral-500 bg-neutral-50' : ''}"
								on:click={() => selectView('chart')}
							>
								<div class="flex items-center">
									<div class="w-8 h-8 rounded-lg bg-teal-700 flex items-center justify-center mr-3">
										<svg class="w-4 h-4 text-white" fill="none" stroke="currentColor" viewBox="0 0 24 24">
											<path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M9 19v-6a2 2 0 00-2-2H5a2 2 0 00-2 2v6a2 2 0 002 2h2a2 2 0 002-2zm0 0V9a2 2 0 012-2h2a2 2 0 012 2v10m-6 0a2 2 0 002 2h2a2 2 0 002-2m0 0V5a2 2 0 012-2h2a2 2 0 012 2v14a2 2 0 01-2 2h-2a2 2 0 01-2-2z"/>
										</svg>
									</div>
									<div class="flex-1">
										<div class="font-semibold text-neutral-900">Chart View</div>
										<div class="text-sm text-neutral-500">Data visualizations</div>
									</div>
									{#if $selectedView === 'chart'}
										<svg class="w-5 h-5 text-neutral-600 ml-auto" fill="currentColor" viewBox="0 0 20 20">
											<path fill-rule="evenodd" d="M16.707 5.293a1 1 0 010 1.414l-8 8a1 1 0 01-1.414 0l-4-4a1 1 0 011.414-1.414L8 12.586l7.293-7.293a1 1 0 011.414 0z" clip-rule="evenodd" />
										</svg>
									{/if}
								</div>
							</button>
						</div>
					</div>
					</div>
				</div>
			</div>
		</section>

	</div>
</div>

<!-- Interactive Dashboard Interface -->
<div class="bg-white" id="interface-section">
	<!-- Unified Context Bar -->
	<UnifiedContextBar />

	<div class="max-w-7xl mx-auto px-4 sm:px-6 lg:px-8 py-12 border-b border-neutral-200" style="display: none;">
		<div class="grid grid-cols-1 xl:grid-cols-3 gap-8">
			<!-- Current State Display -->
			<div class="xl:col-span-2 space-y-6" style="display: none;">
				<Card variant="elevated">
					<h3 class="text-xl font-semibold text-neutral-900 mb-6">Current Context</h3>
					
					<div class="space-y-4">
						<!-- Current URL -->
						<div>
							<label class="block text-sm font-medium text-neutral-700 mb-2">
								Current URL
							</label>
							<div class="bg-neutral-50 border border-neutral-200 rounded-md p-3">
								<code class="text-xs text-neutral-800 break-all">{$currentUrl}</code>
							</div>
						</div>

						<!-- Filter Values -->
						<div>
							<label class="block text-sm font-medium text-neutral-700 mb-2">
								Unified Filter State
							</label>
							<div class="bg-neutral-50 border border-neutral-200 rounded-md p-3">
								<pre class="text-xs text-neutral-800">{JSON.stringify($unifiedFilters, null, 2)}</pre>
							</div>
						</div>

						<!-- Validation Status -->
						<div>
							<label class="block text-sm font-medium text-neutral-700 mb-2">
								Validation Status
							</label>
							<div class="flex items-center space-x-2">
								{#if $areFiltersValid}
									<div class="w-3 h-3 bg-green-500 rounded-full"></div>
									<span class="text-sm text-green-700">Valid - Ready to fetch data</span>
								{:else}
									<div class="w-3 h-3 bg-amber-500 rounded-full"></div>
									<span class="text-sm text-amber-700">Invalid - Missing or incompatible filters</span>
								{/if}
							</div>
						</div>

						<!-- Context Summary -->
						<div class="grid grid-cols-1 md:grid-cols-3 gap-4">
							<div class="bg-teal-50 border border-teal-200 rounded-lg p-3">
								<div class="text-xs font-medium text-teal-700 mb-1">Geography</div>
								<div class="text-sm text-teal-900">
									{$currentGeoLevel ? $geographies[$currentGeoLevel]?.name || $currentGeoLevel : 'Not selected'}
								</div>
							</div>
							<div class="bg-green-50 border border-green-200 rounded-lg p-3">
								<div class="text-xs font-medium text-green-700 mb-1">Year</div>
								<div class="text-sm text-green-900">
									{$currentPrimaryYear || 'Not selected'}
								</div>
							</div>
							<div class="bg-purple-50 border border-purple-200 rounded-lg p-3">
								<div class="text-xs font-medium text-purple-700 mb-1">Variables</div>
								<div class="text-sm text-purple-900">
									{$selectedIndicatorCount} selected
								</div>
							</div>
						</div>
					</div>
				</Card>
			</div>

			<!-- Features -->
			<div class="space-y-6" style="display: none;">
				<!-- Instructions -->
				<Card variant="outline">
					<div>
						<h4 class="text-lg font-semibold text-neutral-900 mb-3">
							🚀 Streamlined Features
						</h4>
						<ul class="text-sm text-neutral-600 space-y-2">
							<li class="flex items-start">
								<span class="text-teal-600 mr-2">•</span>
								<span><strong>Unified Context:</strong> One selection affects all views</span>
							</li>
							<li class="flex items-start">
								<span class="text-teal-600 mr-2">•</span>
								<span><strong>Smart Defaults:</strong> Intelligent cascading selections</span>
							</li>
							<li class="flex items-start">
								<span class="text-teal-600 mr-2">•</span>
								<span><strong>Modal Variable Selector:</strong> Powerful multi-selection interface</span>
							</li>
							<li class="flex items-start">
								<span class="text-teal-600 mr-2">•</span>
								<span><strong>URL Sync:</strong> Every change updates the shareable URL</span>
							</li>
							<li class="flex items-start">
								<span class="text-teal-600 mr-2">•</span>
								<span><strong>Context Preservation:</strong> Settings persist across view switches</span>
							</li>
						</ul>
					</div>
				</Card>

				<!-- Metadata Info -->
				<Card variant="elevated">
					<h4 class="text-lg font-semibold text-neutral-900 mb-3">Available Data</h4>
					<div class="text-sm text-neutral-600 space-y-1">
						<p><strong>Indicators:</strong> {$indicators.length}</p>
						<p><strong>Geography Levels:</strong> {Object.keys($geographies).length}</p>
						<p><strong>Latest Year:</strong> {$latestYear || 'N/A'}</p>
					</div>
				</Card>
			</div>
		</div>
	</div>

	<!-- Data Views Section -->
	<div id="analysis-section" class="max-w-7xl mx-auto px-4 sm:px-6 lg:px-8 py-12 border-b border-neutral-200">
		<div class="text-center mb-12">
			<h2 class="text-4xl font-display font-bold text-neutral-900 mb-4">
				Data Views
			</h2>
			<p class="text-xl text-neutral-600 max-w-2xl mx-auto">
				Explore data through maps, tables, and charts
			</p>
		</div>

		<!-- Analysis Pane Container -->
		<div class="bg-white rounded-2xl border border-neutral-200 overflow-hidden">
			<AnalysisPane />
		</div>

	</div>

	<!-- Footer -->
	<footer class="bg-neutral-50 border-t border-neutral-200 py-16">
		<div class="max-w-7xl mx-auto px-4 sm:px-6 lg:px-8 text-center">
			<div class="flex items-center justify-center gap-3 mb-6">
				<p class="text-neutral-700 text-lg">
					Developed by <a
						href="https://www.newamerica.org/prek-12-education/education-funding-equity/about/"
						target="_blank"
						rel="noopener noreferrer"
						class="text-teal-800 hover:text-teal-900 transition-colors duration-200 underline font-medium"
					>
						New America's Education Funding Equity Initiative
					</a>
				</p>
			</div>
			<div class="flex justify-center space-x-6">
				<Button variant="ghost" size="sm">
					Documentation
				</Button>
				<Button variant="ghost" size="sm">
					GitHub
				</Button>
				<Button variant="ghost" size="sm" on:click={toggleTheme}>
					Toggle Theme
				</Button>
			</div>
		</div>
	</footer>
</div>

<style>
	.bg-grid-pattern {
		background-image: 
			linear-gradient(rgba(0, 0, 0, 0.05) 1px, transparent 1px),
			linear-gradient(90deg, rgba(0, 0, 0, 0.05) 1px, transparent 1px);
		background-size: 20px 20px;
	}

	/* Debug sections - hidden from UI but preserved for debugging */
	.debug-section {
		display: none !important;
	}

	/* Uncomment the line below to show debug sections when needed */
	/* .debug-section { display: block !important; } */

	/* Smooth scrolling */
	html {
		scroll-behavior: smooth;
	}

	/* Custom scrollbar */
	::-webkit-scrollbar {
		width: 8px;
	}

	::-webkit-scrollbar-track {
		background: #f8fafc;
	}

	::-webkit-scrollbar-thumb {
		background: #94a3b8;
		border-radius: 4px;
	}

	::-webkit-scrollbar-thumb:hover {
		background: #64748b;
	}
</style>
