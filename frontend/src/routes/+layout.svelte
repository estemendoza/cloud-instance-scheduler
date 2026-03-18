<script lang="ts">
  import { onMount } from 'svelte';
  import { goto } from '$app/navigation';
  import { page } from '$app/stores';
  import { Toaster } from 'svelte-french-toast';
  import { authStore } from '$lib/stores/auth';
  import { systemStore } from '$lib/stores/system';
  import { systemAPI } from '$lib/api/endpoints/system';
  import type { Snippet } from 'svelte';
  import '../app.css';

  let { children }: { children: Snippet } = $props();

  let loading = true;

  // Public routes that don't require authentication
  const publicRoutes = ['/bootstrap', '/login'];

  onMount(async () => {
    const currentPath = $page.url.pathname;
    const isPublicRoute = publicRoutes.includes(currentPath);

    try {
      // First, check if system is bootstrapped
      const status = await systemAPI.getStatus();
      systemStore.set({ bootstrapped: status.bootstrapped, version: status.version });

      if (!status.bootstrapped) {
        // System not bootstrapped - only allow bootstrap page
        if (currentPath !== '/bootstrap') {
          goto('/bootstrap');
        }
        loading = false;
        return;
      }

      // System is bootstrapped - try to restore session from refresh token
      const restored = await authStore.restore();

      if (restored) {
        // Session restored successfully
        // If on login/bootstrap page with valid auth, redirect to dashboard
        if (isPublicRoute) {
          goto('/');
          return;
        }
      } else {
        // No valid session - redirect to login (unless already on public route)
        if (!isPublicRoute) {
          goto('/login');
        }
      }
    } catch (err) {
      // If we can't reach the API, show error or redirect to login
      console.error('Failed to check system status:', err);
      if (!isPublicRoute) {
        goto('/login');
      }
    }

    loading = false;
  });
</script>

<!-- Toast notifications -->
<Toaster
  position="top-right"
  toastOptions={{
    duration: 4000,
    style: 'background: #1e293b; color: #e2e8f0; border: 1px solid #334155;'
  }}
/>

{#if loading}
  <div class="flex items-center justify-center h-screen bg-slate-900">
    <div class="text-center">
      <div class="animate-spin rounded-full h-10 w-10 border-2 border-slate-700 border-t-emerald-500 mx-auto mb-4"></div>
      <p class="text-slate-500 text-sm font-mono">Initializing...</p>
    </div>
  </div>
{:else}
  {@render children()}
{/if}
