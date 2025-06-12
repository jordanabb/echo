<script lang="ts">
	import { Button, Card, FilterPanel, Map } from '$lib/components';
	import { 
		theme, 
		isLoading,
		// Metadata stores
		metadata,
		metadataLoading,
		metadataError,
		indicators,
		geographies,
		indicatorsByTheme,
		latestYear,
		// Filter stores
		filters,
		currentIndicator,
		currentGeoLevel,
		currentYear,
		currentUrl,
		areFiltersValid,
		updateFilter,
		updateFilters,
		resetFilters
	} from '$lib/stores';
	import { formatDate } from '$lib/utils';

	let loading = false;

	function handleGetStarted() {
		loading = true;
		setTimeout(() => {
			loading = false;
			alert('Welcome to Echo! 🎉');
		}, 2000);
	}

	function toggleTheme() {
		theme.update(t => t === 'light' ? 'dark' : 'light');
	}


	const currentDate = formatDate(new Date());
</script>

<svelte:head>
	<title>Echo - Premium Frontend Experience</title>
	<meta name="description" content="A modern SvelteKit application with premium styling and components" />
</svelte:head>

<div class="min-h-screen bg-gradient-to-br from-primary-50 via-white to-secondary-50">
	<!-- Smart Interactive Filter Panel Demo Section -->
	<div class="max-w-7xl mx-auto px-4 sm:px-6 lg:px-8 py-24 border-b border-neutral-200">
		<div class="text-center mb-16">
			<h2 class="text-4xl font-display font-bold text-neutral-900 mb-4">
				Smart Interactive Filter Panel
			</h2>
			<p class="text-xl text-neutral-600 max-w-2xl mx-auto">
				Experience intelligent cascading filters with real-time validation and URL-based state management
			</p>
		</div>

		<div class="grid grid-cols-1 xl:grid-cols-3 gap-8">
			<!-- Filter Panel -->
			<div class="xl:col-span-2">
				<FilterPanel />
			</div>

			<!-- Current State Display -->
			<div class="space-y-6">
				<Card variant="elevated">
					<h3 class="text-xl font-semibold text-neutral-900 mb-6">Current State</h3>
					
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
								Filter State
							</label>
							<div class="bg-neutral-50 border border-neutral-200 rounded-md p-3">
								<pre class="text-xs text-neutral-800">{JSON.stringify($filters, null, 2)}</pre>
							</div>
						</div>

						<!-- Validation Status -->
						<div>
							<label class="block text-sm font-medium text-neutral-700 mb-2">
								Validation Status
							</label>
							<div class="flex items-center space-x-2">
								{#if $areFiltersValid}
									<div class="w-3 h-3 bg-success-500 rounded-full"></div>
									<span class="text-sm text-success-700">Valid - Ready to fetch data</span>
								{:else}
									<div class="w-3 h-3 bg-warning-500 rounded-full"></div>
									<span class="text-sm text-warning-700">Invalid - Missing or incompatible filters</span>
								{/if}
							</div>
						</div>

						<!-- Metadata Info -->
						<div>
							<label class="block text-sm font-medium text-neutral-700 mb-2">
								Available Data
							</label>
							<div class="text-sm text-neutral-600 space-y-1">
								<p><strong>Indicators:</strong> {$indicators.length}</p>
								<p><strong>Geography Levels:</strong> {Object.keys($geographies).length}</p>
								<p><strong>Latest Year:</strong> {$latestYear || 'N/A'}</p>
							</div>
						</div>
					</div>
				</Card>

				<!-- Instructions -->
				<Card variant="outline">
					<div>
						<h4 class="text-lg font-semibold text-neutral-900 mb-3">
							🧠 Smart Features
						</h4>
						<ul class="text-sm text-neutral-600 space-y-2">
							<li class="flex items-start">
								<span class="text-primary-600 mr-2">•</span>
								<span><strong>Cascading Logic:</strong> Year options update based on selected indicator</span>
							</li>
							<li class="flex items-start">
								<span class="text-primary-600 mr-2">•</span>
								<span><strong>Smart Validation:</strong> Real-time feedback on filter compatibility</span>
							</li>
							<li class="flex items-start">
								<span class="text-primary-600 mr-2">•</span>
								<span><strong>Location Guidance:</strong> State/county selection for census tracts</span>
							</li>
							<li class="flex items-start">
								<span class="text-primary-600 mr-2">•</span>
								<span><strong>URL Sync:</strong> Every filter change updates the shareable URL</span>
							</li>
							<li class="flex items-start">
								<span class="text-primary-600 mr-2">•</span>
								<span><strong>Advanced View:</strong> Toggle to see detailed validation status</span>
							</li>
						</ul>
					</div>
				</Card>
			</div>
		</div>
	</div>

	<!-- Interactive Map Visualization Section -->
	<div class="max-w-7xl mx-auto px-4 sm:px-6 lg:px-8 py-24 border-b border-neutral-200">
		<div class="text-center mb-16">
			<h2 class="text-4xl font-display font-bold text-neutral-900 mb-4">
				Interactive Map Visualization
			</h2>
			<p class="text-xl text-neutral-600 max-w-2xl mx-auto">
				Explore data through dynamic choropleth maps that update seamlessly based on your filter selections
			</p>
		</div>

		<!-- Map Container -->
		<div class="bg-white rounded-2xl shadow-xl border border-neutral-200 overflow-hidden">
			<div class="h-[600px] w-full">
				<Map />
			</div>
		</div>

		<!-- Map Features -->
		<div class="mt-12 grid grid-cols-1 md:grid-cols-2 lg:grid-cols-4 gap-6">
			<Card variant="outline">
				<div class="text-center p-4">
					<div class="w-10 h-10 bg-blue-100 rounded-lg flex items-center justify-center mx-auto mb-3">
						<svg class="w-5 h-5 text-blue-600" fill="none" stroke="currentColor" viewBox="0 0 24 24">
							<path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M9 20l-5.447-2.724A1 1 0 013 16.382V5.618a1 1 0 011.447-.894L9 7m0 13l6-3m-6 3V7m6 10l4.553 2.276A1 1 0 0021 18.382V7.618a1 1 0 00-1.447-.894L15 4m0 13V4m0 0L9 7" />
						</svg>
					</div>
					<h4 class="font-semibold text-neutral-900 mb-1">Reactive Updates</h4>
					<p class="text-sm text-neutral-600">Map automatically updates when filters change</p>
				</div>
			</Card>

			<Card variant="outline">
				<div class="text-center p-4">
					<div class="w-10 h-10 bg-green-100 rounded-lg flex items-center justify-center mx-auto mb-3">
						<svg class="w-5 h-5 text-green-600" fill="none" stroke="currentColor" viewBox="0 0 24 24">
							<path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M7 21a4 4 0 01-4-4V5a2 2 0 012-2h4a2 2 0 012 2v12a4 4 0 01-4 4zM21 5a2 2 0 00-2-2h-4a2 2 0 00-2 2v12a4 4 0 004 4h4a2 2 0 002-2V5z" />
						</svg>
					</div>
					<h4 class="font-semibold text-neutral-900 mb-1">Dynamic Legend</h4>
					<p class="text-sm text-neutral-600">Legend adapts to data ranges and classifications</p>
				</div>
			</Card>

			<Card variant="outline">
				<div class="text-center p-4">
					<div class="w-10 h-10 bg-purple-100 rounded-lg flex items-center justify-center mx-auto mb-3">
						<svg class="w-5 h-5 text-purple-600" fill="none" stroke="currentColor" viewBox="0 0 24 24">
							<path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M15 15l-2 5L9 9l11 4-5 2zm0 0l5 5M7.188 2.239l.777 2.897M5.136 7.965l-2.898-.777M13.95 4.05l-2.122 2.122m-5.657 5.656l-2.12 2.122" />
						</svg>
					</div>
					<h4 class="font-semibold text-neutral-900 mb-1">Interactive Features</h4>
					<p class="text-sm text-neutral-600">Click and hover for detailed information</p>
				</div>
			</Card>

			<Card variant="outline">
				<div class="text-center p-4">
					<div class="w-10 h-10 bg-orange-100 rounded-lg flex items-center justify-center mx-auto mb-3">
						<svg class="w-5 h-5 text-orange-600" fill="none" stroke="currentColor" viewBox="0 0 24 24">
							<path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M13 7h8m0 0v8m0-8l-8 8-4-4-6 6" />
						</svg>
					</div>
					<h4 class="font-semibold text-neutral-900 mb-1">Smooth Transitions</h4>
					<p class="text-sm text-neutral-600">Elegant animations between data updates</p>
				</div>
			</Card>
		</div>
	</div>

	<!-- Features Section -->
	<div class="max-w-7xl mx-auto px-4 sm:px-6 lg:px-8 py-24">
		<div class="text-center mb-16">
			<h2 class="text-4xl font-display font-bold text-neutral-900 mb-4">
				Premium Features
			</h2>
			<p class="text-xl text-neutral-600 max-w-2xl mx-auto">
				Everything you need to build modern, performant web applications
			</p>
		</div>

		<div class="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-3 gap-8">
			<!-- Feature 1 -->
			<Card variant="elevated" hover>
				<div class="text-center">
					<div class="w-12 h-12 bg-primary-100 rounded-xl flex items-center justify-center mx-auto mb-4">
						<svg class="w-6 h-6 text-primary-600" fill="none" stroke="currentColor" viewBox="0 0 24 24">
							<path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M13 10V3L4 14h7v7l9-11h-7z" />
						</svg>
					</div>
					<h3 class="text-xl font-semibold text-neutral-900 mb-2">Lightning Fast</h3>
					<p class="text-neutral-600">Built with SvelteKit for optimal performance and developer experience</p>
				</div>
			</Card>

			<!-- Feature 2 -->
			<Card variant="elevated" hover>
				<div class="text-center">
					<div class="w-12 h-12 bg-secondary-100 rounded-xl flex items-center justify-center mx-auto mb-4">
						<svg class="w-6 h-6 text-secondary-600" fill="none" stroke="currentColor" viewBox="0 0 24 24">
							<path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M7 21a4 4 0 01-4-4V5a2 2 0 012-2h4a2 2 0 012 2v12a4 4 0 01-4 4zM21 5a2 2 0 00-2-2h-4a2 2 0 00-2 2v12a4 4 0 004 4h4a2 2 0 002-2V5z" />
						</svg>
					</div>
					<h3 class="text-xl font-semibold text-neutral-900 mb-2">Type Safe</h3>
					<p class="text-neutral-600">Full TypeScript support with comprehensive type checking</p>
				</div>
			</Card>

			<!-- Feature 3 -->
			<Card variant="elevated" hover>
				<div class="text-center">
					<div class="w-12 h-12 bg-accent-100 rounded-xl flex items-center justify-center mx-auto mb-4">
						<svg class="w-6 h-6 text-accent-600" fill="none" stroke="currentColor" viewBox="0 0 24 24">
							<path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M4.318 6.318a4.5 4.5 0 000 6.364L12 20.364l7.682-7.682a4.5 4.5 0 00-6.364-6.364L12 7.636l-1.318-1.318a4.5 4.5 0 00-6.364 0z" />
						</svg>
					</div>
					<h3 class="text-xl font-semibold text-neutral-900 mb-2">Beautiful Design</h3>
					<p class="text-neutral-600">Premium Tailwind CSS configuration with custom design system</p>
				</div>
			</Card>

			<!-- Feature 4 -->
			<Card variant="elevated" hover>
				<div class="text-center">
					<div class="w-12 h-12 bg-success-100 rounded-xl flex items-center justify-center mx-auto mb-4">
						<svg class="w-6 h-6 text-success-600" fill="none" stroke="currentColor" viewBox="0 0 24 24">
							<path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M9 12l2 2 4-4m6 2a9 9 0 11-18 0 9 9 0 0118 0z" />
						</svg>
					</div>
					<h3 class="text-xl font-semibold text-neutral-900 mb-2">Fully Tested</h3>
					<p class="text-neutral-600">Comprehensive testing setup with Vitest and Playwright</p>
				</div>
			</Card>

			<!-- Feature 5 -->
			<Card variant="elevated" hover>
				<div class="text-center">
					<div class="w-12 h-12 bg-warning-100 rounded-xl flex items-center justify-center mx-auto mb-4">
						<svg class="w-6 h-6 text-warning-600" fill="none" stroke="currentColor" viewBox="0 0 24 24">
							<path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M10.325 4.317c.426-1.756 2.924-1.756 3.35 0a1.724 1.724 0 002.573 1.066c1.543-.94 3.31.826 2.37 2.37a1.724 1.724 0 001.065 2.572c1.756.426 1.756 2.924 0 3.35a1.724 1.724 0 00-1.066 2.573c.94 1.543-.826 3.31-2.37 2.37a1.724 1.724 0 00-2.572 1.065c-.426 1.756-2.924 1.756-3.35 0a1.724 1.724 0 00-2.573-1.066c-1.543.94-3.31-.826-2.37-2.37a1.724 1.724 0 00-1.065-2.572c-1.756-.426-1.756-2.924 0-3.35a1.724 1.724 0 001.066-2.573c-.94-1.543.826-3.31 2.37-2.37.996.608 2.296.07 2.572-1.065z" />
							<path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M15 12a3 3 0 11-6 0 3 3 0 016 0z" />
						</svg>
					</div>
					<h3 class="text-xl font-semibold text-neutral-900 mb-2">Developer Tools</h3>
					<p class="text-neutral-600">ESLint, Prettier, and modern development tooling included</p>
				</div>
			</Card>

			<!-- Feature 6 -->
			<Card variant="elevated" hover>
				<div class="text-center">
					<div class="w-12 h-12 bg-error-100 rounded-xl flex items-center justify-center mx-auto mb-4">
						<svg class="w-6 h-6 text-error-600" fill="none" stroke="currentColor" viewBox="0 0 24 24">
							<path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M4.318 6.318a4.5 4.5 0 000 6.364L12 20.364l7.682-7.682a4.5 4.5 0 00-6.364-6.364L12 7.636l-1.318-1.318a4.5 4.5 0 00-6.364 0z" />
						</svg>
					</div>
					<h3 class="text-xl font-semibold text-neutral-900 mb-2">Production Ready</h3>
					<p class="text-neutral-600">Optimized build process and deployment-ready configuration</p>
				</div>
			</Card>
		</div>
	</div>

	<!-- Footer -->
	<footer class="bg-neutral-900 text-white py-12">
		<div class="max-w-7xl mx-auto px-4 sm:px-6 lg:px-8 text-center">
			<div class="mb-4">
				<div class="inline-flex items-center justify-center w-12 h-12 bg-gradient-to-r from-primary-600 to-secondary-600 rounded-xl mb-4">
					<svg class="w-6 h-6 text-white" fill="none" stroke="currentColor" viewBox="0 0 24 24">
						<path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M13 10V3L4 14h7v7l9-11h-7z" />
					</svg>
				</div>
			</div>
			<p class="text-neutral-400 mb-4">
				Built with ❤️ using SvelteKit, TypeScript, and Tailwind CSS
			</p>
			<div class="flex justify-center space-x-4">
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
			linear-gradient(rgba(0, 0, 0, 0.1) 1px, transparent 1px),
			linear-gradient(90deg, rgba(0, 0, 0, 0.1) 1px, transparent 1px);
		background-size: 20px 20px;
	}
</style>
