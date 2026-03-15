<script lang="ts">
  import { onMount } from 'svelte';
  import { goto } from '$app/navigation';
  import { policiesAPI } from '$lib/api/endpoints/policies';
  import { authStore } from '$lib/stores/auth';
  import { notify } from '$lib/utils/toast';
  import Sidebar from '$lib/components/layout/Sidebar.svelte';
  import type { Policy } from '$lib/types/policy';

  let policies: Policy[] = [];
  let loading = true;
  let error = '';
  let togglingId: string | null = null;

  $: isAdmin = $authStore.user?.role === 'admin';

  onMount(async () => {
    await loadPolicies();
  });

  async function loadPolicies() {
    loading = true;
    error = '';
    try {
      policies = await policiesAPI.list();
    } catch (err: any) {
      error = err.message || 'Failed to load policies';
    } finally {
      loading = false;
    }
  }

  async function toggleEnabled(policy: Policy) {
    togglingId = policy.id;
    try {
      await policiesAPI.update(policy.id, { is_enabled: !policy.is_enabled });
      // Update local state
      policies = policies.map(p =>
        p.id === policy.id ? { ...p, is_enabled: !p.is_enabled } : p
      );
      notify.success(`Policy ${!policy.is_enabled ? 'enabled' : 'disabled'}`);
    } catch (err: any) {
      error = err.message || 'Failed to update policy';
      notify.error(error);
    } finally {
      togglingId = null;
    }
  }

  async function deletePolicy(policy: Policy) {
    if (!confirm(`Delete policy "${policy.name}"? This cannot be undone.`)) {
      return;
    }

    try {
      await policiesAPI.delete(policy.id);
      policies = policies.filter(p => p.id !== policy.id);
      notify.success('Policy deleted');
    } catch (err: any) {
      error = err.message || 'Failed to delete policy';
      notify.error(error);
    }
  }

  function formatScheduleSummary(policy: Policy): string {
    if (policy.schedule_type === 'cron') {
      const sched = policy.schedule as { start?: string; stop?: string };
      if (sched.start && sched.stop) {
        return `cron: ${sched.start}`;
      }
      return 'Cron (incomplete)';
    }
    const days = Object.keys(policy.schedule).length;
    if (days === 0) return 'No schedule';
    if (days === 7) return 'Every day';
    if (days === 5 && !(policy.schedule as Record<string, unknown>).saturday && !(policy.schedule as Record<string, unknown>).sunday) {
      return 'Weekdays';
    }
    return `${days} days/week`;
  }

  function getResourceSelectorType(policy: Policy): string {
    if ('tags' in policy.resource_selector) {
      const tagCount = Object.keys(policy.resource_selector.tags).length;
      return `${tagCount} tag${tagCount !== 1 ? 's' : ''}`;
    }
    if ('resource_ids' in policy.resource_selector) {
      const count = policy.resource_selector.resource_ids.length;
      return `${count} resource${count !== 1 ? 's' : ''}`;
    }
    return 'Unknown';
  }
</script>

<svelte:head>
  <title>Policies - Cloud Instance Scheduler</title>
</svelte:head>

<div class="flex h-screen bg-slate-900">
  <Sidebar />

  <main class="flex-1 overflow-auto pt-14 lg:pt-0">
    <div class="p-6">
      <!-- Header -->
      <div class="flex items-center justify-between mb-6">
        <div>
          <h1 class="text-xl font-semibold text-slate-100">Policies</h1>
          <p class="text-sm text-slate-500 mt-1">Manage scheduling policies for your resources</p>
        </div>

        {#if isAdmin}
          <button
            on:click={() => goto('/policies/new')}
            class="px-4 py-2 bg-emerald-600 hover:bg-emerald-500 text-white text-sm font-medium rounded transition-colors"
          >
            Create Policy
          </button>
        {/if}
      </div>

      {#if error}
        <div class="mb-4 p-3 bg-red-900/30 border border-red-800 rounded">
          <p class="text-sm text-red-400">{error}</p>
        </div>
      {/if}

      {#if loading}
        <div class="flex items-center justify-center py-12">
          <div class="animate-spin rounded-full h-8 w-8 border-2 border-slate-700 border-t-emerald-500"></div>
        </div>
      {:else if policies.length === 0}
        <div class="text-center py-12 bg-slate-800 border border-slate-700 rounded-lg">
          <svg class="w-12 h-12 text-slate-600 mx-auto mb-4" fill="none" viewBox="0 0 24 24" stroke="currentColor">
            <path stroke-linecap="round" stroke-linejoin="round" stroke-width="1.5" d="M12 8v4l3 3m6-3a9 9 0 11-18 0 9 9 0 0118 0z" />
          </svg>
          <h3 class="text-slate-300 font-medium mb-1">No policies yet</h3>
          <p class="text-slate-500 text-sm mb-4">Create a policy to start scheduling your resources</p>
          {#if isAdmin}
            <button
              on:click={() => goto('/policies/new')}
              class="px-4 py-2 bg-emerald-600 hover:bg-emerald-500 text-white text-sm font-medium rounded transition-colors"
            >
              Create Policy
            </button>
          {/if}
        </div>
      {:else}
        <!-- Policy Table -->
        <div class="bg-slate-800 border border-slate-700 rounded-lg overflow-hidden">
          <table class="w-full">
            <thead>
              <tr class="border-b border-slate-700">
                <th class="px-4 py-3 text-left text-xs font-medium text-slate-400 uppercase tracking-wider">Name</th>
                <th class="px-4 py-3 text-left text-xs font-medium text-slate-400 uppercase tracking-wider">Schedule</th>
                <th class="px-4 py-3 text-left text-xs font-medium text-slate-400 uppercase tracking-wider">Timezone</th>
                <th class="px-4 py-3 text-left text-xs font-medium text-slate-400 uppercase tracking-wider">Selector</th>
                <th class="px-4 py-3 text-left text-xs font-medium text-slate-400 uppercase tracking-wider">Status</th>
                <th class="px-4 py-3 text-right text-xs font-medium text-slate-400 uppercase tracking-wider">Actions</th>
              </tr>
            </thead>
            <tbody class="divide-y divide-slate-700">
              {#each policies as policy (policy.id)}
                <tr class="hover:bg-slate-750 transition-colors">
                  <td class="px-4 py-3">
                    <div>
                      <div class="text-sm font-medium text-slate-200">{policy.name}</div>
                      {#if policy.description}
                        <div class="text-xs text-slate-500 truncate max-w-xs">{policy.description}</div>
                      {/if}
                    </div>
                  </td>
                  <td class="px-4 py-3">
                    <span class="text-sm text-slate-300 font-mono">{formatScheduleSummary(policy)}</span>
                  </td>
                  <td class="px-4 py-3">
                    <span class="text-sm text-slate-400 font-mono">{policy.timezone}</span>
                  </td>
                  <td class="px-4 py-3">
                    <span class="text-sm text-slate-400">{getResourceSelectorType(policy)}</span>
                  </td>
                  <td class="px-4 py-3">
                    <button
                      on:click={() => toggleEnabled(policy)}
                      disabled={togglingId === policy.id || !isAdmin}
                      class="relative inline-flex h-5 w-9 items-center rounded-full transition-colors {policy.is_enabled ? 'bg-emerald-600' : 'bg-slate-600'} {!isAdmin ? 'opacity-50 cursor-not-allowed' : ''}"
                    >
                      <span
                        class="inline-block h-3.5 w-3.5 transform rounded-full bg-white transition-transform {policy.is_enabled ? 'translate-x-4.5' : 'translate-x-1'}"
                        style="transform: translateX({policy.is_enabled ? '18px' : '2px'})"
                      />
                    </button>
                  </td>
                  <td class="px-4 py-3 text-right">
                    <div class="flex items-center justify-end gap-2">
                      <button
                        on:click={() => goto(`/policies/${policy.id}`)}
                        class="px-2.5 py-1.5 text-xs font-medium text-slate-300 hover:text-white bg-slate-700 hover:bg-slate-600 rounded transition-colors"
                      >
                        {isAdmin ? 'Edit' : 'View'}
                      </button>
                      {#if isAdmin}
                        <button
                          on:click={() => deletePolicy(policy)}
                          class="px-2.5 py-1.5 text-xs font-medium text-red-400 hover:text-red-300 bg-slate-700 hover:bg-red-900/30 rounded transition-colors"
                        >
                          Delete
                        </button>
                      {/if}
                    </div>
                  </td>
                </tr>
              {/each}
            </tbody>
          </table>
        </div>
      {/if}
    </div>
  </main>
</div>
