<script lang="ts">
	export let variant: 'default' | 'elevated' | 'outlined' | 'glass' | 'premium' | 'floating' = 'default';
	export let padding: 'none' | 'sm' | 'md' | 'lg' | 'xl' = 'md';
	export let hover = false;

	const baseClasses = 'rounded-2xl transition-all duration-300 relative overflow-hidden';

	const variantClasses = {
		default: 'bg-white border border-slate-200/60 shadow-elegant hover:shadow-luxury',
		elevated: 'bg-card-gradient shadow-luxury hover:shadow-floating border border-white/20',
		outlined: 'bg-white/95 border-2 border-teal-200/60 hover:border-teal-300/80 shadow-elegant hover:shadow-luxury backdrop-blur-sm',
		glass: 'bg-white/70 backdrop-blur-md border border-white/30 shadow-glass hover:shadow-glass-lg',
		premium: 'bg-gradient-to-br from-white via-teal-50/30 to-white shadow-premium hover:shadow-floating border border-teal-100/50',
		floating: 'bg-white shadow-floating hover:shadow-floating border border-slate-100/80 hover:border-teal-200/60'
	};

	const paddingClasses = {
		none: '',
		sm: 'p-4',
		md: 'p-6',
		lg: 'p-8',
		xl: 'p-10'
	};

	const hoverClasses = hover ? 'hover:scale-[1.01] hover:-translate-y-1 cursor-pointer' : '';

	$: classes = `${baseClasses} ${variantClasses[variant]} ${paddingClasses[padding]} ${hoverClasses}`;
</script>

<div class={classes} on:click on:keydown role="button" tabindex="0">
	<slot />
</div>
