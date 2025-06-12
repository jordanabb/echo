<script lang="ts">
	export let variant: 'default' | 'elevated' | 'outlined' | 'glass' = 'default';
	export let padding: 'none' | 'sm' | 'md' | 'lg' = 'md';
	export let hover = false;

	const baseClasses = 'rounded-xl transition-all duration-200';

	const variantClasses = {
		default: 'bg-white border border-neutral-200 shadow-soft',
		elevated: 'bg-white shadow-medium hover:shadow-hard',
		outlined: 'bg-white border-2 border-neutral-300',
		glass: 'bg-white/80 backdrop-blur-sm border border-white/20 shadow-soft'
	};

	const paddingClasses = {
		none: '',
		sm: 'p-4',
		md: 'p-6',
		lg: 'p-8'
	};

	const hoverClasses = hover ? 'hover:scale-[1.02] hover:shadow-medium cursor-pointer' : '';

	$: classes = `${baseClasses} ${variantClasses[variant]} ${paddingClasses[padding]} ${hoverClasses}`;
</script>

<div class={classes} on:click on:keydown role="button" tabindex="0">
	<slot />
</div>
