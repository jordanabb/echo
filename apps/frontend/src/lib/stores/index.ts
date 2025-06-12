import { writable } from 'svelte/store';

// Theme store for managing dark/light mode
export const theme = writable<'light' | 'dark'>('light');

// Loading state store
export const isLoading = writable<boolean>(false);

// User preferences store
interface UserPreferences {
	language: string;
	notifications: boolean;
	autoSave: boolean;
}

export const userPreferences = writable<UserPreferences>({
	language: 'en',
	notifications: true,
	autoSave: true
});

// Navigation state store
export const currentPage = writable<string>('/');

// Modal state store
export const modalState = writable<{
	isOpen: boolean;
	type: string | null;
	data: any;
}>({
	isOpen: false,
	type: null,
	data: null
});

// Export metadata and filter stores
export * from './metadata';
export * from './filters';
