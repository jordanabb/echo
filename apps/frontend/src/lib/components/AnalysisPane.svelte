<script lang="ts">
	import { writable } from 'svelte/store';
	import { slide } from 'svelte/transition';
	import { quintOut } from 'svelte/easing';
	import { onMount } from 'svelte';
	import DataTable from './DataTable.svelte';
	import ChartView from './ChartView.svelte';
	import Card from './Card.svelte';
	import { selectedView } from '../stores/interactiveSteps';
	
	// Tab definitions
	type TabId = 'table' | 'chart';
	
	interface Tab {
		id: TabId;
		label: string;
		icon: string;
		description: string;
	}
	
	const tabs: Tab[] = [
		{
			id: 'table',
			label: 'Data Table',
			icon: 'M3 10h18M3 14h18m-9-4v8m-7 0V4a1 1 0 011-1h12a1 1 0 011 1v16a1 1 0 01-1 1H4a1 1 0 01-1-1z',
			description: 'View and explore your data in a comprehensive table format'
		},
		{
			id: 'chart',
			label: 'Chart View',
			icon: 'M9 19v-6a2 2 0 00-2-2H5a2 2 0 00-2 2v6a2 2 0 002 2h2a2 2 0 002-2zm0 0V9a2 2 0 012-2h2a2 2 0 012 2v10m-6 0a2 2 0 002 2h2a2 2 0 002-2m0 0V5a2 2 0 012-2h2a2 2 0 012 2v14a2 2 0 01-2 2h-2a2 2 0 01-2-2z',
			description: 'Create visualizations and charts from your selected data'
		}
	];
	
	// Active tab state
	let activeTab: TabId = 'table';
	
	// Watch for external view selection changes
	$: if ($selectedView === 'table' || $selectedView === 'chart') {
		activeTab = $selectedView;
	}
	
	// Function to switch tabs
	function switchTab(tabId: TabId) {
		activeTab = tabId;
	}
	
	// Function to get tab button classes
	function getTabButtonClasses(tabId: TabId): string {
		const baseClasses = 'flex items-center space-x-3 px-5 py-3 text-sm font-semibold rounded-xl transition-all duration-300 focus:outline-none focus:ring-2 focus:ring-teal-500 focus:ring-offset-2';
		
		if (activeTab === tabId) {
			return `${baseClasses} bg-gradient-to-r from-teal-600 to-teal-700 text-white shadow-luxury hover:shadow-floating border border-teal-800/20`;
		} else {
			return `${baseClasses} text-teal-700 hover:text-teal-900 bg-white/60 backdrop-blur-sm border border-teal-200/60 hover:bg-white hover:shadow-elegant`;
		}
	}
	
	// Function to get tab indicator classes
	function getTabIndicatorClasses(tabId: TabId): string {
		const baseClasses = 'absolute bottom-0 left-0 h-0.5 bg-blue-600 transition-all duration-300 ease-out';
		
		if (activeTab === tabId) {
			return `${baseClasses} w-full opacity-100`;
		} else {
			return `${baseClasses} w-0 opacity-0`;
		}
	}
</script>

<div class="w-full bg-gradient-to-br from-white via-white to-teal-50/30 rounded-2xl shadow-floating border border-teal-200/30 backdrop-blur-sm">
	<!-- Tab Navigation -->
	<div class="border-b border-teal-200/40 bg-gradient-to-r from-white via-teal-50/20 to-white rounded-t-2xl">
		<div class="px-6 pt-6 pb-0">
			<div class="flex items-center justify-between mb-6">
				<div class="flex items-center space-x-3">
					<div class="w-10 h-10 rounded-xl bg-gradient-to-br from-teal-100 to-teal-200 flex items-center justify-center shadow-elegant">
						<svg class="w-5 h-5 text-teal-700" fill="none" stroke="currentColor" viewBox="0 0 24 24">
							<path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M9 19v-6a2 2 0 00-2-2H5a2 2 0 00-2 2v6a2 2 0 002 2h2a2 2 0 002-2zm0 0V9a2 2 0 012-2h2a2 2 0 012 2v10m-6 0a2 2 0 002 2h2a2 2 0 002-2m0 0V5a2 2 0 012-2h2a2 2 0 012 2v14a2 2 0 01-2 2h-2a2 2 0 01-2-2z"/>
						</svg>
					</div>
					<div>
						<h2 class="text-2xl font-bold text-teal-900">Data Analysis</h2>
						<p class="text-sm text-teal-700 mt-0.5">
							Explore your data through tables and visualizations
						</p>
					</div>
				</div>
			</div>
			
			<!-- Tab Buttons -->
			<div class="flex space-x-2">
				{#each tabs as tab}
					<button
						class={getTabButtonClasses(tab.id)}
						on:click={() => switchTab(tab.id)}
						title={tab.description}
					>
						<div class="flex items-center space-x-2">
							<div class="w-6 h-6 rounded-lg bg-gradient-to-br from-teal-100 to-teal-200 flex items-center justify-center">
								<svg class="w-4 h-4 text-teal-700" fill="none" stroke="currentColor" viewBox="0 0 24 24">
									<path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="{tab.icon}"/>
								</svg>
							</div>
							<span>{tab.label}</span>
						</div>
						
						<!-- Active indicator -->
						{#if activeTab === tab.id}
							<div class="ml-2 w-2 h-2 bg-teal-600 rounded-full animate-pulse"></div>
						{/if}
					</button>
				{/each}
			</div>
		</div>
	</div>
	
	<!-- Tab Content -->
	<div class="relative">
		<!-- Table View -->
		{#if activeTab === 'table'}
			<div 
				class="w-full"
				in:slide={{ duration: 300, easing: quintOut }}
				out:slide={{ duration: 200, easing: quintOut }}
			>
				<div class="p-6">
					<DataTable />
				</div>
			</div>
		{/if}
		
		<!-- Chart View -->
		{#if activeTab === 'chart'}
			<div 
				class="w-full"
				in:slide={{ duration: 300, easing: quintOut }}
				out:slide={{ duration: 200, easing: quintOut }}
			>
				<div class="p-6">
					<ChartView />
				</div>
			</div>
		{/if}
	</div>
	
	<!-- Tab Content Info Bar -->
	<div class="bg-gradient-to-r from-white via-teal-50/20 to-white border-t border-teal-200/40 px-6 py-4 rounded-b-2xl">
		<div class="flex items-center justify-between">
			<div class="flex items-center space-x-3">
				<div class="w-6 h-6 rounded-lg bg-gradient-to-br from-teal-100 to-teal-200 flex items-center justify-center">
					<svg class="w-4 h-4 text-teal-700" fill="none" stroke="currentColor" viewBox="0 0 24 24">
						<path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="{tabs.find(tab => tab.id === activeTab)?.icon}"/>
					</svg>
				</div>
				<span class="text-sm font-medium text-teal-700">
					{tabs.find(tab => tab.id === activeTab)?.description}
				</span>
			</div>
			
			<!-- Quick Switch Buttons -->
			<div class="flex items-center space-x-3">
				<span class="text-xs font-medium text-teal-600">Quick switch:</span>
				{#each tabs as tab}
					{#if tab.id !== activeTab}
						<button
							class="text-xs text-teal-600 hover:text-teal-800 font-semibold bg-white/60 backdrop-blur-sm border border-teal-200/60 rounded-lg px-3 py-1.5 hover:bg-white hover:shadow-elegant transition-all duration-300"
							on:click={() => switchTab(tab.id)}
						>
							{tab.label}
						</button>
					{/if}
				{/each}
			</div>
		</div>
	</div>
</div>

<style>
	/* Custom styles for smooth transitions */
	.tab-content {
		min-height: 400px;
	}
	
	/* Ensure smooth tab switching */
	:global(.tab-transition) {
		transition: all 0.3s ease-out;
	}
</style>
