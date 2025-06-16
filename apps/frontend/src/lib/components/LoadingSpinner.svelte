<script lang="ts">
	export let variant: 'default' | 'dots' | 'pulse' | 'bars' | 'ring' = 'default';
	export let size: 'sm' | 'md' | 'lg' | 'xl' = 'md';
	export let color: 'primary' | 'teal' | 'white' | 'slate' = 'primary';
	export let text: string = '';
	export let overlay: boolean = false;
	export let className: string = '';

	const sizeClasses = {
		sm: 'w-4 h-4',
		md: 'w-8 h-8',
		lg: 'w-12 h-12',
		xl: 'w-16 h-16'
	};

	const colorClasses = {
		primary: 'text-teal-600 border-teal-600',
		teal: 'text-teal-500 border-teal-500',
		white: 'text-white border-white',
		slate: 'text-slate-600 border-slate-600'
	};

	const textSizeClasses = {
		sm: 'text-xs',
		md: 'text-sm',
		lg: 'text-base',
		xl: 'text-lg'
	};

	$: spinnerSize = sizeClasses[size];
	$: spinnerColor = colorClasses[color];
	$: textSize = textSizeClasses[size];
</script>

{#if overlay}
	<div class="fixed inset-0 bg-black bg-opacity-50 flex items-center justify-center z-50 backdrop-blur-sm">
		<div class="bg-white rounded-2xl p-8 shadow-floating max-w-sm mx-4">
			<div class="text-center">
				<div class="mb-4">
					<svelte:self {variant} {size} {color} />
				</div>
				{#if text}
					<p class="text-slate-700 font-medium {textSize}">{text}</p>
				{/if}
			</div>
		</div>
	</div>
{:else}
	<div class="flex items-center justify-center {className}">
		{#if variant === 'default'}
			<div class="{spinnerSize} border-4 border-slate-200 border-t-current rounded-full animate-spin {spinnerColor}"></div>
		
		{:else if variant === 'dots'}
			<div class="flex space-x-1">
				{#each Array(3) as _, i}
					<div 
						class="w-2 h-2 rounded-full animate-bounce {spinnerColor.split(' ')[0]} bg-current"
						style="animation-delay: {i * 0.1}s; animation-duration: 0.6s;"
					></div>
				{/each}
			</div>
		
		{:else if variant === 'pulse'}
			<div class="{spinnerSize} rounded-full animate-ping {spinnerColor.split(' ')[0]} bg-current opacity-75"></div>
		
		{:else if variant === 'bars'}
			<div class="flex space-x-1 items-end">
				{#each Array(4) as _, i}
					<div 
						class="w-1 bg-current rounded-full animate-pulse {spinnerColor.split(' ')[0]}"
						style="height: {12 + (i % 2) * 8}px; animation-delay: {i * 0.1}s; animation-duration: 1s;"
					></div>
				{/each}
			</div>
		
		{:else if variant === 'ring'}
			<div class="relative {spinnerSize}">
				<div class="absolute inset-0 border-4 border-slate-200 rounded-full"></div>
				<div class="absolute inset-0 border-4 border-transparent border-t-current rounded-full animate-spin {spinnerColor}"></div>
				<div class="absolute inset-2 border-2 border-transparent border-t-current rounded-full animate-spin {spinnerColor}" style="animation-direction: reverse; animation-duration: 0.75s;"></div>
			</div>
		{/if}
		
		{#if text && !overlay}
			<span class="ml-3 font-medium {spinnerColor.split(' ')[0]} {textSize}">{text}</span>
		{/if}
	</div>
{/if}
