<script lang="ts">
  import { onMount } from 'svelte';
  import { page } from '$app/stores';
  import { goto } from '$app/navigation';
  import Sidebar from '$lib/components/layout/Sidebar.svelte';
  import { executionsAPI } from '$lib/api/endpoints/executions';
  import { resourcesAPI } from '$lib/api/endpoints/resources';
  import type { Execution, ExecutionFilter } from '$lib/types/execution';
  import type { Resource } from '$lib/types/resource';

  let loading = $state(true);
  let error = $state('');
  let executions = $state<Execution[]>([]);
  let resources = $state<Resource[]>([]);
  let totalCount = $state(0);

  const PAGE_SIZE = 20;
  let currentPage = $state(0);

  // Filter state
  let statusFilter = $state('');
  let actionFilter = $state('');
  let hoursFilter = $state('');

  const statusOptions = [
    { value: 'true', label: 'Success' },
    { value: 'false', label: 'Failed' },
    { value: 'pending', label: 'In Progress' }
  ];

  const actionOptions = [
    { value: 'START', label: 'START' },
    { value: 'STOP', label: 'STOP' }
  ];

  const hoursOptions = [
    { value: '1', label: 'Last hour' },
    { value: '24', label: 'Last 24 hours' },
    { value: '168', label: 'Last 7 days' },
    { value: '', label: 'All time' }
  ];

  let resourceMap = $derived(new Map(resources.map(r => [r.id, r])));
  let hasFilters = $derived(statusFilter || actionFilter || hoursFilter);
  let totalPages = $derived(Math.ceil(totalCount / PAGE_SIZE));

  onMount(async () => {
    // Read query params for pre-filtering
    const params = $page.url.searchParams;
    if (params.has('success')) statusFilter = params.get('success')!;
    if (params.has('action')) actionFilter = params.get('action')!;
    if (params.has('hours')) hoursFilter = params.get('hours')!;

    await loadExecutions();
  });

  function buildFilters(pageNum: number): ExecutionFilter {
    const filters: ExecutionFilter = {
      limit: PAGE_SIZE,
      offset: pageNum * PAGE_SIZE
    };
    if (statusFilter === 'pending') {
      filters.status = 'pending';
    } else if (statusFilter) {
      filters.success = statusFilter === 'true';
    }
    if (actionFilter) filters.action = actionFilter;
    if (hoursFilter) filters.hours = Number(hoursFilter);
    return filters;
  }

  async function loadExecutions() {
    loading = true;
    error = '';

    try {
      const filters = buildFilters(currentPage);
      const countFilters: ExecutionFilter = { ...filters };
      delete countFilters.limit;
      delete countFilters.offset;

      const [executionsData, resourcesData, countData] = await Promise.all([
        executionsAPI.list(filters),
        resources.length > 0 ? Promise.resolve(resources) : resourcesAPI.list({ page_size: 100 }).then(r => r.items),
        executionsAPI.getCount(countFilters).catch(() => ({ total: 0 }))
      ]);

      executions = executionsData;
      resources = resourcesData;
      totalCount = countData.total;
    } catch (err: any) {
      error = err.message || 'Failed to load executions';
    } finally {
      loading = false;
    }
  }

  async function loadPage(page: number) {
    currentPage = page;
    loading = true;
    error = '';

    try {
      const filters = buildFilters(page);
      executions = await executionsAPI.list(filters);
    } catch (err: any) {
      error = err.message || 'Failed to load executions';
    } finally {
      loading = false;
    }
  }

  function applyFilters() {
    currentPage = 0;
    loadExecutions();
  }

  function clearFilters() {
    statusFilter = '';
    actionFilter = '';
    hoursFilter = '';
    currentPage = 0;
    loadExecutions();
  }

  function getResourceName(resourceId: string): string {
    const r = resourceMap.get(resourceId);
    return r?.name || r?.provider_resource_id || 'Unknown';
  }

  function handleRowClick(execution: Execution) {
    goto(`/resources/${execution.resource_id}`);
  }

  function timeAgo(dateStr: string): string {
    const diff = Date.now() - new Date(dateStr).getTime();
    const mins = Math.floor(diff / 60000);
    if (mins < 1) return 'just now';
    if (mins < 60) return `${mins}m ago`;
    const hours = Math.floor(mins / 60);
    if (hours < 24) return `${hours}h ago`;
    return `${Math.floor(hours / 24)}d ago`;
  }
</script>

<svelte:head>
  <title>Executions - Cloud Instance Scheduler</title>
</svelte:head>

<div class="flex h-screen bg-slate-900">
  <Sidebar />

  <main class="flex-1 overflow-y-auto pt-14 lg:pt-0">
    <div class="p-6">
      <!-- Header -->
      <div class="mb-6 flex justify-between items-start">
        <div>
          <h1 class="text-xl font-semibold text-slate-100">Executions</h1>
          <p class="text-sm text-slate-500 mt-1">
            View execution history across all resources
          </p>
        </div>
        <button
          onclick={() => { currentPage = 0; loadExecutions(); }}
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
            <label for="status-filter" class="block text-xs font-medium text-slate-400 mb-1.5">
              Status
            </label>
            <select
              id="status-filter"
              bind:value={statusFilter}
              class="w-full bg-slate-900 border border-slate-700 text-slate-200 text-sm rounded px-3 py-2 focus:border-emerald-500 focus:ring-1 focus:ring-emerald-500 focus:outline-none"
            >
              <option value="">All</option>
              {#each statusOptions as option}
                <option value={option.value}>{option.label}</option>
              {/each}
            </select>
          </div>

          <div class="w-44">
            <label for="action-filter" class="block text-xs font-medium text-slate-400 mb-1.5">
              Action
            </label>
            <select
              id="action-filter"
              bind:value={actionFilter}
              class="w-full bg-slate-900 border border-slate-700 text-slate-200 text-sm rounded px-3 py-2 focus:border-emerald-500 focus:ring-1 focus:ring-emerald-500 focus:outline-none"
            >
              <option value="">All</option>
              {#each actionOptions as option}
                <option value={option.value}>{option.label}</option>
              {/each}
            </select>
          </div>

          <div class="w-44">
            <label for="hours-filter" class="block text-xs font-medium text-slate-400 mb-1.5">
              Time Period
            </label>
            <select
              id="hours-filter"
              bind:value={hoursFilter}
              class="w-full bg-slate-900 border border-slate-700 text-slate-200 text-sm rounded px-3 py-2 focus:border-emerald-500 focus:ring-1 focus:ring-emerald-500 focus:outline-none"
            >
              {#each hoursOptions as option}
                <option value={option.value}>{option.label}</option>
              {/each}
            </select>
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

      <!-- Executions Table -->
      <div class="bg-slate-800 border border-slate-700 rounded-lg overflow-hidden">
        <div class="overflow-x-auto">
          <table class="min-w-full">
            <thead>
              <tr class="border-b border-slate-700">
                <th class="px-4 py-3 text-left text-xs font-medium text-slate-500 uppercase tracking-wider">
                  Resource
                </th>
                <th class="px-4 py-3 text-left text-xs font-medium text-slate-500 uppercase tracking-wider">
                  Action
                </th>
                <th class="px-4 py-3 text-left text-xs font-medium text-slate-500 uppercase tracking-wider">
                  Status
                </th>
                <th class="px-4 py-3 text-left text-xs font-medium text-slate-500 uppercase tracking-wider">
                  Error
                </th>
                <th class="px-4 py-3 text-left text-xs font-medium text-slate-500 uppercase tracking-wider">
                  Time
                </th>
              </tr>
            </thead>
            <tbody class="divide-y divide-slate-700/50">
              {#if loading}
                {#each Array(5) as _}
                  <tr>
                    {#each Array(5) as _}
                      <td class="px-4 py-3">
                        <div class="h-4 bg-slate-700 rounded animate-pulse"></div>
                      </td>
                    {/each}
                  </tr>
                {/each}
              {:else if executions.length === 0}
                <tr>
                  <td colspan="5" class="px-4 py-12 text-center">
                    <svg class="w-8 h-8 text-slate-600 mx-auto mb-3" fill="none" viewBox="0 0 24 24" stroke="currentColor">
                      <path stroke-linecap="round" stroke-linejoin="round" stroke-width="1.5" d="M12 8v4l3 3m6-3a9 9 0 11-18 0 9 9 0 0118 0z" />
                    </svg>
                    <p class="text-sm text-slate-500">No executions found</p>
                    <p class="text-xs text-slate-600 mt-1">Try adjusting your filters</p>
                  </td>
                </tr>
              {:else}
                {#each executions as execution}
                  <tr
                    class="hover:bg-slate-700/50 cursor-pointer transition-colors"
                    onclick={() => handleRowClick(execution)}
                    onkeypress={(e) => e.key === 'Enter' && handleRowClick(execution)}
                    tabindex="0"
                    role="button"
                  >
                    <td class="px-4 py-3">
                      <span class="text-sm font-medium text-slate-200">
                        {getResourceName(execution.resource_id)}
                      </span>
                    </td>
                    <td class="px-4 py-3">
                      <span class="text-xs px-1.5 py-0.5 rounded font-mono {execution.action === 'START' ? 'bg-emerald-900/50 text-emerald-400' : 'bg-amber-900/50 text-amber-400'}">
                        {execution.action}
                      </span>
                    </td>
                    <td class="px-4 py-3">
                      {#if execution.status === 'pending'}
                        <span class="inline-flex items-center gap-1.5 text-xs font-medium text-amber-400">
                          <svg class="w-3 h-3 animate-spin" fill="none" viewBox="0 0 24 24">
                            <circle class="opacity-25" cx="12" cy="12" r="10" stroke="currentColor" stroke-width="4"></circle>
                            <path class="opacity-75" fill="currentColor" d="M4 12a8 8 0 018-8V0C5.373 0 0 5.373 0 12h4zm2 5.291A7.962 7.962 0 014 12H0c0 3.042 1.135 5.824 3 7.938l3-2.647z"></path>
                          </svg>
                          IN PROGRESS
                        </span>
                      {:else}
                        <span class="inline-flex items-center gap-1.5 text-xs font-medium {execution.success ? 'text-emerald-400' : 'text-red-400'}">
                          <span class="w-1.5 h-1.5 rounded-full {execution.success ? 'bg-emerald-500' : 'bg-red-500'}"></span>
                          {execution.success ? 'OK' : 'FAILED'}
                        </span>
                      {/if}
                    </td>
                    <td class="px-4 py-3">
                      {#if execution.error_message}
                        <p class="text-xs text-red-400/80 truncate max-w-xs" title={execution.error_message}>
                          {execution.error_message}
                        </p>
                      {:else}
                        <span class="text-xs text-slate-600">—</span>
                      {/if}
                    </td>
                    <td class="px-4 py-3 text-sm text-slate-500 whitespace-nowrap" title={new Date(execution.executed_at).toLocaleString()}>
                      {timeAgo(execution.executed_at)}
                    </td>
                  </tr>
                {/each}
              {/if}
            </tbody>
          </table>
        </div>
      </div>

      <!-- Footer: Count + Pagination -->
      {#if !loading}
        <div class="mt-3 flex items-center justify-between">
          <p class="text-xs text-slate-500">
            {#if totalCount > 0}
              Showing <span class="font-mono text-slate-400">{currentPage * PAGE_SIZE + 1}–{Math.min((currentPage + 1) * PAGE_SIZE, totalCount)}</span> of <span class="font-mono text-slate-400">{totalCount}</span> execution{totalCount !== 1 ? 's' : ''}
            {:else}
              No executions
            {/if}
          </p>

          {#if totalPages > 1}
            <div class="flex items-center gap-3">
              <button
                onclick={() => loadPage(currentPage - 1)}
                disabled={currentPage === 0 || loading}
                class="px-3 py-1.5 text-xs font-medium rounded border transition-colors
                  {currentPage === 0
                    ? 'text-slate-600 border-slate-700 cursor-not-allowed'
                    : 'text-slate-300 border-slate-600 hover:bg-slate-700 hover:text-slate-200'}"
              >
                Previous
              </button>
              <span class="text-xs text-slate-500">
                Page {currentPage + 1} of {totalPages}
              </span>
              <button
                onclick={() => loadPage(currentPage + 1)}
                disabled={currentPage >= totalPages - 1 || loading}
                class="px-3 py-1.5 text-xs font-medium rounded border transition-colors
                  {currentPage >= totalPages - 1
                    ? 'text-slate-600 border-slate-700 cursor-not-allowed'
                    : 'text-slate-300 border-slate-600 hover:bg-slate-700 hover:text-slate-200'}"
              >
                Next
              </button>
            </div>
          {/if}
        </div>
      {/if}
    </div>
  </main>
</div>
