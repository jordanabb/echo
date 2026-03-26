<script lang="ts">
	import { createEventDispatcher } from 'svelte';

	export let variant: 'primary' | 'secondary' | 'accent' | 'outline' | 'ghost' = 'primary';
	export let size: 'xs' | 'sm' | 'md' | 'lg' = 'md';
	export let disabled = false;
	export let loading = false;
	export let href: string | undefined = undefined;
	export let type: 'button' | 'submit' | 'reset' = 'button';
	export let ripple = true;
	export let className = '';

	const dispatch = createEventDispatcher();

	let buttonElement: HTMLButtonElement | HTMLAnchorElement;
	let rippleElements: Array<{ id: number; x: number; y: number }> = [];
	let rippleId = 0;

	const baseClasses = 'relative inline-flex items-center justify-center font-semibold transition-all duration-300 focus:outline-none focus:ring-2 focus:ring-offset-2 disabled:opacity-50 disabled:cursor-not-allowed transform hover:scale-[1.02] active:scale-[0.98] overflow-hidden';

	const variantClasses = {
		primary: 'bg-teal-50 text-teal-800 hover:bg-teal-100 focus:ring-teal-500 border-2 border-teal-700 hover:border-teal-800',
		secondary: 'bg-gradient-to-r from-secondary-600 to-secondary-700 text-white hover:from-secondary-700 hover:to-secondary-800 focus:ring-secondary-500 shadow-luxury hover:shadow-floating',
		accent: 'bg-gradient-to-r from-accent-600 to-accent-700 text-white hover:from-accent-700 hover:to-accent-800 focus:ring-accent-500 shadow-luxury hover:shadow-floating',
		outline: 'border-2 border-neutral-300 text-neutral-800 hover:bg-neutral-50 hover:border-neutral-400 focus:ring-neutral-400 backdrop-blur-sm',
		ghost: 'text-neutral-700 hover:bg-neutral-50 hover:text-neutral-900 focus:ring-neutral-400 backdrop-blur-sm'
	};

	const sizeClasses = {
		xs: 'px-2 py-1 text-xs rounded-lg font-medium',
		sm: 'px-4 py-2 text-sm rounded-xl font-medium',
		md: 'px-6 py-3 text-base rounded-2xl',
		lg: 'px-8 py-4 text-lg rounded-2xl'
	};

	$: classes = `${baseClasses} ${variantClasses[variant]} ${sizeClasses[size]} ${className}`;

	function createRipple(event: MouseEvent) {
		if (!ripple || disabled || loading) return;

		const rect = buttonElement.getBoundingClientRect();
		const x = event.clientX - rect.left;
		const y = event.clientY - rect.top;

		const newRipple = {
			id: rippleId++,
			x,
			y
		};

		rippleElements = [...rippleElements, newRipple];

		// Remove ripple after animation
		setTimeout(() => {
			rippleElements = rippleElements.filter(r => r.id !== newRipple.id);
		}, 600);
	}

	function handleClick(event: MouseEvent) {
		createRipple(event);
		dispatch('click', event);
	}
</script>

{#if href}
	<a 
		{href} 
		class={classes} 
		class:opacity-50={disabled} 
		class:cursor-not-allowed={disabled}
		bind:this={buttonElement}
		on:click={handleClick}
	>
		<!-- Ripple Effects -->
		{#each rippleElements as ripple (ripple.id)}
			<span
				class="absolute rounded-full bg-white bg-opacity-30 pointer-events-none animate-ripple"
				style="left: {ripple.x}px; top: {ripple.y}px; width: 0; height: 0; transform: translate(-50%, -50%);"
			></span>
		{/each}

		<!-- Content -->
		<span class="relative z-10 flex items-center">
			{#if loading}
				<svg class="animate-spin -ml-1 mr-2 h-4 w-4" xmlns="http://www.w3.org/2000/svg" fill="none" viewBox="0 0 24 24">
					<circle class="opacity-25" cx="12" cy="12" r="10" stroke="currentColor" stroke-width="4"></circle>
					<path class="opacity-75" fill="currentColor" d="M4 12a8 8 0 018-8V0C5.373 0 0 5.373 0 12h4zm2 5.291A7.962 7.962 0 014 12H0c0 3.042 1.135 5.824 3 7.938l3-2.647z"></path>
				</svg>
			{/if}
			<slot />
		</span>
	</a>
{:else}
	<button 
		{type} 
		{disabled} 
		class={classes} 
		bind:this={buttonElement}
		on:click={handleClick}
	>
		<!-- Ripple Effects -->
		{#each rippleElements as ripple (ripple.id)}
			<span
				class="absolute rounded-full bg-white bg-opacity-30 pointer-events-none animate-ripple"
				style="left: {ripple.x}px; top: {ripple.y}px; width: 0; height: 0; transform: translate(-50%, -50%);"
			></span>
		{/each}

		<!-- Content -->
		<span class="relative z-10 flex items-center">
			{#if loading}
				<svg class="animate-spin -ml-1 mr-2 h-4 w-4" xmlns="http://www.w3.org/2000/svg" fill="none" viewBox="0 0 24 24">
					<circle class="opacity-25" cx="12" cy="12" r="10" stroke="currentColor" stroke-width="4"></circle>
					<path class="opacity-75" fill="currentColor" d="M4 12a8 8 0 018-8V0C5.373 0 0 5.373 0 12h4zm2 5.291A7.962 7.962 0 014 12H0c0 3.042 1.135 5.824 3 7.938l3-2.647z"></path>
				</svg>
			{/if}
			<slot />
		</span>
	</button>
{/if}
