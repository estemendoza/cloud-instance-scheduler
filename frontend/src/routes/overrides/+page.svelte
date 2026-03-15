<script lang="ts">
  import { onMount } from 'svelte';
  import Sidebar from '$lib/components/layout/Sidebar.svelte';
  import { overridesAPI } from '$lib/api/endpoints/overrides';
  import { resourcesAPI } from '$lib/api/endpoints/resources';
  import { authStore } from '$lib/stores/auth';
  import type { Override } from '$lib/types/override';
  import type { Resource } from '$lib/types/resource';

  let loading = true;
  let error = '';
  let overrides: Override[] = [];
  let resourceMap: Map<string, Resource> = new Map();

  $: canManage = $authStore.user?.role === 'admin' || $authStore.user?.role === 'operator';

  onMount(async () => {
    await loadOverrides();
  });

  async function loadOverrides() {
    loading = true;
    error = '';

    try {
      const [overridesData, resourcesData] = await Promise.all([
        overridesAPI.list(),
        resourcesAPI.list({ page_size: 100 }).catch(() => ({ items: [] }))
      ]);
      overrides = overridesData;
      resourceMap = new Map(resourcesData.items.map((r: Resource) => [r.id, r]));
    } catch (err: any) {
      error = err.message || 'Failed to load overrides';
    } finally {
      loading = false;
    }
  }

  async function cancelOverride(overrideId: string) {
    if (!confirm('Cancel this override?')) return;
    try {
      await overridesAPI.cancel(overrideId);
      overrides = overrides.filter(o => o.id !== overrideId);
    } catch (err: any) {
      alert(err.message || 'Failed to cancel override');
    }
  }

  function getResourceName(resourceId: string): string {
    const resource = resourceMap.get(resourceId);
    return resource?.name || resource?.provider_resource_id || resourceId.slice(0, 8) + '...';
  }

  function getResourceProviderId(resourceId: string): string | null {
    const resource = resourceMap.get(resourceId);
    return resource?.name ? resource.provider_resource_id : null;
  }

  function formatRelativeTime(dateStr: string): string {
    const date = new Date(dateStr);
    const now = new Date();
    const diffMs = date.getTime() - now.getTime();
    const absDiffMs = Math.abs(diffMs);
    const hours = Math.floor(absDiffMs / (1000 * 60 * 60));
    const days = Math.floor(hours / 24);
    if (days > 0) return diffMs > 0 ? `in ${days}d ${hours % 24}h` : `${days}d ago`;
    if (hours > 0) return diffMs > 0 ? `in ${hours}h` : `${hours}h ago`;
    const mins = Math.floor(absDiffMs / (1000 * 60));
    return diffMs > 0 ? `in ${mins}m` : `${mins}m ago`;
  }
</script>

<svelte:head>
  <title>Overrides - Cloud Instance Scheduler</title>
</svelte:head>

<div class="flex h-screen bg-slate-900">
  <Sidebar />

  <main class="flex-1 overflow-y-auto pt-14 lg:pt-0">
    <div class="p-6">
      <!-- Header -->
      <div class="mb-6 flex justify-between items-start">
        <div>
          <h1 class="text-xl font-semibold text-slate-100">Overrides</h1>
          <p class="text-sm text-slate-500 mt-1">
            Manage manual overrides that temporarily override policy schedules
          </p>
        </div>
        <button
          on:click={loadOverrides}
          disabled={loading}
          class="px-3 py-1.5 text-sm text-slate-400 hover:text-slate-200 bg-slate-800 hover:bg-slate-700 border border-slate-700 rounded transition-colors disabled:opacity-50"
        >
          {loading ? 'Loading...' : 'Refresh'}
        </button>
      </div>

      {#if error}
        <div class="mb-4 p-3 bg-red-900/30 border border-red-800 rounded">
          <p class="text-sm text-red-400">{error}</p>
        </div>
      {/if}

      <!-- Overrides Table -->
      <div class="bg-slate-800 border border-slate-700 rounded-lg overflow-hidden">
        <div class="overflow-x-auto">
          <table class="min-w-full">
            <thead>
              <tr class="border-b border-slate-700">
                <th class="px-4 py-3 text-left text-xs font-medium text-slate-500 uppercase tracking-wider">
                  Resource
                </th>
                <th class="px-4 py-3 text-left text-xs font-medium text-slate-500 uppercase tracking-wider">
                  Desired State
                </th>
                <th class="px-4 py-3 text-left text-xs font-medium text-slate-500 uppercase tracking-wider">
                  Expires
                </th>
                <th class="px-4 py-3 text-left text-xs font-medium text-slate-500 uppercase tracking-wider">
                  Reason
                </th>
                <th class="px-4 py-3 text-left text-xs font-medium text-slate-500 uppercase tracking-wider">
                  Created
                </th>
                {#if canManage}
                  <th class="px-4 py-3 text-left text-xs font-medium text-slate-500 uppercase tracking-wider">
                    Actions
                  </th>
                {/if}
              </tr>
            </thead>
            <tbody class="divide-y divide-slate-700/50">
              {#if loading}
                {#each Array(5) as _}
                  <tr>
                    {#each Array(canManage ? 6 : 5) as _}
                      <td class="px-4 py-3">
                        <div class="h-4 bg-slate-700 rounded animate-pulse"></div>
                      </td>
                    {/each}
                  </tr>
                {/each}
              {:else if overrides.length === 0}
                <tr>
                  <td colspan={canManage ? 6 : 5} class="px-4 py-12 text-center">
                    <svg class="w-8 h-8 text-slate-600 mx-auto mb-3" fill="none" viewBox="0 0 24 24" stroke="currentColor">
                      <path stroke-linecap="round" stroke-linejoin="round" stroke-width="1.5" d="M9 12l2 2 4-4m5.618-4.016A11.955 11.955 0 0112 2.944a11.955 11.955 0 01-8.618 3.04A12.02 12.02 0 003 9c0 5.591 3.824 10.29 9 11.622 5.176-1.332 9-6.03 9-11.622 0-1.042-.133-2.052-.382-3.016z" />
                    </svg>
                    <p class="text-sm text-slate-500">No active overrides</p>
                    <p class="text-xs text-slate-600 mt-1">Overrides can be created from the resource detail page</p>
                  </td>
                </tr>
              {:else}
                {#each overrides as override}
                  <tr class="hover:bg-slate-700/50 transition-colors">
                    <td class="px-4 py-3">
                      <div class="flex flex-col">
                        <a
                          href="/resources/{override.resource_id}"
                          class="text-sm font-medium text-slate-200 hover:text-emerald-400 transition-colors"
                        >
                          {getResourceName(override.resource_id)}
                        </a>
                        {#if getResourceProviderId(override.resource_id)}
                          <span class="text-xs text-slate-500 font-mono">{getResourceProviderId(override.resource_id)}</span>
                        {/if}
                      </div>
                    </td>
                    <td class="px-4 py-3">
                      <span class="inline-flex px-2 py-0.5 text-xs font-medium rounded border {override.desired_state === 'RUNNING'
                        ? 'bg-emerald-900/50 text-emerald-400 border-emerald-800'
                        : 'bg-slate-700 text-slate-400 border-slate-600'}">
                        {override.desired_state}
                      </span>
                    </td>
                    <td class="px-4 py-3">
                      <div class="flex flex-col">
                        <span class="text-sm text-slate-300">{formatRelativeTime(override.expires_at)}</span>
                        <span class="text-xs text-slate-500">{new Date(override.expires_at).toLocaleString()}</span>
                      </div>
                    </td>
                    <td class="px-4 py-3 text-sm text-slate-400">
                      {override.reason || '—'}
                    </td>
                    <td class="px-4 py-3 text-sm text-slate-500">
                      {new Date(override.created_at).toLocaleString()}
                    </td>
                    {#if canManage}
                      <td class="px-4 py-3">
                        <button
                          on:click={() => cancelOverride(override.id)}
                          class="text-xs text-red-400 hover:text-red-300 transition-colors"
                        >
                          Cancel
                        </button>
                      </td>
                    {/if}
                  </tr>
                {/each}
              {/if}
            </tbody>
          </table>
        </div>
      </div>
    </div>
  </main>
</div>
