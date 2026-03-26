<script lang="ts">
	import Button from './Button.svelte';

	export let variant: 'default' | 'search' | 'data' | 'selection' | 'error' | 'custom' = 'default';
	export let title: string = '';
	export let description: string = '';
	export let icon: string = '';
	export let actionText: string = '';
	export let actionVariant: 'primary' | 'secondary' | 'outline' = 'primary';
	export let showAction: boolean = true;
	export let className: string = '';

	// Predefined variants with icons and content
	const variants = {
		default: {
			icon: '📊',
			title: 'No Data Available',
			description: 'There is no data to display at the moment.',
			actionText: 'Refresh'
		},
		search: {
			icon: '🔍',
			title: 'No Results Found',
			description: 'Try adjusting your search terms or filters.',
			actionText: 'Clear Search'
		},
		data: {
			icon: '📈',
			title: 'No Data to Display',
			description: 'Select indicators and configure your filters to view data.',
			actionText: 'Select Data'
		},
		selection: {
			icon: '',
			title: 'Make Your Selection',
			description: 'Choose your preferences to get started with the analysis.',
			actionText: 'Get Started'
		},
		error: {
			icon: '⚠️',
			title: 'Something Went Wrong',
			description: 'We encountered an error while loading the data.',
			actionText: 'Try Again'
		},
		custom: {
			icon: '',
			title: '',
			description: '',
			actionText: ''
		}
	};

	$: currentVariant = variants[variant];
	$: displayTitle = title || currentVariant.title;
	$: displayDescription = description || currentVariant.description;
	$: displayIcon = icon || currentVariant.icon;
	$: displayActionText = actionText || currentVariant.actionText;
</script>

<div class="text-center py-16 px-8 {className}">
	<!-- Icon/Illustration -->
	<div class="mb-8">
		{#if displayIcon.startsWith('http') || displayIcon.startsWith('/') || displayIcon.includes('.')}
			<!-- Image URL -->
			<img src={displayIcon} alt="" class="w-24 h-24 mx-auto opacity-60" />
		{:else if displayIcon}
			<!-- Emoji or text icon -->
			<div class="text-6xl mb-4 opacity-60">
				{displayIcon}
			</div>
		{:else}
			<!-- Default SVG icon based on variant -->
			{#if variant === 'selection'}
				<div class="w-20 h-20 bg-teal-700 rounded-3xl mx-auto mb-8 flex items-center justify-center shadow-elegant">
					<svg class="w-10 h-10 text-white" fill="none" stroke="currentColor" viewBox="0 0 24 24">
						<path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M12 6V4m0 2a2 2 0 100 4m0-4a2 2 0 110 4m-6 8a2 2 0 100-4m0 4a2 2 0 100 4m0-4v2m0-6V4m6 6v10m6-2a2 2 0 100-4m0 4a2 2 0 100 4m0-4v2m0-6V4"/>
					</svg>
				</div>
			{:else}
				<div class="w-24 h-24 mx-auto mb-4 bg-gradient-to-br from-neutral-100 to-neutral-200 rounded-full flex items-center justify-center">
					{#if variant === 'search'}
						<svg class="w-12 h-12 text-neutral-400" fill="none" stroke="currentColor" viewBox="0 0 24 24">
							<path stroke-linecap="round" stroke-linejoin="round" stroke-width="1.5" d="M21 21l-6-6m2-5a7 7 0 11-14 0 7 7 0 0114 0z" />
						</svg>
					{:else if variant === 'data'}
						<svg class="w-12 h-12 text-neutral-400" fill="none" stroke="currentColor" viewBox="0 0 24 24">
							<path stroke-linecap="round" stroke-linejoin="round" stroke-width="1.5" d="M9 19v-6a2 2 0 00-2-2H5a2 2 0 00-2-2V7a2 2 0 012-2h2a2 2 0 002 2v2a2 2 0 002 2h2a2 2 0 002-2V7a2 2 0 012-2h2a2 2 0 012 2v2a2 2 0 00-2 2h-2a2 2 0 00-2 2v6a2 2 0 01-2 2H9a2 2 0 01-2-2z" />
						</svg>
					{:else if variant === 'error'}
						<svg class="w-12 h-12 text-red-400" fill="none" stroke="currentColor" viewBox="0 0 24 24">
							<path stroke-linecap="round" stroke-linejoin="round" stroke-width="1.5" d="M12 9v2m0 4h.01m-6.938 4h13.856c1.54 0 2.502-1.667 1.732-2.5L13.732 4c-.77-.833-1.964-.833-2.732 0L3.34 16.5c-.77.833.192 2.5 1.732 2.5z" />
						</svg>
					{:else}
						<svg class="w-12 h-12 text-neutral-400" fill="none" stroke="currentColor" viewBox="0 0 24 24">
							<path stroke-linecap="round" stroke-linejoin="round" stroke-width="1.5" d="M20 13V6a2 2 0 00-2-2H6a2 2 0 00-2 2v7m16 0v5a2 2 0 01-2 2H6a2 2 0 01-2-2v-5m16 0h-2.586a1 1 0 00-.707.293l-2.414 2.414a1 1 0 01-.707.293h-3.172a1 1 0 01-.707-.293l-2.414-2.414A1 1 0 006.586 13H4" />
						</svg>
					{/if}
				</div>
			{/if}
		{/if}
	</div>

	<!-- Content -->
	<div class="max-w-md mx-auto">
		{#if displayTitle}
			<h3 class="text-xl font-semibold text-neutral-900 mb-3">
				{displayTitle}
			</h3>
		{/if}
		
		{#if displayDescription}
			<p class="text-neutral-600 mb-8 leading-relaxed">
				{displayDescription}
			</p>
		{/if}

		<!-- Custom content slot -->
		<slot name="content" />
	</div>

	<!-- Action Button -->
	{#if showAction && displayActionText}
		<div class="mt-8">
			<Button 
				variant={actionVariant} 
				on:click
				class="inline-flex items-center"
			>
				{#if variant === 'search'}
					<svg class="w-4 h-4 mr-2" fill="none" stroke="currentColor" viewBox="0 0 24 24">
						<path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M6 18L18 6M6 6l12 12" />
					</svg>
				{:else if variant === 'error'}
					<svg class="w-4 h-4 mr-2" fill="none" stroke="currentColor" viewBox="0 0 24 24">
						<path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M4 4v5h.582m15.356 2A8.001 8.001 0 004.582 9m0 0H9m11 11v-5h-.581m0 0a8.003 8.003 0 01-15.357-2m15.357 2H15" />
					</svg>
				{:else if variant === 'data' || variant === 'selection'}
					<svg class="w-4 h-4 mr-2" fill="none" stroke="currentColor" viewBox="0 0 24 24">
						<path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M12 6v6m0 0v6m0-6h6m-6 0H6" />
					</svg>
				{:else}
					<svg class="w-4 h-4 mr-2" fill="none" stroke="currentColor" viewBox="0 0 24 24">
						<path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M4 4v5h.582m15.356 2A8.001 8.001 0 004.582 9m0 0H9m11 11v-5h-.581m0 0a8.003 8.003 0 01-15.357-2m15.357 2H15" />
					</svg>
				{/if}
				{displayActionText}
			</Button>
		</div>
	{/if}

	<!-- Custom action slot -->
	<slot name="action" />

	<!-- Additional content slot -->
	<slot />
</div>
