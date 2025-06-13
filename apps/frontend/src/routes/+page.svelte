<script lang="ts">
	import { AnalysisPane, Button, Card, DataTable, Map, UnifiedContextBar } from '$lib/components';
	import { 
		theme, 
		isLoading
	} from '$lib/stores';
	import { 
		unifiedFilters,
		currentGeoLevel,
		currentPrimaryYear,
		currentPrimaryIndicator,
		selectedIndicatorCount,
		selectedIndicatorsWithMetadata,
		areFiltersValid,
		isAnalysisReady,
		currentUrl,
		currentSelectionDescription,
		updateFilter
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
		updateFilter('geoLevel', geoLevel);
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

<svelte:head>
	<title>ECHO Data Dashboard - Education, Community, and Housing Open Data</title>
	<meta name="description" content="Education, Community, and Housing Open Data Dashboard - Explore comprehensive data across multiple geographic levels" />
</svelte:head>

<!-- Hero Landing Section -->
<div class="min-h-screen bg-gradient-to-br from-slate-50 via-white to-teal-50 relative overflow-hidden">
	<!-- Sophisticated Background Elements -->
	<div class="absolute inset-0 bg-grid-pattern opacity-5"></div>
	<div class="absolute inset-0 bg-gradient-to-t from-teal-100/30 via-transparent to-transparent"></div>
	
	<!-- Floating Orbs for Visual Interest -->
	<div class="absolute top-20 left-20 w-32 h-32 bg-teal-200/20 rounded-full blur-xl animate-pulse"></div>
	<div class="absolute bottom-40 right-32 w-48 h-48 bg-emerald-200/20 rounded-full blur-2xl animate-pulse delay-1000"></div>
	<div class="absolute top-1/2 left-1/3 w-24 h-24 bg-teal-300/20 rounded-full blur-lg animate-pulse delay-500"></div>
	
	<!-- Hero Content -->
	<div class="relative z-10 min-h-screen flex items-center justify-center px-4 sm:px-6 lg:px-8">
		<div class="text-center max-w-6xl mx-auto">
			<!-- Premium Logo/Icon -->
			<div class="mb-16">
				<div class="inline-flex items-center justify-center w-32 h-32 bg-gradient-to-br from-teal-700 to-teal-800 rounded-4xl mb-10 shadow-floating hover:shadow-teal-glow-lg transition-all duration-500 transform hover:scale-105 border border-teal-600/30">
					<svg class="w-16 h-16 text-white drop-shadow-lg" fill="none" stroke="currentColor" viewBox="0 0 24 24">
						<path stroke-linecap="round" stroke-linejoin="round" stroke-width="1.5" d="M9 19v-6a2 2 0 00-2-2H5a2 2 0 00-2-2V7a2 2 0 012-2h2a2 2 0 002 2v2a2 2 0 002 2h2a2 2 0 002-2V7a2 2 0 012-2h2a2 2 0 012 2v2a2 2 0 00-2 2h-2a2 2 0 00-2 2v6a2 2 0 01-2 2H9a2 2 0 01-2-2z" />
					</svg>
				</div>
			</div>

			<!-- Dramatic Main Title -->
			<h1 class="text-7xl md:text-9xl font-display font-black mb-8 tracking-tight leading-none">
				<span class="bg-gradient-to-r from-teal-800 via-teal-700 to-teal-800 bg-clip-text text-transparent drop-shadow-sm">
					ECHO
				</span>
			</h1>
			
			<!-- Subtitle -->
			<p class="text-2xl md:text-3xl text-teal-700 font-light mb-10 max-w-4xl mx-auto leading-relaxed">
				Education, Community, and Housing Open Data Dashboard
			</p>
		</div>
	</div>

	<!-- Elegant Scroll Indicator -->
	<div class="absolute bottom-16 left-1/2 transform -translate-x-1/2 animate-bounce">
		<div class="w-8 h-12 border-2 border-teal-600/60 rounded-full flex justify-center backdrop-blur-sm">
			<div class="w-1.5 h-4 bg-teal-600/80 rounded-full mt-2 animate-pulse"></div>
		</div>
	</div>
</div>

<!-- Main Dashboard Homepage -->
<div class="min-h-screen bg-gradient-to-br from-slate-50/50 via-white to-teal-50/30" id="dashboard-section">

	<!-- Content Sections -->
	<div class="max-w-7xl mx-auto px-4 sm:px-6 lg:px-8 py-16">
		<!-- About Section -->
		<section class="mb-32">
			<div class="text-center mb-16">
				<h2 class="text-5xl font-display font-bold text-slate-900 mb-6">
					<span class="bg-gradient-to-r from-teal-900 via-teal-800 to-teal-900 bg-clip-text text-transparent">
						About the ECHO Dashboard
					</span>
				</h2>
				<div class="w-32 h-1.5 bg-premium-teal mx-auto rounded-full shadow-teal-glow"></div>
			</div>
			
			<div class="max-w-5xl mx-auto">
				<Card variant="premium" padding="xl">
					<div class="text-slate-700 text-xl leading-relaxed space-y-8">
						<p class="text-2xl font-light text-slate-800 leading-relaxed">
							This dashboard includes a wide range of national data related to education, housing, and community 
							demographics and welfare. This data is intended for use by policymakers, advocates, journalists, and anyone 
							who seeks to understand and shape social policy in their states and communities.
						</p>
						<p class="text-lg">
							The data is presented at four geographic levels: school districts, state legislative districts, counties, and census tracts. 
							The data can be viewed in maps or data tables, and can be used to generate several kinds of charts.
						</p>
						<div class="bg-gradient-to-r from-teal-50 to-emerald-50 border-l-4 border-teal-800 p-8 rounded-r-2xl shadow-elegant">
							<div class="flex items-start">
								<div class="flex-shrink-0 mr-4">
									<div class="w-8 h-8 bg-teal-800 rounded-full flex items-center justify-center">
										<svg class="w-4 h-4 text-white" fill="none" stroke="currentColor" viewBox="0 0 24 24">
											<path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M13 16h-1v-4h-1m1-4h.01M21 12a9 9 0 11-18 0 9 9 0 0118 0z" />
										</svg>
									</div>
								</div>
								<p class="font-semibold text-teal-900 text-lg">
									Note: The dashboard is not compatible with mobile at this time. Please use a personal computer.
								</p>
							</div>
						</div>
					</div>
				</Card>
			</div>
		</section>

		<!-- How to Use Section -->
		<section class="mb-32">
			<div class="text-center mb-20">
				<h2 class="text-5xl font-display font-bold text-slate-900 mb-6">
					<span class="bg-gradient-to-r from-teal-900 via-teal-800 to-teal-900 bg-clip-text text-transparent">
						How to Use the ECHO Dashboard
					</span>
				</h2>
				<div class="w-32 h-1.5 bg-premium-teal mx-auto mb-8 rounded-full shadow-teal-glow"></div>
				<p class="text-2xl text-slate-600 max-w-4xl mx-auto font-light leading-relaxed">
					Follow these simple steps to explore and analyze the data
				</p>
			</div>
			
			<!-- Plain English Description of Current Selection -->
			{#if $currentSelectionDescription && ($currentGeoLevel || $selectedIndicatorCount > 0 || $selectedView)}
				<div class="max-w-4xl mx-auto mb-12">
					<div class="bg-gradient-to-r from-teal-50 to-emerald-50 border border-teal-200 rounded-2xl p-8 shadow-lg">
						<div class="flex items-center justify-center mb-4">
							<div class="w-10 h-10 bg-teal-100 rounded-full flex items-center justify-center mr-3">
								<svg class="w-5 h-5 text-teal-600" fill="none" stroke="currentColor" viewBox="0 0 24 24">
									<path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M15 12a3 3 0 11-6 0 3 3 0 016 0z" />
									<path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M2.458 12C3.732 7.943 7.523 5 12 5c4.478 0 8.268 2.943 9.542 7-1.274 4.057-5.064 7-9.542 7-4.477 0-8.268-2.943-9.542-7z" />
								</svg>
							</div>
							<span class="text-lg font-medium text-teal-700">Your Current Selection</span>
						</div>
						<p class="text-2xl font-semibold text-teal-900 text-center">
							{$currentSelectionDescription}
							{#if $selectedView}
								<span class="text-teal-700"> - viewing in {$selectedView === 'chart' ? 'charts' : $selectedView}</span>
							{/if}
						</p>
						{#if $allStepsCompleted}
							<div class="mt-4 text-center">
								<span class="text-sm text-teal-600 font-medium">✓ All steps completed - scroll down to see your data!</span>
							</div>
						{/if}
					</div>
				</div>
			{/if}
			
			<div class="grid grid-cols-1 md:grid-cols-3 gap-16">
				<!-- Step 1: Interactive Geographic Level Selection -->
				<Card variant="floating" padding="lg" hover={true}>
					<div class="text-center">
						<div class="relative mb-10">
							<div class="w-40 h-40 bg-gradient-to-br from-teal-100 via-teal-50 to-emerald-50 rounded-3xl mx-auto mb-8 flex items-center justify-center shadow-luxury group-hover:shadow-floating transition-all duration-500 border border-teal-200/50">
								<svg class="w-20 h-20 text-teal-800" fill="none" stroke="currentColor" viewBox="0 0 24 24">
									<path stroke-linecap="round" stroke-linejoin="round" stroke-width="1.5" d="M9 19v-6a2 2 0 00-2-2H5a2 2 0 00-2-2V7a2 2 0 012-2h2a2 2 0 002 2v2a2 2 0 002 2h2a2 2 0 002-2V7a2 2 0 012-2h2a2 2 0 012 2v2a2 2 0 00-2 2h-2a2 2 0 00-2 2v6a2 2 0 01-2 2H9a2 2 0 01-2-2z" />
								</svg>
							</div>
							<div class="w-16 h-16 bg-premium-teal text-white rounded-2xl flex items-center justify-center mx-auto mb-8 font-bold text-2xl shadow-teal-glow relative">
								1
								{#if $stepCompletion.step1}
									<div class="absolute -top-2 -right-2 w-6 h-6 bg-green-500 rounded-full flex items-center justify-center">
										<svg class="w-4 h-4 text-white" fill="none" stroke="currentColor" viewBox="0 0 24 24">
											<path stroke-linecap="round" stroke-linejoin="round" stroke-width="3" d="M5 13l4 4L19 7" />
										</svg>
									</div>
								{/if}
							</div>
						</div>
						<h3 class="text-3xl font-bold text-slate-900 mb-6">Select Geographic Level</h3>
						<p class="text-slate-600 leading-relaxed text-lg mb-8">
							Choose from school districts, counties, legislative districts, or census tracts
						</p>
						
						<!-- Interactive Geographic Selection -->
						<div class="mt-6">
							<select
								class="w-full text-lg font-medium bg-white border-2 border-teal-200 focus:ring-4 focus:ring-teal-500/20 focus:border-teal-500 rounded-xl px-4 py-3 cursor-pointer hover:border-teal-300 transition-all"
								value={$currentGeoLevel || ''}
								on:change={handleGeoLevelChange}
							>
								<option value="">Select geography...</option>
								{#each Object.keys($geographies) as level}
									<option value={level}>{$geographies[level]?.name || level}</option>
								{/each}
							</select>
						</div>
					</div>
				</Card>

				<!-- Step 2: Variable Selection -->
				<Card variant="floating" padding="lg" hover={true}>
					<div class="text-center">
						<div class="relative mb-10">
							<div class="w-40 h-40 bg-gradient-to-br from-emerald-100 via-emerald-50 to-teal-50 rounded-3xl mx-auto mb-8 flex items-center justify-center shadow-luxury group-hover:shadow-floating transition-all duration-500 border border-emerald-200/50">
								<svg class="w-20 h-20 text-emerald-800" fill="none" stroke="currentColor" viewBox="0 0 24 24">
									<path stroke-linecap="round" stroke-linejoin="round" stroke-width="1.5" d="M9 20l-5.447-2.724A1 1 0 013 16.382V5.618a1 1 0 011.447-.894L9 7m0 13l6-3m-6 3V7m6 10l4.553 2.276A1 1 0 0021 18.382V7.618a1 1 0 00-.553-.894L15 4m0 13V4m0 0L9 7" />
								</svg>
							</div>
							<div class="w-16 h-16 bg-gradient-to-r from-emerald-700 to-emerald-800 text-white rounded-2xl flex items-center justify-center mx-auto mb-8 font-bold text-2xl shadow-elegant relative">
								2
								{#if $stepCompletion.step2}
									<div class="absolute -top-2 -right-2 w-6 h-6 bg-green-500 rounded-full flex items-center justify-center">
										<svg class="w-4 h-4 text-white" fill="none" stroke="currentColor" viewBox="0 0 24 24">
											<path stroke-linecap="round" stroke-linejoin="round" stroke-width="3" d="M5 13l4 4L19 7" />
										</svg>
									</div>
								{/if}
							</div>
						</div>
						<h3 class="text-3xl font-bold text-slate-900 mb-6">Select Variables</h3>
						<p class="text-slate-600 leading-relaxed text-lg mb-8">
							Choose the data variables you want to explore and analyze
						</p>
						
						<!-- Variable Selection Button -->
						<div class="mt-6">
							<button
								class="w-full text-lg font-medium bg-gradient-to-r from-emerald-600 to-emerald-700 text-white rounded-xl px-6 py-3 hover:from-emerald-700 hover:to-emerald-800 transition-all duration-200 shadow-lg hover:shadow-xl flex items-center justify-center"
								on:click={() => $showVariableSelector = true}
							>
								<svg class="w-5 h-5 mr-2" fill="none" stroke="currentColor" viewBox="0 0 24 24">
									<path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M9 5H7a2 2 0 00-2 2v12a2 2 0 002 2h10a2 2 0 002-2V7a2 2 0 00-2-2h-2M9 5a2 2 0 002 2h2a2 2 0 002-2M9 5a2 2 0 012-2h2a2 2 0 012 2" />
								</svg>
								{getVariableDisplayText()}
							</button>
							{#if $selectedIndicatorCount > 0}
								<p class="mt-2 text-sm text-emerald-600 font-medium">
									{$selectedIndicatorCount} variable{$selectedIndicatorCount === 1 ? '' : 's'} selected
								</p>
							{/if}
						</div>
					</div>
				</Card>

				<!-- Step 3: View Selection -->
				<Card variant="floating" padding="lg" hover={true}>
					<div class="text-center">
						<div class="relative mb-10">
							<div class="w-40 h-40 bg-gradient-to-br from-slate-100 via-slate-50 to-teal-50 rounded-3xl mx-auto mb-8 flex items-center justify-center shadow-luxury group-hover:shadow-floating transition-all duration-500 border border-slate-200/50">
								<svg class="w-20 h-20 text-slate-800" fill="none" stroke="currentColor" viewBox="0 0 24 24">
									<path stroke-linecap="round" stroke-linejoin="round" stroke-width="1.5" d="M9 19v-6a2 2 0 00-2-2H5a2 2 0 00-2-2V7a2 2 0 012-2h2a2 2 0 002 2v2a2 2 0 002 2h2a2 2 0 002-2V7a2 2 0 012-2h2a2 2 0 012 2v2a2 2 0 00-2 2h-2a2 2 0 00-2 2v6a2 2 0 01-2 2H9a2 2 0 01-2-2z" />
								</svg>
							</div>
							<div class="w-16 h-16 bg-gradient-to-r from-slate-700 to-slate-800 text-white rounded-2xl flex items-center justify-center mx-auto mb-8 font-bold text-2xl shadow-elegant relative">
								3
								{#if $stepCompletion.step3}
									<div class="absolute -top-2 -right-2 w-6 h-6 bg-green-500 rounded-full flex items-center justify-center">
										<svg class="w-4 h-4 text-white" fill="none" stroke="currentColor" viewBox="0 0 24 24">
											<path stroke-linecap="round" stroke-linejoin="round" stroke-width="3" d="M5 13l4 4L19 7" />
										</svg>
									</div>
								{/if}
							</div>
						</div>
						<h3 class="text-3xl font-bold text-slate-900 mb-6">Select View</h3>
						<p class="text-slate-600 leading-relaxed text-lg mb-8">
							Choose how you want to visualize and analyze your data
						</p>
						
						<!-- View Selection Buttons -->
						<div class="mt-6 space-y-3">
							<button
								class="w-full text-left p-4 rounded-xl border-2 transition-all duration-200 {$selectedView === 'map' ? 'border-teal-500 bg-teal-50' : 'border-slate-200 hover:border-slate-300'}"
								on:click={() => selectView('map')}
							>
								<div class="flex items-center">
									<span class="text-2xl mr-3">🗺️</span>
									<div>
										<div class="font-semibold text-slate-900">Map View</div>
										<div class="text-sm text-slate-600">Interactive choropleth maps</div>
									</div>
									{#if $selectedView === 'map'}
										<svg class="w-5 h-5 text-teal-600 ml-auto" fill="currentColor" viewBox="0 0 20 20">
											<path fill-rule="evenodd" d="M16.707 5.293a1 1 0 010 1.414l-8 8a1 1 0 01-1.414 0l-4-4a1 1 0 011.414-1.414L8 12.586l7.293-7.293a1 1 0 011.414 0z" clip-rule="evenodd" />
										</svg>
									{/if}
								</div>
							</button>
							
							<button
								class="w-full text-left p-4 rounded-xl border-2 transition-all duration-200 {$selectedView === 'table' ? 'border-teal-500 bg-teal-50' : 'border-slate-200 hover:border-slate-300'}"
								on:click={() => selectView('table')}
							>
								<div class="flex items-center">
									<span class="text-2xl mr-3">📊</span>
									<div>
										<div class="font-semibold text-slate-900">Table View</div>
										<div class="text-sm text-slate-600">Comprehensive data tables</div>
									</div>
									{#if $selectedView === 'table'}
										<svg class="w-5 h-5 text-teal-600 ml-auto" fill="currentColor" viewBox="0 0 20 20">
											<path fill-rule="evenodd" d="M16.707 5.293a1 1 0 010 1.414l-8 8a1 1 0 01-1.414 0l-4-4a1 1 0 011.414-1.414L8 12.586l7.293-7.293a1 1 0 011.414 0z" clip-rule="evenodd" />
										</svg>
									{/if}
								</div>
							</button>
							
							<button
								class="w-full text-left p-4 rounded-xl border-2 transition-all duration-200 {$selectedView === 'chart' ? 'border-teal-500 bg-teal-50' : 'border-slate-200 hover:border-slate-300'}"
								on:click={() => selectView('chart')}
							>
								<div class="flex items-center">
									<span class="text-2xl mr-3">📈</span>
									<div>
										<div class="font-semibold text-slate-900">Chart View</div>
										<div class="text-sm text-slate-600">Data visualizations</div>
									</div>
									{#if $selectedView === 'chart'}
										<svg class="w-5 h-5 text-teal-600 ml-auto" fill="currentColor" viewBox="0 0 20 20">
											<path fill-rule="evenodd" d="M16.707 5.293a1 1 0 010 1.414l-8 8a1 1 0 01-1.414 0l-4-4a1 1 0 011.414-1.414L8 12.586l7.293-7.293a1 1 0 011.414 0z" clip-rule="evenodd" />
										</svg>
									{/if}
								</div>
							</button>
						</div>
					</div>
				</Card>
			</div>
		</section>

		<!-- Premium Get Started Button -->
		<div class="text-center">
			<Button 
				variant="primary" 
				size="lg"
				on:click={() => {
					const interfaceSection = document.getElementById('interface-section');
					if (interfaceSection) {
						interfaceSection.scrollIntoView({ behavior: 'smooth' });
					}
				}}
			>
				<span class="mr-4">Start Exploring Data</span>
				<svg class="w-6 h-6" fill="none" stroke="currentColor" viewBox="0 0 24 24">
					<path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M13 7l5 5m0 0l-5 5m5-5H6" />
				</svg>
			</Button>
		</div>
	</div>
</div>

<!-- Interactive Dashboard Interface -->
<div class="min-h-screen bg-gradient-to-br from-slate-50 via-white to-slate-100" id="interface-section">
	<!-- Unified Context Bar -->
	<UnifiedContextBar />

	<!-- Streamlined Interface Demo Section -->
	<div class="max-w-7xl mx-auto px-4 sm:px-6 lg:px-8 py-24 border-b border-slate-200">
		<div class="text-center mb-16">
			<h2 class="text-4xl font-display font-bold text-slate-900 mb-4">
				Streamlined Data Interface
			</h2>
			<p class="text-xl text-slate-600 max-w-2xl mx-auto">
				One unified context bar controls all data selections across maps, tables, and charts
			</p>
			
			<!-- Current Selection Description -->
			{#if $currentSelectionDescription && ($currentGeoLevel || $currentPrimaryIndicator || $selectedIndicatorCount > 0)}
				<div class="mt-8 max-w-3xl mx-auto">
					<div class="bg-gradient-to-r from-teal-50 to-teal-100 border border-teal-200 rounded-xl p-6">
						<div class="flex items-center justify-center mb-3">
							<div class="w-8 h-8 bg-teal-100 rounded-full flex items-center justify-center mr-3">
								<svg class="w-4 h-4 text-teal-600" fill="none" stroke="currentColor" viewBox="0 0 24 24">
									<path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M15 12a3 3 0 11-6 0 3 3 0 016 0z" />
									<path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M2.458 12C3.732 7.943 7.523 5 12 5c4.478 0 8.268 2.943 9.542 7-1.274 4.057-5.064 7-9.542 7-4.477 0-8.268-2.943-9.542-7z" />
								</svg>
							</div>
							<span class="text-sm font-medium text-teal-700">Currently Viewing</span>
						</div>
						<p class="text-2xl font-semibold text-teal-900 text-center">
							{$currentSelectionDescription}
						</p>
					</div>
				</div>
			{/if}
		</div>

		<div class="grid grid-cols-1 xl:grid-cols-3 gap-8">
			<!-- Current State Display -->
			<div class="xl:col-span-2 space-y-6">
				<Card variant="elevated">
					<h3 class="text-xl font-semibold text-slate-900 mb-6">Current Context</h3>
					
					<div class="space-y-4">
						<!-- Current URL -->
						<div>
							<label class="block text-sm font-medium text-slate-700 mb-2">
								Current URL
							</label>
							<div class="bg-slate-50 border border-slate-200 rounded-md p-3">
								<code class="text-xs text-slate-800 break-all">{$currentUrl}</code>
							</div>
						</div>

						<!-- Filter Values -->
						<div>
							<label class="block text-sm font-medium text-slate-700 mb-2">
								Unified Filter State
							</label>
							<div class="bg-slate-50 border border-slate-200 rounded-md p-3">
								<pre class="text-xs text-slate-800">{JSON.stringify($unifiedFilters, null, 2)}</pre>
							</div>
						</div>

						<!-- Validation Status -->
						<div>
							<label class="block text-sm font-medium text-slate-700 mb-2">
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
			<div class="space-y-6">
				<!-- Instructions -->
				<Card variant="outline">
					<div>
						<h4 class="text-lg font-semibold text-slate-900 mb-3">
							🚀 Streamlined Features
						</h4>
						<ul class="text-sm text-slate-600 space-y-2">
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
					<h4 class="text-lg font-semibold text-slate-900 mb-3">Available Data</h4>
					<div class="text-sm text-slate-600 space-y-1">
						<p><strong>Indicators:</strong> {$indicators.length}</p>
						<p><strong>Geography Levels:</strong> {Object.keys($geographies).length}</p>
						<p><strong>Latest Year:</strong> {$latestYear || 'N/A'}</p>
					</div>
				</Card>
			</div>
		</div>
	</div>

	<!-- Interactive Map Visualization Section -->
	<div id="map-section" class="max-w-7xl mx-auto px-4 sm:px-6 lg:px-8 py-24 border-b border-slate-200">
		<div class="text-center mb-16">
			<h2 class="text-4xl font-display font-bold text-slate-900 mb-4">
				Interactive Map Visualization
			</h2>
			<p class="text-xl text-slate-600 max-w-2xl mx-auto">
				Explore data through dynamic choropleth maps that update seamlessly based on your filter selections
			</p>
		</div>

		<!-- Map Container -->
		<div class="bg-white rounded-2xl shadow-xl border border-slate-200 overflow-hidden">
			<div class="h-[600px] w-full">
				<Map />
			</div>
		</div>

	</div>

	<!-- Data Analysis Suite Section -->
	<div id="analysis-section" class="max-w-7xl mx-auto px-4 sm:px-6 lg:px-8 py-24 border-b border-slate-200">
		<div class="text-center mb-16">
			<h2 class="text-4xl font-display font-bold text-slate-900 mb-4">
				Intelligent Data Analysis Suite
			</h2>
			<p class="text-xl text-slate-600 max-w-2xl mx-auto">
				Seamlessly switch between comprehensive data tables and insightful visualizations with our tabbed analysis interface
			</p>
		</div>

		<!-- Analysis Pane Container -->
		<div class="bg-white rounded-2xl shadow-xl border border-slate-200 overflow-hidden">
			<AnalysisPane />
		</div>

	</div>

	<!-- Footer -->
	<footer class="bg-slate-900 text-white py-16">
		<div class="max-w-7xl mx-auto px-4 sm:px-6 lg:px-8 text-center">
			<div class="mb-8">
				<div class="inline-flex items-center justify-center w-16 h-16 bg-gradient-to-r from-teal-600 to-teal-700 rounded-2xl mb-6">
					<svg class="w-8 h-8 text-white" fill="none" stroke="currentColor" viewBox="0 0 24 24">
						<path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M9 19v-6a2 2 0 00-2-2H5a2 2 0 00-2-2V7a2 2 0 012-2h2a2 2 0 002 2v2a2 2 0 002 2h2a2 2 0 002-2V7a2 2 0 012-2h2a2 2 0 012 2v2a2 2 0 00-2 2h-2a2 2 0 00-2 2v6a2 2 0 01-2 2H9a2 2 0 01-2-2z" />
					</svg>
				</div>
			</div>
			<p class="text-slate-400 mb-6 text-lg">
				Built with ❤️ using SvelteKit, TypeScript, and Tailwind CSS
			</p>
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
		background: #0f766e;
		border-radius: 4px;
	}

	::-webkit-scrollbar-thumb:hover {
		background: #0d9488;
	}
</style>
