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
			icon: '📊',
			description: 'View and explore your data in a comprehensive table format'
		},
		{
			id: 'chart',
			label: 'Chart View',
			icon: '📈',
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
		const baseClasses = 'flex items-center space-x-2 px-4 py-3 text-sm font-medium rounded-lg transition-all duration-200 focus:outline-none focus:ring-2 focus:ring-blue-500 focus:ring-offset-2';
		
		if (activeTab === tabId) {
			return `${baseClasses} bg-blue-600 text-white shadow-md`;
		} else {
			return `${baseClasses} text-gray-600 hover:text-gray-900 hover:bg-gray-100`;
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

<div class="w-full">
	<!-- Tab Navigation -->
	<div class="border-b border-gray-200 bg-white">
		<div class="px-6 pt-6 pb-0">
			<div class="flex items-center justify-between mb-4">
				<div>
					<h2 class="text-2xl font-bold text-gray-900">Data Analysis</h2>
					<p class="text-sm text-gray-600 mt-1">
						Explore your data through tables and visualizations
					</p>
				</div>
			</div>
			
			<!-- Tab Buttons -->
			<div class="flex space-x-1">
				{#each tabs as tab}
					<button
						class={getTabButtonClasses(tab.id)}
						on:click={() => switchTab(tab.id)}
						title={tab.description}
					>
						<span class="text-lg">{tab.icon}</span>
						<span>{tab.label}</span>
						
						<!-- Active indicator -->
						{#if activeTab === tab.id}
							<div class="ml-2 w-2 h-2 bg-white rounded-full opacity-75"></div>
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
	<div class="bg-gray-50 border-t border-gray-200 px-6 py-3">
		<div class="flex items-center justify-between">
			<div class="flex items-center space-x-2">
				<span class="text-lg">{tabs.find(tab => tab.id === activeTab)?.icon}</span>
				<span class="text-sm text-gray-600">
					{tabs.find(tab => tab.id === activeTab)?.description}
				</span>
			</div>
			
			<!-- Quick Switch Buttons -->
			<div class="flex items-center space-x-2">
				<span class="text-xs text-gray-500">Quick switch:</span>
				{#each tabs as tab}
					{#if tab.id !== activeTab}
						<button
							class="text-xs text-blue-600 hover:text-blue-800 font-medium px-2 py-1 rounded hover:bg-blue-50 transition-colors"
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
