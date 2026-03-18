<script lang="ts">
  import { onMount } from 'svelte';
  import { goto } from '$app/navigation';
  import Sidebar from '$lib/components/layout/Sidebar.svelte';
  import { resourcesAPI } from '$lib/api/endpoints/resources';
  import { overridesAPI } from '$lib/api/endpoints/overrides';
  import type { Resource, ResourceFilter } from '$lib/types/resource';
  import type { Override } from '$lib/types/override';

  let loading = $state(true);
  let error = $state('');
  let resources = $state<Resource[]>([]);
  let overrideMap = $state<Map<string, Override>>(new Map());

  // Pagination state
  let currentPage = $state(1);
  let pageSize = $state(25);
  let totalItems = $state(0);
  let totalPages = $state(1);

  // Filter state
  let providerFilter = $state('');
  let stateFilter = $state('');
  let regionFilter = $state('');

  const providerOptions = [
    { value: 'aws', label: 'AWS' },
    { value: 'azure', label: 'Azure' },
    { value: 'gcp', label: 'Google Cloud' }
  ];

  const stateOptions = [
    { value: 'running', label: 'Running' },
    { value: 'stopped', label: 'Stopped' },
    { value: 'pending', label: 'Pending' },
    { value: 'stopping', label: 'Stopping' }
  ];

  const pageSizeOptions = [10, 25, 50, 100];

  onMount(async () => {
    await loadResources();
  });

  async function loadResources() {
    loading = true;
    error = '';

    try {
      const filters: ResourceFilter = {
        page: currentPage,
        page_size: pageSize,
      };
      if (providerFilter) filters.provider_type = providerFilter;
      if (stateFilter) filters.state = stateFilter;
      if (regionFilter) filters.region = regionFilter;

      const [result, activeOverrides] = await Promise.all([
        resourcesAPI.list(filters),
        overridesAPI.list().catch(() => [])
      ]);
      resources = result.items;
      totalItems = result.total;
      totalPages = result.total_pages;
      currentPage = result.page;
      overrideMap = new Map(activeOverrides.map((o: Override) => [o.resource_id, o]));
    } catch (err: any) {
      error = err.message || 'Failed to load resources';
    } finally {
      loading = false;
    }
  }

  function goToPage(page: number) {
    if (page < 1 || page > totalPages || page === currentPage) return;
    currentPage = page;
    loadResources();
  }

  function changePageSize(newSize: number) {
    pageSize = newSize;
    currentPage = 1;
    loadResources();
  }

  function handleRowClick(resource: Resource) {
    goto(`/resources/${resource.id}`);
  }

  function getStateClasses(state: string): string {
    switch (state.toLowerCase()) {
      case 'running':
        return 'bg-emerald-900/50 text-emerald-400 border-emerald-800';
      case 'stopped':
        return 'bg-slate-700 text-slate-400 border-slate-600';
      case 'pending':
      case 'stopping':
        return 'bg-amber-900/50 text-amber-400 border-amber-800';
      default:
        return 'bg-slate-700 text-slate-400 border-slate-600';
    }
  }

  function clearFilters() {
    providerFilter = '';
    stateFilter = '';
    regionFilter = '';
    currentPage = 1;
    loadResources();
  }

  function applyFilters() {
    currentPage = 1;
    loadResources();
  }

  let hasFilters = $derived(providerFilter || stateFilter || regionFilter);

  let pageStart = $derived(totalItems === 0 ? 0 : (currentPage - 1) * pageSize + 1);
  let pageEnd = $derived(Math.min(currentPage * pageSize, totalItems));

  // Generate visible page numbers with ellipsis
  function getVisiblePages(current: number, total: number): (number | '...')[] {
    if (total <= 7) return Array.from({ length: total }, (_, i) => i + 1);

    const pages: (number | '...')[] = [1];

    if (current > 3) pages.push('...');

    const start = Math.max(2, current - 1);
    const end = Math.min(total - 1, current + 1);

    for (let i = start; i <= end; i++) pages.push(i);

    if (current < total - 2) pages.push('...');

    pages.push(total);
    return pages;
  }

  let visiblePages = $derived(getVisiblePages(currentPage, totalPages));

  function getProviderLabel(type: string | null): string {
    switch (type) {
      case 'aws': return 'AWS';
      case 'azure': return 'Azure';
      case 'gcp': return 'GCP';
      default: return '';
    }
  }

  function getProviderBadgeClasses(type: string | null): string {
    switch (type) {
      case 'aws': return 'bg-amber-950/60 text-amber-400 border-amber-800/50';
      case 'azure': return 'bg-blue-950/60 text-blue-400 border-blue-800/50';
      case 'gcp': return 'bg-red-950/60 text-red-400 border-red-800/50';
      default: return 'bg-slate-800 text-slate-500 border-slate-700';
    }
  }
</script>

<svelte:head>
  <title>Resources - Cloud Instance Scheduler</title>
</svelte:head>

<div class="flex h-screen bg-slate-900">
  <Sidebar />

  <main class="flex-1 overflow-y-auto pt-14 lg:pt-0">
    <div class="p-6">
      <!-- Header -->
      <div class="mb-6 flex justify-between items-start">
        <div>
          <h1 class="text-xl font-semibold text-slate-100">Resources</h1>
          <p class="text-sm text-slate-500 mt-1">
            Manage cloud instances and view scheduling status
          </p>
        </div>
        <button
          onclick={loadResources}
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

      <!-- Filters -->
      <div class="bg-slate-800 border border-slate-700 rounded-lg p-4 mb-6">
        <div class="flex flex-wrap gap-4 items-end">
          <div class="w-44">
            <label for="provider-filter" class="block text-xs font-medium text-slate-400 mb-1.5">
              Provider
            </label>
            <select
              id="provider-filter"
              bind:value={providerFilter}
              class="w-full bg-slate-900 border border-slate-700 text-slate-200 text-sm rounded px-3 py-2 focus:border-emerald-500 focus:ring-1 focus:ring-emerald-500 focus:outline-none"
            >
              <option value="">All Providers</option>
              {#each providerOptions as option}
                <option value={option.value}>{option.label}</option>
              {/each}
            </select>
          </div>

          <div class="w-44">
            <label for="state-filter" class="block text-xs font-medium text-slate-400 mb-1.5">
              State
            </label>
            <select
              id="state-filter"
              bind:value={stateFilter}
              class="w-full bg-slate-900 border border-slate-700 text-slate-200 text-sm rounded px-3 py-2 focus:border-emerald-500 focus:ring-1 focus:ring-emerald-500 focus:outline-none"
            >
              <option value="">All States</option>
              {#each stateOptions as option}
                <option value={option.value}>{option.label}</option>
              {/each}
            </select>
          </div>

          <div class="w-44">
            <label for="region-filter" class="block text-xs font-medium text-slate-400 mb-1.5">
              Region
            </label>
            <input
              id="region-filter"
              type="text"
              bind:value={regionFilter}
              placeholder="e.g., us-east-1"
              class="w-full bg-slate-900 border border-slate-700 text-slate-200 text-sm rounded px-3 py-2 placeholder-slate-500 focus:border-emerald-500 focus:ring-1 focus:ring-emerald-500 focus:outline-none"
            />
          </div>

          <div class="flex gap-2">
            <button
              onclick={applyFilters}
              class="px-4 py-2 text-sm font-medium bg-emerald-600 hover:bg-emerald-500 text-white rounded transition-colors"
            >
              Apply
            </button>
            {#if hasFilters}
              <button
                onclick={clearFilters}
                class="px-4 py-2 text-sm text-slate-400 hover:text-slate-200 bg-slate-700 hover:bg-slate-600 rounded transition-colors"
              >
                Clear
              </button>
            {/if}
          </div>
        </div>
      </div>

      <!-- Resources Table -->
      <div class="bg-slate-800 border border-slate-700 rounded-lg overflow-hidden">
        <div class="overflow-x-auto">
          <table class="min-w-full">
            <thead>
              <tr class="border-b border-slate-700">
                <th class="px-4 py-3 text-left text-xs font-medium text-slate-500 uppercase tracking-wider">
                  Name
                </th>
                <th class="px-4 py-3 text-left text-xs font-medium text-slate-500 uppercase tracking-wider">
                  State
                </th>
                <th class="px-4 py-3 text-left text-xs font-medium text-slate-500 uppercase tracking-wider">
                  Region
                </th>
                <th class="px-4 py-3 text-left text-xs font-medium text-slate-500 uppercase tracking-wider">
                  Instance Type
                </th>
                <th class="px-4 py-3 text-left text-xs font-medium text-slate-500 uppercase tracking-wider">
                  Last Seen
                </th>
              </tr>
            </thead>
            <tbody class="divide-y divide-slate-700/50">
              {#if loading}
                {#each Array(pageSize > 10 ? 10 : pageSize) as _}
                  <tr>
                    {#each Array(5) as _}
                      <td class="px-4 py-3">
                        <div class="h-4 bg-slate-700 rounded animate-pulse"></div>
                      </td>
                    {/each}
                  </tr>
                {/each}
              {:else if resources.length === 0}
                <tr>
                  <td colspan="5" class="px-4 py-12 text-center">
                    <svg class="w-8 h-8 text-slate-600 mx-auto mb-3" fill="none" viewBox="0 0 24 24" stroke="currentColor">
                      <path stroke-linecap="round" stroke-linejoin="round" stroke-width="1.5" d="M5 12h14M5 12a2 2 0 01-2-2V6a2 2 0 012-2h14a2 2 0 012 2v4a2 2 0 01-2 2M5 12a2 2 0 00-2 2v4a2 2 0 002 2h14a2 2 0 002-2v-4a2 2 0 00-2-2" />
                    </svg>
                    <p class="text-sm text-slate-500">No resources found</p>
                    <p class="text-xs text-slate-600 mt-1">Try adjusting your filters or add a cloud account</p>
                  </td>
                </tr>
              {:else}
                {#each resources as resource}
                  <tr
                    class="hover:bg-slate-700/50 cursor-pointer transition-colors"
                    onclick={() => handleRowClick(resource)}
                    onkeypress={(e) => e.key === 'Enter' && handleRowClick(resource)}
                    tabindex="0"
                    role="button"
                  >
                    <td class="px-4 py-3">
                      <div class="flex items-center gap-2.5">
                        <!-- Provider badge -->
                        <span
                          class="flex-shrink-0 inline-flex items-center justify-center px-1.5 h-5 text-[10px] font-bold rounded border {getProviderBadgeClasses(resource.provider_type)}"
                          title={getProviderLabel(resource.provider_type)}
                        >
                          {getProviderLabel(resource.provider_type) || '?'}
                        </span>
                        <div class="flex flex-col">
                          <span class="text-sm font-medium text-slate-200">
                            {resource.name || resource.provider_resource_id}
                          </span>
                          {#if resource.name}
                            <span class="text-xs text-slate-500 font-mono">{resource.provider_resource_id}</span>
                          {/if}
                        </div>
                      </div>
                    </td>
                    <td class="px-4 py-3">
                      <div class="flex items-center gap-1.5">
                        <span class="inline-flex px-2 py-0.5 text-xs font-medium rounded border {getStateClasses(resource.state)}">
                          {resource.state}
                        </span>
                        {#if overrideMap.has(resource.id)}
                          <span
                            class="inline-flex px-1.5 py-0.5 text-[10px] font-medium rounded bg-indigo-900/50 text-indigo-400 border border-indigo-800"
                            title="Override active: {overrideMap.get(resource.id)?.desired_state} until {new Date(overrideMap.get(resource.id)?.expires_at || '').toLocaleString()}"
                          >
                            Override
                          </span>
                        {/if}
                      </div>
                    </td>
                    <td class="px-4 py-3 text-sm text-slate-400 font-mono">
                      {resource.region}
                    </td>
                    <td class="px-4 py-3 text-sm text-slate-400 font-mono">
                      {resource.instance_type || '—'}
                    </td>
                    <td class="px-4 py-3 text-sm text-slate-500">
                      {new Date(resource.last_seen_at).toLocaleString()}
                    </td>
                  </tr>
                {/each}
              {/if}
            </tbody>
          </table>
        </div>

        <!-- Pagination -->
        {#if !loading && totalItems > 0}
          <div class="border-t border-slate-700 px-4 py-3 flex flex-wrap items-center justify-between gap-4">
            <!-- Left: showing count and page size -->
            <div class="flex items-center gap-4 text-sm text-slate-400">
              <span>
                Showing <span class="font-mono text-slate-300">{pageStart}</span>–<span class="font-mono text-slate-300">{pageEnd}</span> of <span class="font-mono text-slate-300">{totalItems}</span>
              </span>
              <div class="flex items-center gap-1.5">
                <label for="page-size" class="text-slate-500">Per page:</label>
                <select
                  id="page-size"
                  value={pageSize}
                  onchange={(e) => changePageSize(Number((e.target as HTMLSelectElement).value))}
                  class="bg-slate-900 border border-slate-700 text-slate-300 text-sm rounded px-2 py-1 focus:border-emerald-500 focus:ring-1 focus:ring-emerald-500 focus:outline-none"
                >
                  {#each pageSizeOptions as size}
                    <option value={size}>{size}</option>
                  {/each}
                </select>
              </div>
            </div>

            <!-- Right: page navigation -->
            <div class="flex items-center gap-1">
              <!-- Previous -->
              <button
                onclick={() => goToPage(currentPage - 1)}
                disabled={currentPage <= 1}
                class="px-2 py-1 text-sm text-slate-400 hover:text-slate-200 bg-slate-800 hover:bg-slate-700 border border-slate-700 rounded transition-colors disabled:opacity-30 disabled:cursor-not-allowed disabled:hover:bg-slate-800 disabled:hover:text-slate-400"
                aria-label="Previous page"
              >
                <svg class="w-4 h-4" fill="none" viewBox="0 0 24 24" stroke="currentColor">
                  <path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M15 19l-7-7 7-7" />
                </svg>
              </button>

              <!-- Page numbers -->
              {#each visiblePages as pageNum}
                {#if pageNum === '...'}
                  <span class="px-2 py-1 text-sm text-slate-600">...</span>
                {:else}
                  <button
                    onclick={() => goToPage(pageNum)}
                    class="px-2.5 py-1 text-sm rounded border transition-colors {pageNum === currentPage
                      ? 'bg-emerald-600 border-emerald-500 text-white'
                      : 'text-slate-400 hover:text-slate-200 bg-slate-800 hover:bg-slate-700 border-slate-700'}"
                  >
                    {pageNum}
                  </button>
                {/if}
              {/each}

              <!-- Next -->
              <button
                onclick={() => goToPage(currentPage + 1)}
                disabled={currentPage >= totalPages}
                class="px-2 py-1 text-sm text-slate-400 hover:text-slate-200 bg-slate-800 hover:bg-slate-700 border border-slate-700 rounded transition-colors disabled:opacity-30 disabled:cursor-not-allowed disabled:hover:bg-slate-800 disabled:hover:text-slate-400"
                aria-label="Next page"
              >
                <svg class="w-4 h-4" fill="none" viewBox="0 0 24 24" stroke="currentColor">
                  <path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M9 5l7 7-7 7" />
                </svg>
              </button>
            </div>
          </div>
        {/if}
      </div>
    </div>
  </main>
</div>
