// API base URL utility
// In production, PUBLIC_API_URL points to the App Runner backend.
// In development, the vite proxy handles /api → localhost:8000,
// so we can leave the base empty.
import { PUBLIC_API_URL } from '$env/static/public';

const API_BASE = PUBLIC_API_URL || '';

export function apiUrl(path: string): string {
	// Ensure path starts with /
	if (!path.startsWith('/')) {
		path = '/' + path;
	}
	return `${API_BASE}${path}`;
}
