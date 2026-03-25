<script lang="ts">
  import { onMount } from 'svelte';
  import Sidebar from '$lib/components/layout/Sidebar.svelte';
  import { authStore } from '$lib/stores/auth';
  import { savingsAPI } from '$lib/api/endpoints/savings';
  import { executionsAPI } from '$lib/api/endpoints/executions';
  import { resourcesAPI } from '$lib/api/endpoints/resources';
  import { cloudAccountsAPI } from '$lib/api/endpoints/cloudAccounts';
  import { policiesAPI } from '$lib/api/endpoints/policies';
  import type { OrganizationSavings } from '$lib/types/savings';
  import type { Execution, ExecutionSummary } from '$lib/types/execution';
  import type { Resource } from '$lib/types/resource';
  import type { CloudAccount } from '$lib/types/cloudAccount';
  import type { Policy } from '$lib/types/policy';

  let loading = $state(true);
  let error = $state('');

  let savings = $state<OrganizationSavings | null>(null);
  let summary = $state<ExecutionSummary | null>(null);
  let resources = $state<Resource[]>([]);
  let recentFailures = $state<Execution[]>([]);
  let cloudAccounts = $state<CloudAccount[]>([]);
  let policies = $state<Policy[]>([]);

  onMount(async () => {
    await loadDashboardData();
  });

  async function loadDashboardData() {
    loading = true;
    error = '';

    try {
      // Fetch all data in parallel
      const [savingsData, summaryData, resourcesData, failuresData, accountsData, policiesData] = await Promise.all([
        savingsAPI.getOrganizationSavings().catch(() => null),
        executionsAPI.getSummary().catch(() => null),
        resourcesAPI.list({ page_size: 100 }),
        executionsAPI.list({ success: false, hours: 24, limit: 5 }).catch(() => []),
        cloudAccountsAPI.list().catch(() => []),
        policiesAPI.list().catch(() => [])
      ]);

      savings = savingsData;
      summary = summaryData;
      resources = resourcesData.items;
      recentFailures = failuresData;
      cloudAccounts = accountsData;
      policies = policiesData;
    } catch (err: any) {
      error = err.message || 'Failed to load dashboard data';
    } finally {
      loading = false;
    }
  }

  function formatCurrency(amount: number, currency: string = 'USD'): string {
    return new Intl.NumberFormat('en-US', {
      style: 'currency',
      currency,
      minimumFractionDigits: 0,
      maximumFractionDigits: 0
    }).format(amount);
  }

  function formatPercent(rate: number): string {
    return `${(rate * 100).toFixed(1)}%`;
  }

  let stepAccount = $derived(cloudAccounts.length > 0);
  let stepResources = $derived(resources.length > 0);
  let stepPolicies = $derived(policies.length > 0);
  let stepSavings = $derived(savings !== null && savings.total_monthly_savings > 0);
  let steps = $derived([
    { done: stepAccount, label: 'Connect a cloud account (AWS, Azure, or GCP)', href: '/settings' },
    { done: stepResources, label: 'Sync and discover your instances', href: '/settings' },
    { done: stepPolicies, label: 'Create policies to schedule start/stop', href: '/policies/new' },
    { done: stepSavings, label: 'Watch the savings add up', href: '/calculator' },
  ]);
  let hasNoData = $derived(!stepAccount || !stepResources || !stepPolicies);
  let nextStep = $derived(steps.findIndex(s => !s.done));
  let runningResources = $derived(resources.filter((r) => r.state === 'RUNNING').length);
  let stoppedResources = $derived(resources.filter((r) => r.state === 'STOPPED').length);
  let resourceMap = $derived(new Map(resources.map(r => [r.id, r])));

  function getResourceName(resourceId: string): string {
    const r = resourceMap.get(resourceId);
    return r?.name || r?.provider_resource_id || 'Unknown resource';
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
  <title>Dashboard - Cloud Instance Scheduler</title>
</svelte:head>

<div class="flex h-screen bg-slate-900">
  <Sidebar />

  <main class="flex-1 overflow-y-auto pt-14 lg:pt-0">
    <div class="p-6">
      <!-- Header -->
      <div class="mb-6 flex justify-between items-start">
        <div>
          <h1 class="text-xl font-semibold text-slate-100">Dashboard</h1>
          <p class="text-sm text-slate-500 mt-1">
            Welcome back, {$authStore.user?.full_name || $authStore.user?.email?.split('@')[0]}
          </p>
        </div>
        <button
          onclick={loadDashboardData}
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

      {#if !loading && hasNoData}
        <!-- Empty State -->
        <div class="flex flex-col items-center justify-center py-20">
          <div class="w-16 h-16 bg-slate-800 border border-slate-700 rounded-2xl flex items-center justify-center mb-6">
            <svg class="w-8 h-8 text-emerald-500" fill="none" viewBox="0 0 24 24" stroke="currentColor">
              <path stroke-linecap="round" stroke-linejoin="round" stroke-width="1.5" d="M3 15a4 4 0 004 4h9a5 5 0 10-.1-9.999 5.002 5.002 0 10-9.78 2.096A4.001 4.001 0 003 15z" />
            </svg>
          </div>
          <h2 class="text-lg font-semibold text-slate-100 mb-2">Welcome to Cloud Instance Scheduler</h2>
          <p class="text-sm text-slate-400 text-center max-w-md mb-8">
            Connect your first cloud account to start discovering instances and saving on compute costs.
          </p>

          <div class="w-full max-w-sm space-y-3">
            {#each steps as step, i}
              <div class="flex items-center gap-3 text-sm">
                {#if step.done}
                  <div class="w-7 h-7 rounded-full bg-emerald-900/50 border border-emerald-800 flex items-center justify-center flex-shrink-0">
                    <svg class="w-3.5 h-3.5 text-emerald-400" fill="none" viewBox="0 0 24 24" stroke="currentColor" stroke-width="3">
                      <path stroke-linecap="round" stroke-linejoin="round" d="M5 13l4 4L19 7" />
                    </svg>
                  </div>
                  <span class="text-slate-400 line-through">{step.label}</span>
                {:else}
                  <div class="w-7 h-7 rounded-full {i === nextStep ? 'bg-emerald-900/50 border-emerald-800' : 'bg-slate-800 border-slate-700'} border flex items-center justify-center flex-shrink-0">
                    <span class="text-xs font-semibold {i === nextStep ? 'text-emerald-400' : 'text-slate-500'}">{i + 1}</span>
                  </div>
                  <span class="{i === nextStep ? 'text-slate-300' : 'text-slate-500'}">{step.label}</span>
                {/if}
              </div>
            {/each}
          </div>

          {#if nextStep >= 0}
            <a
              href={steps[nextStep].href}
              class="mt-8 inline-flex items-center gap-2 px-5 py-2.5 bg-emerald-600 hover:bg-emerald-500 text-white text-sm font-medium rounded-lg transition-colors"
            >
              <svg class="w-4 h-4" fill="none" viewBox="0 0 24 24" stroke="currentColor">
                <path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M13 7l5 5m0 0l-5 5m5-5H6" />
              </svg>
              {#if nextStep === 0}
                Connect Cloud Account
              {:else if nextStep === 1}
                Sync Resources
              {:else if nextStep === 2}
                Create a Policy
              {:else}
                Open Calculator
              {/if}
            </a>
          {/if}
        </div>
      {:else}
      <!-- KPI Cards -->
      <div class="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-4 gap-4 mb-6">
        <!-- Savings Card -->
        <div class="bg-slate-800 border border-slate-700 rounded-lg p-4">
          <div class="flex items-center justify-between mb-2">
            <span class="text-xs font-medium text-slate-500 uppercase tracking-wider">Est. Monthly Savings</span>
            <svg class="w-4 h-4 text-emerald-500" fill="none" viewBox="0 0 24 24" stroke="currentColor">
              <path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M12 8c-1.657 0-3 .895-3 2s1.343 2 3 2 3 .895 3 2-1.343 2-3 2m0-8c1.11 0 2.08.402 2.599 1M12 8V7m0 1v8m0 0v1m0-1c-1.11 0-2.08-.402-2.599-1M21 12a9 9 0 11-18 0 9 9 0 0118 0z" />
            </svg>
          </div>
          {#if loading}
            <div class="h-8 bg-slate-700 rounded animate-pulse mb-1"></div>
          {:else}
            <div class="text-2xl font-semibold text-emerald-400 font-mono">
              {savings ? formatCurrency(savings.total_monthly_savings, savings.currency) : '$0'}
            </div>
          {/if}
          <p class="text-xs text-slate-500 mt-1">
            {savings ? `Projected from ${savings.resources_with_savings} scheduled resources` : 'No data'}
          </p>
        </div>

        <!-- Resources Card -->
        <div class="bg-slate-800 border border-slate-700 rounded-lg p-4">
          <div class="flex items-center justify-between mb-2">
            <span class="text-xs font-medium text-slate-500 uppercase tracking-wider">Resources</span>
            <svg class="w-4 h-4 text-slate-400" fill="none" viewBox="0 0 24 24" stroke="currentColor">
              <path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M5 12h14M5 12a2 2 0 01-2-2V6a2 2 0 012-2h14a2 2 0 012 2v4a2 2 0 01-2 2M5 12a2 2 0 00-2 2v4a2 2 0 002 2h14a2 2 0 002-2v-4a2 2 0 00-2-2" />
            </svg>
          </div>
          {#if loading}
            <div class="h-8 bg-slate-700 rounded animate-pulse mb-1"></div>
          {:else}
            <div class="text-2xl font-semibold text-slate-100 font-mono">{resources.length}</div>
          {/if}
          <p class="text-xs text-slate-500 mt-1">
            <span class="text-emerald-500">{runningResources} running</span> · <span class="text-slate-400">{stoppedResources} stopped</span>
          </p>
        </div>

        <!-- Success Rate Card -->
        <div class="bg-slate-800 border border-slate-700 rounded-lg p-4">
          <div class="flex items-center justify-between mb-2">
            <span class="text-xs font-medium text-slate-500 uppercase tracking-wider">Success Rate (24h)</span>
            <svg class="w-4 h-4 {summary && (summary.last_24_hours.success_rate ?? 0) >= 0.95 ? 'text-emerald-500' : (summary?.last_24_hours.success_rate ?? 0) >= 0.8 ? 'text-amber-500' : 'text-red-500'}" fill="none" viewBox="0 0 24 24" stroke="currentColor">
              <path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M9 12l2 2 4-4m6 2a9 9 0 11-18 0 9 9 0 0118 0z" />
            </svg>
          </div>
          {#if loading}
            <div class="h-8 bg-slate-700 rounded animate-pulse mb-1"></div>
          {:else}
            <div class="text-2xl font-semibold font-mono {summary && (summary.last_24_hours.success_rate ?? 0) >= 0.95 ? 'text-emerald-400' : (summary?.last_24_hours.success_rate ?? 0) >= 0.8 ? 'text-amber-400' : 'text-red-400'}">
              {summary ? formatPercent(summary.last_24_hours.success_rate) : '—'}
            </div>
          {/if}
          <p class="text-xs text-slate-500 mt-1">
            {summary ? `${summary.last_24_hours.total_executions} executions` : 'No data'}
          </p>
        </div>

        <!-- Failures Card -->
        <div class="bg-slate-800 border border-slate-700 rounded-lg p-4">
          <div class="flex items-center justify-between mb-2">
            <span class="text-xs font-medium text-slate-500 uppercase tracking-wider">Recent Failures</span>
            <svg class="w-4 h-4 {summary && summary.recent_failures_count === 0 ? 'text-emerald-500' : 'text-red-500'}" fill="none" viewBox="0 0 24 24" stroke="currentColor">
              <path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M12 8v4m0 4h.01M21 12a9 9 0 11-18 0 9 9 0 0118 0z" />
            </svg>
          </div>
          {#if loading}
            <div class="h-8 bg-slate-700 rounded animate-pulse mb-1"></div>
          {:else}
            <div class="text-2xl font-semibold font-mono {summary && summary.recent_failures_count === 0 ? 'text-emerald-400' : 'text-red-400'}">
              {summary?.recent_failures_count ?? 0}
            </div>
          {/if}
          <p class="text-xs text-slate-500 mt-1">Last 24 hours</p>
        </div>
      </div>

      <!-- Recent Failures -->
      {#if !loading && recentFailures.length > 0}
        <div class="bg-slate-800 border border-red-900/50 rounded-lg p-5 mb-6">
          <h2 class="text-sm font-medium text-red-400 uppercase tracking-wider mb-3">Recent Failures (24h)</h2>
          <div class="space-y-2">
            {#each recentFailures as failure}
              <a
                href="/resources/{failure.resource_id}"
                class="flex items-start gap-3 p-2 bg-slate-900/50 hover:bg-slate-900 border border-slate-700 rounded transition-colors"
              >
                <div class="w-2 h-2 rounded-full bg-red-500 mt-1.5 flex-shrink-0"></div>
                <div class="flex-1 min-w-0">
                  <div class="flex items-center gap-2">
                    <span class="text-sm font-medium text-slate-200 truncate">{getResourceName(failure.resource_id)}</span>
                    <span class="text-xs px-1.5 py-0.5 rounded font-mono {failure.action === 'START' ? 'bg-emerald-900/50 text-emerald-400' : 'bg-amber-900/50 text-amber-400'}">
                      {failure.action}
                    </span>
                    <span class="text-xs text-slate-500 ml-auto flex-shrink-0">{timeAgo(failure.executed_at)}</span>
                  </div>
                  {#if failure.error_message}
                    <p class="text-xs text-red-400/80 mt-1 truncate" title={failure.error_message}>
                      {failure.error_message}
                    </p>
                  {:else}
                    <p class="text-xs text-slate-500 mt-1">Action failed (no error details)</p>
                  {/if}
                </div>
              </a>
            {/each}
          </div>
          {#if summary && summary.recent_failures_count > recentFailures.length}
            <div class="mt-3 pt-3 border-t border-slate-700/50 text-center">
              <a
                href="/executions?success=false"
                class="text-xs text-red-400 hover:text-red-300 transition-colors"
              >
                View all {summary.recent_failures_count} failures &rarr;
              </a>
            </div>
          {/if}
        </div>
      {/if}

      <!-- Quick Actions / Recent Activity -->
      <div class="grid grid-cols-1 lg:grid-cols-2 gap-4">
        <!-- Quick Actions -->
        <div class="bg-slate-800 border border-slate-700 rounded-lg p-5">
          <h2 class="text-sm font-medium text-slate-300 uppercase tracking-wider mb-4">Quick Actions</h2>
          <div class="space-y-2">
            <a
              href="/resources"
              class="flex items-center gap-3 p-3 bg-slate-900/50 hover:bg-slate-900 border border-slate-700 rounded transition-colors group"
            >
              <div class="w-8 h-8 bg-slate-800 rounded flex items-center justify-center">
                <svg class="w-4 h-4 text-slate-400 group-hover:text-emerald-500 transition-colors" fill="none" viewBox="0 0 24 24" stroke="currentColor">
                  <path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M5 12h14M5 12a2 2 0 01-2-2V6a2 2 0 012-2h14a2 2 0 012 2v4a2 2 0 01-2 2M5 12a2 2 0 00-2 2v4a2 2 0 002 2h14a2 2 0 002-2v-4a2 2 0 00-2-2" />
                </svg>
              </div>
              <div>
                <p class="text-sm font-medium text-slate-200">View Resources</p>
                <p class="text-xs text-slate-500">Manage your cloud instances</p>
              </div>
            </a>
            <a
              href="/policies"
              class="flex items-center gap-3 p-3 bg-slate-900/50 hover:bg-slate-900 border border-slate-700 rounded transition-colors group"
            >
              <div class="w-8 h-8 bg-slate-800 rounded flex items-center justify-center">
                <svg class="w-4 h-4 text-slate-400 group-hover:text-emerald-500 transition-colors" fill="none" viewBox="0 0 24 24" stroke="currentColor">
                  <path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M12 8v4l3 3m6-3a9 9 0 11-18 0 9 9 0 0118 0z" />
                </svg>
              </div>
              <div>
                <p class="text-sm font-medium text-slate-200">Configure Policies</p>
                <p class="text-xs text-slate-500">Set up scheduling rules</p>
              </div>
            </a>
          </div>
        </div>

        <!-- Execution Summary -->
        <div class="bg-slate-800 border border-slate-700 rounded-lg p-5">
          <h2 class="text-sm font-medium text-slate-300 uppercase tracking-wider mb-4">Execution Summary</h2>
          {#if loading}
            <div class="space-y-3">
              {#each Array(3) as _}
                <div class="h-5 bg-slate-700 rounded animate-pulse"></div>
              {/each}
            </div>
          {:else if summary}
            <div class="space-y-3">
              <div class="flex justify-between items-center py-2 border-b border-slate-700">
                <span class="text-sm text-slate-400">Last Hour</span>
                <span class="text-sm font-mono text-slate-200">
                  <span class="text-emerald-500">{summary.last_hour.successful}</span>/<span class="text-slate-400">{summary.last_hour.total_executions}</span>
                </span>
              </div>
              <div class="flex justify-between items-center py-2 border-b border-slate-700">
                <span class="text-sm text-slate-400">Last 24 Hours</span>
                <span class="text-sm font-mono text-slate-200">
                  <span class="text-emerald-500">{summary.last_24_hours.successful}</span>/<span class="text-slate-400">{summary.last_24_hours.total_executions}</span>
                </span>
              </div>
              <div class="flex justify-between items-center py-2">
                <span class="text-sm text-slate-400">Last 7 Days</span>
                <span class="text-sm font-mono text-slate-200">
                  <span class="text-emerald-500">{summary.last_7_days.successful}</span>/<span class="text-slate-400">{summary.last_7_days.total_executions}</span>
                </span>
              </div>
              {#if summary.last_execution_at}
                <p class="text-xs text-slate-500 pt-2 border-t border-slate-700">
                  Last execution: <span class="font-mono">{new Date(summary.last_execution_at).toLocaleString()}</span>
                </p>
              {/if}
            </div>
          {:else}
            <div class="text-center py-6">
              <svg class="w-8 h-8 text-slate-600 mx-auto mb-2" fill="none" viewBox="0 0 24 24" stroke="currentColor">
                <path stroke-linecap="round" stroke-linejoin="round" stroke-width="1.5" d="M9 5H7a2 2 0 00-2 2v12a2 2 0 002 2h10a2 2 0 002-2V7a2 2 0 00-2-2h-2M9 5a2 2 0 002 2h2a2 2 0 002-2M9 5a2 2 0 012-2h2a2 2 0 012 2" />
              </svg>
              <p class="text-sm text-slate-500">No execution data available</p>
            </div>
          {/if}
        </div>
      </div>
      {/if}
    </div>
  </main>
</div>
