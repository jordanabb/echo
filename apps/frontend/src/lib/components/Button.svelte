<script lang="ts">
	export let variant: 'primary' | 'secondary' | 'accent' | 'outline' | 'ghost' = 'primary';
	export let size: 'xs' | 'sm' | 'md' | 'lg' = 'md';
	export let disabled = false;
	export let loading = false;
	export let href: string | undefined = undefined;
	export let type: 'button' | 'submit' | 'reset' = 'button';

	const baseClasses = 'inline-flex items-center justify-center font-semibold transition-all duration-300 focus:outline-none focus:ring-2 focus:ring-offset-2 disabled:opacity-50 disabled:cursor-not-allowed transform hover:scale-[1.02] active:scale-[0.98]';

	const variantClasses = {
		primary: 'bg-premium-teal text-white hover:shadow-teal-glow focus:ring-teal-500 shadow-luxury hover:shadow-floating border border-teal-800/20',
		secondary: 'bg-gradient-to-r from-secondary-600 to-secondary-700 text-white hover:from-secondary-700 hover:to-secondary-800 focus:ring-secondary-500 shadow-luxury hover:shadow-floating',
		accent: 'bg-gradient-to-r from-accent-600 to-accent-700 text-white hover:from-accent-700 hover:to-accent-800 focus:ring-accent-500 shadow-luxury hover:shadow-floating',
		outline: 'border-2 border-teal-800 text-teal-800 hover:bg-teal-50 hover:border-teal-900 focus:ring-teal-500 shadow-elegant hover:shadow-luxury backdrop-blur-sm',
		ghost: 'text-teal-800 hover:bg-teal-50 hover:text-teal-900 focus:ring-teal-500 hover:shadow-elegant backdrop-blur-sm'
	};

	const sizeClasses = {
		xs: 'px-2 py-1 text-xs rounded-lg font-medium',
		sm: 'px-4 py-2 text-sm rounded-xl font-medium',
		md: 'px-6 py-3 text-base rounded-2xl',
		lg: 'px-8 py-4 text-lg rounded-2xl'
	};

	$: classes = `${baseClasses} ${variantClasses[variant]} ${sizeClasses[size]}`;
</script>

{#if href}
	<a {href} class={classes} class:opacity-50={disabled} class:cursor-not-allowed={disabled}>
		{#if loading}
			<svg class="animate-spin -ml-1 mr-2 h-4 w-4" xmlns="http://www.w3.org/2000/svg" fill="none" viewBox="0 0 24 24">
				<circle class="opacity-25" cx="12" cy="12" r="10" stroke="currentColor" stroke-width="4"></circle>
				<path class="opacity-75" fill="currentColor" d="M4 12a8 8 0 018-8V0C5.373 0 0 5.373 0 12h4zm2 5.291A7.962 7.962 0 014 12H0c0 3.042 1.135 5.824 3 7.938l3-2.647z"></path>
			</svg>
		{/if}
		<slot />
	</a>
{:else}
	<button {type} {disabled} class={classes} on:click>
		{#if loading}
			<svg class="animate-spin -ml-1 mr-2 h-4 w-4" xmlns="http://www.w3.org/2000/svg" fill="none" viewBox="0 0 24 24">
				<circle class="opacity-25" cx="12" cy="12" r="10" stroke="currentColor" stroke-width="4"></circle>
				<path class="opacity-75" fill="currentColor" d="M4 12a8 8 0 018-8V0C5.373 0 0 5.373 0 12h4zm2 5.291A7.962 7.962 0 014 12H0c0 3.042 1.135 5.824 3 7.938l3-2.647z"></path>
			</svg>
		{/if}
		<slot />
	</button>
{/if}
