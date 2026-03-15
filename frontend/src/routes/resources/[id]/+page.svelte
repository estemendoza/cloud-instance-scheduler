<script lang="ts">
  import { onMount } from 'svelte';
  import { page } from '$app/stores';
  import { goto } from '$app/navigation';
  import Sidebar from '$lib/components/layout/Sidebar.svelte';
  import { resourcesAPI } from '$lib/api/endpoints/resources';
  import { savingsAPI } from '$lib/api/endpoints/savings';
  import { executionsAPI } from '$lib/api/endpoints/executions';
  import { overridesAPI } from '$lib/api/endpoints/overrides';
  import { authStore } from '$lib/stores/auth';
  import type { Resource } from '$lib/types/resource';
  import type { ResourceSavings } from '$lib/types/savings';
  import type { Execution } from '$lib/types/execution';
  import type { Override } from '$lib/types/override';

  let loading = true;
  let error = '';

  let resource: Resource | null = null;
  let savings: ResourceSavings | null = null;
  let timeline: Execution[] = [];
  let overrides: Override[] = [];

  // Override form state
  let showOverrideForm = false;
  let overrideDesiredState: 'RUNNING' | 'STOPPED' = 'RUNNING';
  let overrideExpiresAt = '';
  let overrideReason = '';
  let overrideSubmitting = false;
  let overrideError = '';

  $: canManageOverrides = $authStore.user?.role === 'admin' || $authStore.user?.role === 'operator';

  const PAGE_SIZE = 10;
  let currentPage = 0;
  let hasMore = true;
  let loadingMore = false;
  let totalExecutions = 0;

  $: resourceId = $page.params.id;

  onMount(async () => {
    await loadResourceData();
  });

  async function loadResourceData() {
    loading = true;
    error = '';

    try {
      const [resourceData, savingsData, timelineData, countData, overridesData] = await Promise.all([
        resourcesAPI.get(resourceId),
        savingsAPI.getResourceSavings(resourceId).catch(() => null),
        executionsAPI.getResourceTimeline(resourceId, PAGE_SIZE, 0),
        executionsAPI.getResourceTimelineCount(resourceId).catch(() => ({ total: 0 })),
        overridesAPI.list(resourceId).catch(() => [])
      ]);

      resource = resourceData;
      savings = savingsData;
      timeline = timelineData;
      totalExecutions = countData.total;
      overrides = overridesData;
      currentPage = 0;
      hasMore = timelineData.length === PAGE_SIZE;
    } catch (err: any) {
      error = err.message || 'Failed to load resource data';
      if (err.status === 404) {
        error = 'Resource not found';
      }
    } finally {
      loading = false;
    }
  }

  function getStateClasses(state: string): string {
    switch (state?.toLowerCase()) {
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

  function getExecutionStatusClasses(status: string): string {
    switch (status?.toLowerCase()) {
      case 'success':
        return 'bg-emerald-500';
      case 'failure':
        return 'bg-red-500';
      case 'pending':
        return 'bg-amber-500';
      default:
        return 'bg-slate-500';
    }
  }

  function formatCurrency(amount: number, currency: string = 'USD'): string {
    return new Intl.NumberFormat('en-US', {
      style: 'currency',
      currency
    }).format(amount);
  }

  async function loadTimelinePage(page: number) {
    loadingMore = true;
    try {
      const data = await executionsAPI.getResourceTimeline(resourceId, PAGE_SIZE, page * PAGE_SIZE);
      timeline = data;
      currentPage = page;
      hasMore = data.length === PAGE_SIZE;
    } catch (err) {
      // Keep existing data on error
    } finally {
      loadingMore = false;
    }
  }

  async function createOverride() {
    if (!overrideExpiresAt) return;
    overrideSubmitting = true;
    overrideError = '';
    try {
      await overridesAPI.create({
        resource_id: resourceId,
        desired_state: overrideDesiredState,
        expires_at: new Date(overrideExpiresAt).toISOString(),
        reason: overrideReason || undefined
      });
      overrides = await overridesAPI.list(resourceId);
      showOverrideForm = false;
      overrideDesiredState = 'RUNNING';
      overrideExpiresAt = '';
      overrideReason = '';
    } catch (err: any) {
      overrideError = err.message || 'Failed to create override';
    } finally {
      overrideSubmitting = false;
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

  function goBack() {
    goto('/resources');
  }
</script>

<svelte:head>
  <title>{resource?.name || 'Resource'} - Cloud Instance Scheduler</title>
</svelte:head>

<div class="flex h-screen bg-slate-900">
  <Sidebar />

  <main class="flex-1 overflow-y-auto pt-14 lg:pt-0">
    <div class="p-6">
      <!-- Back Button -->
      <button
        on:click={goBack}
        class="flex items-center gap-2 text-slate-400 hover:text-slate-200 mb-6 text-sm transition-colors"
      >
        <svg class="w-4 h-4" fill="none" viewBox="0 0 24 24" stroke="currentColor">
          <path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M10 19l-7-7m0 0l7-7m-7 7h18" />
        </svg>
        Back to Resources
      </button>

      {#if error}
        <div class="mb-4 p-4 bg-red-900/30 border border-red-800 rounded-lg">
          <p class="text-red-400">{error}</p>
          <button
            on:click={goBack}
            class="mt-3 px-4 py-2 text-sm bg-slate-700 hover:bg-slate-600 text-slate-200 rounded transition-colors"
          >
            Return to Resources
          </button>
        </div>
      {:else if loading}
        <div class="space-y-6">
          <div class="h-24 bg-slate-800 rounded-lg animate-pulse"></div>
          <div class="grid grid-cols-1 lg:grid-cols-3 gap-6">
            <div class="lg:col-span-2 space-y-6">
              <div class="h-48 bg-slate-800 rounded-lg animate-pulse"></div>
              <div class="h-64 bg-slate-800 rounded-lg animate-pulse"></div>
            </div>
            <div class="h-64 bg-slate-800 rounded-lg animate-pulse"></div>
          </div>
        </div>
      {:else if resource}
        <!-- Header -->
        <div class="mb-6 flex justify-between items-start">
          <div>
            <div class="flex items-center gap-3 mb-1">
              {#if resource.provider_type}
                <span
                  class="inline-flex items-center justify-center px-1.5 h-5 text-[10px] font-bold rounded border {getProviderBadgeClasses(resource.provider_type)}"
                  title={getProviderLabel(resource.provider_type)}
                >
                  {getProviderLabel(resource.provider_type)}
                </span>
              {/if}
              <h1 class="text-xl font-semibold text-slate-100">
                {resource.name || resource.provider_resource_id}
              </h1>
              <span class="inline-flex px-2 py-0.5 text-xs font-medium rounded border {getStateClasses(resource.state)}">
                {resource.state}
              </span>
            </div>
            <p class="text-sm text-slate-500 font-mono">{resource.provider_resource_id}</p>
          </div>
          <button
            on:click={loadResourceData}
            class="px-3 py-1.5 text-sm text-slate-400 hover:text-slate-200 bg-slate-800 hover:bg-slate-700 border border-slate-700 rounded transition-colors"
          >
            Refresh
          </button>
        </div>

        <div class="grid grid-cols-1 lg:grid-cols-3 gap-6">
          <!-- Resource Info -->
          <div class="lg:col-span-2 space-y-6">
            <div class="bg-slate-800 border border-slate-700 rounded-lg p-5">
              <h2 class="text-sm font-medium text-slate-300 uppercase tracking-wider mb-4">Resource Information</h2>
              <dl class="grid grid-cols-2 gap-4">
                <div>
                  <dt class="text-xs text-slate-500 uppercase tracking-wider">Region</dt>
                  <dd class="mt-1 text-sm text-slate-200 font-mono">{resource.region}</dd>
                </div>
                <div>
                  <dt class="text-xs text-slate-500 uppercase tracking-wider">Instance Type</dt>
                  <dd class="mt-1 text-sm text-slate-200 font-mono">{resource.instance_type || '—'}</dd>
                </div>
                <div>
                  <dt class="text-xs text-slate-500 uppercase tracking-wider">Resource Type</dt>
                  <dd class="mt-1 text-sm text-slate-200">{resource.resource_type}</dd>
                </div>
                <div>
                  <dt class="text-xs text-slate-500 uppercase tracking-wider">Last Seen</dt>
                  <dd class="mt-1 text-sm text-slate-200">
                    {new Date(resource.last_seen_at).toLocaleString()}
                  </dd>
                </div>
                <div>
                  <dt class="text-xs text-slate-500 uppercase tracking-wider">Created</dt>
                  <dd class="mt-1 text-sm text-slate-200">
                    {new Date(resource.created_at).toLocaleString()}
                  </dd>
                </div>
                <div>
                  <dt class="text-xs text-slate-500 uppercase tracking-wider">Updated</dt>
                  <dd class="mt-1 text-sm text-slate-200">
                    {new Date(resource.updated_at).toLocaleString()}
                  </dd>
                </div>
              </dl>

              {#if resource.tags && Object.keys(resource.tags).length > 0}
                <div class="mt-6 pt-5 border-t border-slate-700">
                  <h4 class="text-xs text-slate-500 uppercase tracking-wider mb-3">Tags</h4>
                  <div class="flex flex-wrap gap-2">
                    {#each Object.entries(resource.tags) as [key, value]}
                      <span class="inline-flex items-center px-2 py-1 rounded text-xs font-mono bg-slate-700 text-slate-300 border border-slate-600">
                        <span class="text-slate-500">{key}:</span>
                        <span class="ml-1">{value}</span>
                      </span>
                    {/each}
                  </div>
                </div>
              {/if}
            </div>

            <!-- Execution Timeline -->
            <div class="bg-slate-800 border border-slate-700 rounded-lg p-5">
              <div class="flex items-center justify-between mb-4">
                <h2 class="text-sm font-medium text-slate-300 uppercase tracking-wider">Execution History</h2>
                {#if totalExecutions > 0}
                  <span class="text-xs text-slate-500">{totalExecutions} total</span>
                {/if}
              </div>
              {#if timeline.length === 0 && currentPage === 0}
                <div class="text-center py-8">
                  <svg class="w-8 h-8 text-slate-600 mx-auto mb-3" fill="none" viewBox="0 0 24 24" stroke="currentColor">
                    <path stroke-linecap="round" stroke-linejoin="round" stroke-width="1.5" d="M12 8v4l3 3m6-3a9 9 0 11-18 0 9 9 0 0118 0z" />
                  </svg>
                  <p class="text-sm text-slate-500">No execution history available</p>
                </div>
              {:else}
                <div class="space-y-1 {loadingMore ? 'opacity-50 pointer-events-none' : ''}">
                  {#each timeline as execution}
                    <div class="flex items-start gap-3 py-3 border-b border-slate-700/50 last:border-0">
                      <div class="mt-1.5">
                        {#if execution.status === 'pending'}
                          <div class="w-2 h-2 rounded-full bg-amber-400 animate-pulse"></div>
                        {:else}
                          <div class="w-2 h-2 rounded-full {execution.success ? 'bg-emerald-500' : 'bg-red-500'}"></div>
                        {/if}
                      </div>
                      <div class="flex-1 min-w-0">
                        <div class="flex items-center gap-2">
                          <span class="text-sm font-medium {execution.status === 'pending' ? 'text-amber-300' : execution.success ? 'text-slate-200' : 'text-red-300'}">
                            {execution.action}
                          </span>
                          {#if execution.status === 'pending'}
                            <span class="text-xs px-1.5 py-0.5 rounded bg-amber-900/30 text-amber-400 inline-flex items-center gap-1">
                              <svg class="w-3 h-3 animate-spin" fill="none" viewBox="0 0 24 24">
                                <circle class="opacity-25" cx="12" cy="12" r="10" stroke="currentColor" stroke-width="4"></circle>
                                <path class="opacity-75" fill="currentColor" d="M4 12a8 8 0 018-8V0C5.373 0 0 5.373 0 12h4zm2 5.291A7.962 7.962 0 014 12H0c0 3.042 1.135 5.824 3 7.938l3-2.647z"></path>
                              </svg>
                              IN PROGRESS
                            </span>
                          {:else}
                            <span class="text-xs px-1.5 py-0.5 rounded {execution.success ? 'bg-emerald-900/30 text-emerald-400' : 'bg-red-900/30 text-red-400'}">
                              {execution.success ? 'OK' : 'FAILED'}
                            </span>
                          {/if}
                          <span class="text-xs text-slate-500 font-mono ml-auto shrink-0">
                            {new Date(execution.executed_at).toLocaleString()}
                          </span>
                        </div>
                        {#if execution.error_message}
                          <p class="text-xs text-red-400/80 mt-1.5 whitespace-pre-wrap break-words bg-red-900/10 border border-red-900/30 rounded p-2">
                            {execution.error_message}
                          </p>
                        {/if}
                      </div>
                    </div>
                  {/each}
                </div>

                <!-- Pagination Controls -->
                {#if currentPage > 0 || hasMore}
                  <div class="flex items-center justify-between pt-4 mt-4 border-t border-slate-700">
                    <button
                      on:click={() => loadTimelinePage(currentPage - 1)}
                      disabled={currentPage === 0 || loadingMore}
                      class="px-3 py-1.5 text-xs font-medium rounded border transition-colors
                        {currentPage === 0
                          ? 'text-slate-600 border-slate-700 cursor-not-allowed'
                          : 'text-slate-300 border-slate-600 hover:bg-slate-700 hover:text-slate-200'}"
                    >
                      Previous
                    </button>
                    <span class="text-xs text-slate-500">
                      Page {currentPage + 1}{#if totalExecutions > 0} of {Math.ceil(totalExecutions / PAGE_SIZE)}{/if}
                    </span>
                    <button
                      on:click={() => loadTimelinePage(currentPage + 1)}
                      disabled={!hasMore || loadingMore}
                      class="px-3 py-1.5 text-xs font-medium rounded border transition-colors
                        {!hasMore
                          ? 'text-slate-600 border-slate-700 cursor-not-allowed'
                          : 'text-slate-300 border-slate-600 hover:bg-slate-700 hover:text-slate-200'}"
                    >
                      Next
                    </button>
                  </div>
                {/if}
              {/if}
            </div>
          </div>

          <!-- Savings Sidebar -->
          <div class="space-y-6">
            <div class="bg-slate-800 border border-slate-700 rounded-lg p-5">
              <h2 class="text-sm font-medium text-slate-300 uppercase tracking-wider mb-4">Projected Savings</h2>
              {#if savings}
                <div class="space-y-4">
                  <div class="text-center pb-4 border-b border-slate-700">
                    <p class="text-3xl font-semibold text-emerald-400 font-mono">
                      {formatCurrency(savings.monthly_savings, savings.currency)}
                    </p>
                    <p class="text-xs text-slate-500 mt-1">Est. Monthly Savings</p>
                  </div>

                  <dl class="space-y-3">
                    <div class="flex justify-between items-center py-2 border-b border-slate-700/50">
                      <dt class="text-sm text-slate-400">Est. Annual</dt>
                      <dd class="text-sm font-mono text-emerald-400">
                        {formatCurrency(savings.annual_savings, savings.currency)}
                      </dd>
                    </div>
                    <div class="flex justify-between items-center py-2 border-b border-slate-700/50">
                      <dt class="text-sm text-slate-400">Hourly Rate</dt>
                      <dd class="text-sm font-mono text-slate-200">
                        {formatCurrency(savings.hourly_rate, savings.currency)}/hr
                      </dd>
                    </div>
                    <div class="flex justify-between items-center py-2 border-b border-slate-700/50">
                      <dt class="text-sm text-slate-400">Stopped Hours/Week</dt>
                      <dd class="text-sm font-mono text-slate-200">
                        {savings.stopped_hours_per_week.toFixed(1)}h
                      </dd>
                    </div>
                    {#if savings.policy_name}
                      <div class="flex justify-between items-center py-2">
                        <dt class="text-sm text-slate-400">Policy</dt>
                        <dd class="text-sm text-slate-200">
                          {savings.policy_name}
                        </dd>
                      </div>
                    {/if}
                  </dl>

                  <p class="text-xs text-slate-500 pt-3 border-t border-slate-700">
                    Based on scheduled downtime. Actual savings depend on policy execution.
                  </p>
                  {#if savings.note}
                    <p class="text-xs text-slate-500 italic">
                      {savings.note}
                    </p>
                  {/if}
                </div>
              {:else}
                <div class="text-center py-6">
                  <svg class="w-8 h-8 text-slate-600 mx-auto mb-3" fill="none" viewBox="0 0 24 24" stroke="currentColor">
                    <path stroke-linecap="round" stroke-linejoin="round" stroke-width="1.5" d="M12 8c-1.657 0-3 .895-3 2s1.343 2 3 2 3 .895 3 2-1.343 2-3 2m0-8c1.11 0 2.08.402 2.599 1M12 8V7m0 1v8m0 0v1m0-1c-1.11 0-2.08-.402-2.599-1M21 12a9 9 0 11-18 0 9 9 0 0118 0z" />
                  </svg>
                  <p class="text-sm text-slate-500">No savings data available</p>
                  <p class="text-xs text-slate-600 mt-1">Pricing info may not be configured</p>
                </div>
              {/if}
            </div>

            <!-- Active Overrides -->
            <div class="bg-slate-800 border border-slate-700 rounded-lg p-5">
              <div class="flex items-center justify-between mb-4">
                <h2 class="text-sm font-medium text-slate-300 uppercase tracking-wider">Active Overrides</h2>
                {#if canManageOverrides && !showOverrideForm}
                  <button
                    on:click={() => showOverrideForm = true}
                    class="text-xs text-emerald-400 hover:text-emerald-300 transition-colors"
                  >
                    + Create
                  </button>
                {/if}
              </div>

              {#if showOverrideForm}
                <div class="mb-4 p-3 bg-slate-900 border border-slate-700 rounded-lg space-y-3">
                  <div>
                    <label for="override-state" class="block text-xs font-medium text-slate-400 mb-1">Desired State</label>
                    <select
                      id="override-state"
                      bind:value={overrideDesiredState}
                      class="w-full bg-slate-800 border border-slate-700 text-slate-200 text-sm rounded px-3 py-2 focus:border-emerald-500 focus:ring-1 focus:ring-emerald-500 focus:outline-none"
                    >
                      <option value="RUNNING">RUNNING</option>
                      <option value="STOPPED">STOPPED</option>
                    </select>
                  </div>
                  <div>
                    <label for="override-expires" class="block text-xs font-medium text-slate-400 mb-1">Expires At</label>
                    <input
                      id="override-expires"
                      type="datetime-local"
                      bind:value={overrideExpiresAt}
                      class="w-full bg-slate-800 border border-slate-700 text-slate-200 text-sm rounded px-3 py-2 focus:border-emerald-500 focus:ring-1 focus:ring-emerald-500 focus:outline-none"
                    />
                  </div>
                  <div>
                    <label for="override-reason" class="block text-xs font-medium text-slate-400 mb-1">Reason (optional)</label>
                    <input
                      id="override-reason"
                      type="text"
                      bind:value={overrideReason}
                      placeholder="e.g., Emergency maintenance"
                      class="w-full bg-slate-800 border border-slate-700 text-slate-200 text-sm rounded px-3 py-2 placeholder-slate-500 focus:border-emerald-500 focus:ring-1 focus:ring-emerald-500 focus:outline-none"
                    />
                  </div>
                  {#if overrideError}
                    <p class="text-xs text-red-400">{overrideError}</p>
                  {/if}
                  <div class="flex gap-2">
                    <button
                      on:click={createOverride}
                      disabled={overrideSubmitting || !overrideExpiresAt}
                      class="flex-1 px-3 py-1.5 text-sm font-medium bg-emerald-600 hover:bg-emerald-500 text-white rounded transition-colors disabled:opacity-50"
                    >
                      {overrideSubmitting ? 'Creating...' : 'Create'}
                    </button>
                    <button
                      on:click={() => { showOverrideForm = false; overrideError = ''; }}
                      class="px-3 py-1.5 text-sm text-slate-400 hover:text-slate-200 bg-slate-700 hover:bg-slate-600 rounded transition-colors"
                    >
                      Cancel
                    </button>
                  </div>
                </div>
              {/if}

              {#if overrides.length === 0}
                <div class="text-center py-6">
                  <svg class="w-8 h-8 text-slate-600 mx-auto mb-3" fill="none" viewBox="0 0 24 24" stroke="currentColor">
                    <path stroke-linecap="round" stroke-linejoin="round" stroke-width="1.5" d="M9 12l2 2 4-4m5.618-4.016A11.955 11.955 0 0112 2.944a11.955 11.955 0 01-8.618 3.04A12.02 12.02 0 003 9c0 5.591 3.824 10.29 9 11.622 5.176-1.332 9-6.03 9-11.622 0-1.042-.133-2.052-.382-3.016z" />
                  </svg>
                  <p class="text-sm text-slate-500">No active overrides</p>
                </div>
              {:else}
                <div class="space-y-3">
                  {#each overrides as override}
                    <div class="p-3 bg-slate-900 border border-slate-700 rounded-lg">
                      <div class="flex items-center justify-between mb-2">
                        <span class="inline-flex px-2 py-0.5 text-xs font-medium rounded border {override.desired_state === 'RUNNING'
                          ? 'bg-emerald-900/50 text-emerald-400 border-emerald-800'
                          : 'bg-slate-700 text-slate-400 border-slate-600'}">
                          {override.desired_state}
                        </span>
                        {#if canManageOverrides}
                          <button
                            on:click={() => cancelOverride(override.id)}
                            class="text-xs text-red-400 hover:text-red-300 transition-colors"
                          >
                            Cancel
                          </button>
                        {/if}
                      </div>
                      <div class="text-xs text-slate-500 space-y-1">
                        <p>Expires: <span class="text-slate-400">{formatRelativeTime(override.expires_at)}</span></p>
                        {#if override.reason}
                          <p>Reason: <span class="text-slate-400">{override.reason}</span></p>
                        {/if}
                        <p>Created: <span class="text-slate-400">{new Date(override.created_at).toLocaleString()}</span></p>
                      </div>
                    </div>
                  {/each}
                </div>
              {/if}
            </div>
          </div>
        </div>
      {/if}
    </div>
  </main>
</div>
