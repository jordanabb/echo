<script lang="ts">
	export let variant: 'text' | 'card' | 'table' | 'map' | 'chart' | 'custom' = 'text';
	export let lines: number = 3;
	export let width: string = 'w-full';
	export let height: string = 'h-4';
	export let className: string = '';
	export let animate: boolean = true;

	const baseClasses = 'bg-gradient-to-r from-neutral-200 via-neutral-100 to-neutral-200 rounded';
	const animationClasses = animate ? 'bg-[length:200%_100%] animate-shimmer' : 'animate-skeleton-pulse';
	
	$: skeletonClasses = `${baseClasses} ${animationClasses} ${className}`;
</script>

{#if variant === 'text'}
	<div class="space-y-3">
		{#each Array(lines) as _, i}
			<div 
				class="{skeletonClasses} {height} {i === lines - 1 ? 'w-3/4' : width}"
				style="animation-delay: {i * 0.1}s"
			></div>
		{/each}
	</div>

{:else if variant === 'card'}
	<div class="bg-white rounded-2xl shadow-elegant p-6 space-y-4">
		<!-- Header -->
		<div class="flex items-center space-x-3">
			<div class="{skeletonClasses} w-12 h-12 rounded-full"></div>
			<div class="flex-1 space-y-2">
				<div class="{skeletonClasses} h-4 w-3/4"></div>
				<div class="{skeletonClasses} h-3 w-1/2"></div>
			</div>
		</div>
		
		<!-- Content -->
		<div class="space-y-3">
			{#each Array(3) as _, i}
				<div 
					class="{skeletonClasses} h-4 {i === 2 ? 'w-2/3' : 'w-full'}"
					style="animation-delay: {(i + 2) * 0.1}s"
				></div>
			{/each}
		</div>
		
		<!-- Footer -->
		<div class="flex justify-between items-center pt-4">
			<div class="{skeletonClasses} h-8 w-20 rounded-lg"></div>
			<div class="{skeletonClasses} h-8 w-16 rounded-lg"></div>
		</div>
	</div>

{:else if variant === 'table'}
	<div class="bg-white rounded-2xl shadow-elegant overflow-hidden">
		<!-- Table Header -->
		<div class="bg-neutral-50 px-6 py-4 border-b border-neutral-200">
			<div class="flex justify-between items-center">
				<div class="{skeletonClasses} h-6 w-32"></div>
				<div class="{skeletonClasses} h-8 w-24 rounded-lg"></div>
			</div>
		</div>
		
		<!-- Table Content -->
		<div class="p-6">
			<!-- Search Bar -->
			<div class="mb-4">
				<div class="{skeletonClasses} h-10 w-full rounded-lg"></div>
			</div>
			
			<!-- Table Headers -->
			<div class="grid grid-cols-4 gap-4 mb-4 pb-3 border-b border-neutral-200">
				{#each Array(4) as _, i}
					<div 
						class="{skeletonClasses} h-4 w-full"
						style="animation-delay: {i * 0.05}s"
					></div>
				{/each}
			</div>
			
			<!-- Table Rows -->
			{#each Array(5) as _, rowIndex}
				<div class="grid grid-cols-4 gap-4 py-3 border-b border-neutral-100">
					{#each Array(4) as _, colIndex}
						<div 
							class="{skeletonClasses} h-4 {colIndex === 0 ? 'w-3/4' : colIndex === 3 ? 'w-1/2' : 'w-full'}"
							style="animation-delay: {(rowIndex * 4 + colIndex) * 0.02}s"
						></div>
					{/each}
				</div>
			{/each}
		</div>
	</div>

{:else if variant === 'map'}
	<div class="relative bg-white rounded-2xl shadow-elegant overflow-hidden">
		<!-- Map Container -->
		<div class="h-96 relative">
			<div class="{skeletonClasses} w-full h-full"></div>
			
			<!-- Floating Elements -->
			<div class="absolute top-4 left-4 space-y-2">
				<div class="{skeletonClasses} w-32 h-8 rounded-lg"></div>
				<div class="{skeletonClasses} w-24 h-6 rounded-lg"></div>
			</div>
			
			<div class="absolute bottom-4 right-4">
				<div class="{skeletonClasses} w-20 h-24 rounded-lg"></div>
			</div>
			
			<!-- Loading Overlay -->
			<div class="absolute inset-0 bg-white bg-opacity-75 flex items-center justify-center">
				<div class="text-center">
					<div class="w-12 h-12 border-4 border-teal-200 border-t-teal-600 rounded-full animate-spin mb-4"></div>
					<div class="{skeletonClasses} h-4 w-32"></div>
				</div>
			</div>
		</div>
	</div>

{:else if variant === 'chart'}
	<div class="bg-white rounded-2xl shadow-elegant p-6">
		<!-- Chart Header -->
		<div class="flex justify-between items-center mb-6">
			<div class="space-y-2">
				<div class="{skeletonClasses} h-6 w-48"></div>
				<div class="{skeletonClasses} h-4 w-32"></div>
			</div>
			<div class="{skeletonClasses} h-8 w-20 rounded-lg"></div>
		</div>
		
		<!-- Chart Area -->
		<div class="relative h-64">
			<!-- Y-axis labels -->
			<div class="absolute left-0 top-0 bottom-0 w-8 flex flex-col justify-between py-2">
				{#each Array(5) as _, i}
					<div 
						class="{skeletonClasses} h-3 w-6"
						style="animation-delay: {i * 0.1}s"
					></div>
				{/each}
			</div>
			
			<!-- Chart bars/lines -->
			<div class="ml-12 h-full flex items-end justify-between space-x-2">
				{#each Array(8) as _, i}
					<div 
						class="{skeletonClasses} w-8 rounded-t"
						style="height: {Math.random() * 60 + 20}%; animation-delay: {i * 0.1}s"
					></div>
				{/each}
			</div>
			
			<!-- X-axis labels -->
			<div class="ml-12 mt-2 flex justify-between">
				{#each Array(8) as _, i}
					<div 
						class="{skeletonClasses} h-3 w-8"
						style="animation-delay: {i * 0.05}s"
					></div>
				{/each}
			</div>
		</div>
	</div>

{:else if variant === 'custom'}
	<div class="{skeletonClasses} {width} {height}"></div>
{/if}
