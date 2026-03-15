<script lang="ts">
  import { onMount } from 'svelte';
  import { goto } from '$app/navigation';
  import { page } from '$app/stores';
  import { policiesAPI } from '$lib/api/endpoints/policies';
  import { authStore } from '$lib/stores/auth';
  import { notify } from '$lib/utils/toast';
  import Sidebar from '$lib/components/layout/Sidebar.svelte';
  import ScheduleGrid from '$lib/components/policy/ScheduleGrid.svelte';
  import CronScheduleInput from '$lib/components/policy/CronScheduleInput.svelte';
  import TimezoneSelect from '$lib/components/policy/TimezoneSelect.svelte';
  import ResourceSelector from '$lib/components/policy/ResourceSelector.svelte';
  import type { Policy, WeeklySchedule, CronSchedule, ResourceSelector as ResourceSelectorType, PolicyUpdate, ScheduleType } from '$lib/types/policy';

  let policy: Policy | null = null;
  let name = '';
  let description = '';
  let timezone = 'UTC';
  let scheduleType: ScheduleType = 'weekly';
  let weeklySchedule: WeeklySchedule = {};
  let cronSchedule: CronSchedule = { start: '', stop: '' };
  let resourceSelector: ResourceSelectorType = { tags: {} };
  let isEnabled = true;

  let loadingPolicy = true;
  let saving = false;
  let error = '';

  $: policyId = $page.params.id;
  $: isAdmin = $authStore.user?.role === 'admin';

  onMount(async () => {
    await loadPolicy();
  });

  async function loadPolicy() {
    loadingPolicy = true;
    error = '';

    try {
      policy = await policiesAPI.get(policyId);

      // Initialize form fields
      name = policy.name;
      description = policy.description || '';
      timezone = policy.timezone;
      scheduleType = policy.schedule_type || 'weekly';
      if (scheduleType === 'cron') {
        cronSchedule = policy.schedule as CronSchedule;
      } else {
        weeklySchedule = policy.schedule as WeeklySchedule;
      }
      resourceSelector = policy.resource_selector;
      isEnabled = policy.is_enabled;
    } catch (err: any) {
      error = err.message || 'Failed to load policy';
    } finally {
      loadingPolicy = false;
    }
  }

  async function handleSubmit() {
    if (!isAdmin) return;

    error = '';

    // Validation
    if (!name.trim()) {
      error = 'Name is required';
      return;
    }

    if (!timezone) {
      error = 'Timezone is required';
      return;
    }

    if (scheduleType === 'weekly' && Object.keys(weeklySchedule).length === 0) {
      error = 'Please define a schedule (select at least one time block)';
      return;
    }

    if (scheduleType === 'cron' && (!cronSchedule.start.trim() || !cronSchedule.stop.trim())) {
      error = 'Both start and stop cron expressions are required';
      return;
    }

    // Check resource selector is valid
    if ('tags' in resourceSelector) {
      if (Object.keys(resourceSelector.tags).length === 0) {
        error = 'Please add at least one tag for resource selection';
        return;
      }
    } else if ('resource_ids' in resourceSelector) {
      if (resourceSelector.resource_ids.length === 0) {
        error = 'Please select at least one resource';
        return;
      }
    }

    saving = true;

    try {
      const schedule = scheduleType === 'weekly' ? weeklySchedule : cronSchedule;
      const update: PolicyUpdate = {
        name: name.trim(),
        description: description.trim() || undefined,
        timezone,
        schedule_type: scheduleType,
        schedule,
        resource_selector: resourceSelector,
        is_enabled: isEnabled
      };

      await policiesAPI.update(policyId, update);
      notify.success('Policy updated successfully');
      goto('/policies');
    } catch (err: any) {
      error = err.message || 'Failed to update policy';
      notify.error(error);
    } finally {
      saving = false;
    }
  }

  function handleScheduleChange(event: CustomEvent<WeeklySchedule>) {
    weeklySchedule = event.detail;
  }

  function handleCronScheduleChange(event: CustomEvent<CronSchedule>) {
    cronSchedule = event.detail;
  }

  function handleTimezoneChange(event: CustomEvent<string>) {
    timezone = event.detail;
  }

  function handleResourceSelectorChange(event: CustomEvent<ResourceSelectorType>) {
    resourceSelector = event.detail;
  }
</script>

<svelte:head>
  <title>{policy ? `Edit ${policy.name}` : 'Policy'} - Cloud Instance Scheduler</title>
</svelte:head>

<div class="flex h-screen bg-slate-900">
  <Sidebar />

  <main class="flex-1 overflow-auto pt-14 lg:pt-0">
    <div class="p-6 max-w-4xl">
      <!-- Header -->
      <div class="mb-6">
        <button
          on:click={() => goto('/policies')}
          class="flex items-center gap-1 text-sm text-slate-400 hover:text-slate-200 mb-2"
        >
          <svg class="w-4 h-4" fill="none" viewBox="0 0 24 24" stroke="currentColor">
            <path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M15 19l-7-7 7-7" />
          </svg>
          Back to Policies
        </button>
        <h1 class="text-xl font-semibold text-slate-100">
          {isAdmin ? 'Edit Policy' : 'View Policy'}
        </h1>
        {#if !isAdmin}
          <p class="text-sm text-slate-500 mt-1">You have view-only access to this policy</p>
        {/if}
      </div>

      {#if loadingPolicy}
        <div class="flex items-center justify-center py-12">
          <div class="animate-spin rounded-full h-8 w-8 border-2 border-slate-700 border-t-emerald-500"></div>
        </div>
      {:else if error && !policy}
        <div class="p-4 bg-red-900/30 border border-red-800 rounded">
          <p class="text-red-400">{error}</p>
          <button
            on:click={() => goto('/policies')}
            class="mt-2 text-sm text-slate-400 hover:text-white"
          >
            Back to Policies
          </button>
        </div>
      {:else}
        {#if error}
          <div class="mb-4 p-3 bg-red-900/30 border border-red-800 rounded">
            <p class="text-sm text-red-400">{error}</p>
          </div>
        {/if}

        <form on:submit|preventDefault={handleSubmit} class="space-y-6">
          <!-- Basic Info Section -->
          <div class="bg-slate-800 border border-slate-700 rounded-lg p-5">
            <h2 class="text-sm font-medium text-slate-300 uppercase tracking-wider mb-4">Basic Information</h2>

            <div class="space-y-4">
              <div>
                <label for="name" class="block text-xs font-medium text-slate-400 uppercase tracking-wider mb-2">
                  Name <span class="text-red-500">*</span>
                </label>
                <input
                  id="name"
                  type="text"
                  bind:value={name}
                  disabled={!isAdmin}
                  placeholder="e.g., Development Hours"
                  class="w-full px-3 py-2 bg-slate-900 border border-slate-600 rounded text-sm text-slate-100 placeholder-slate-500 focus:outline-none focus:ring-1 focus:ring-emerald-500 focus:border-emerald-500 disabled:opacity-60 disabled:cursor-not-allowed"
                />
              </div>

              <div>
                <label for="description" class="block text-xs font-medium text-slate-400 uppercase tracking-wider mb-2">
                  Description
                </label>
                <textarea
                  id="description"
                  bind:value={description}
                  disabled={!isAdmin}
                  rows="2"
                  placeholder="Optional description..."
                  class="w-full px-3 py-2 bg-slate-900 border border-slate-600 rounded text-sm text-slate-100 placeholder-slate-500 focus:outline-none focus:ring-1 focus:ring-emerald-500 focus:border-emerald-500 resize-none disabled:opacity-60 disabled:cursor-not-allowed"
                />
              </div>

              <div>
                <label class="block text-xs font-medium text-slate-400 uppercase tracking-wider mb-2">
                  Timezone <span class="text-red-500">*</span>
                </label>
                <div class="max-w-xs">
                  <TimezoneSelect value={timezone} disabled={!isAdmin} on:change={handleTimezoneChange} />
                </div>
                <p class="text-xs text-slate-500 mt-1">Schedule times will be in this timezone</p>
              </div>

              <div class="flex items-center gap-3">
                <label class="flex items-center gap-2 {isAdmin ? 'cursor-pointer' : 'cursor-not-allowed'}">
                  <input
                    type="checkbox"
                    bind:checked={isEnabled}
                    disabled={!isAdmin}
                    class="w-4 h-4 text-emerald-600 bg-slate-900 border-slate-600 rounded focus:ring-emerald-500 focus:ring-offset-slate-800 disabled:opacity-60"
                  />
                  <span class="text-sm text-slate-300">Policy enabled</span>
                </label>
              </div>
            </div>
          </div>

          <!-- Schedule Section -->
          <div class="bg-slate-800 border border-slate-700 rounded-lg p-5">
            <div class="flex items-center justify-between mb-4">
              <div>
                <h2 class="text-sm font-medium text-slate-300 uppercase tracking-wider">Schedule</h2>
                <p class="text-xs text-slate-500 mt-1">
                  Resources are <span class="text-emerald-500">running</span> during scheduled hours.
                  Outside these hours, resources will be stopped.
                </p>
              </div>
              {#if isAdmin}
                <div class="flex items-center bg-slate-900 border border-slate-700 rounded-lg p-0.5">
                  <button
                    type="button"
                    on:click={() => scheduleType = 'weekly'}
                    class="px-3 py-1.5 text-xs font-medium rounded-md transition-colors {scheduleType === 'weekly' ? 'bg-slate-700 text-slate-100' : 'text-slate-400 hover:text-slate-300'}"
                  >
                    Weekly Grid
                  </button>
                  <button
                    type="button"
                    on:click={() => scheduleType = 'cron'}
                    class="px-3 py-1.5 text-xs font-medium rounded-md transition-colors {scheduleType === 'cron' ? 'bg-slate-700 text-slate-100' : 'text-slate-400 hover:text-slate-300'}"
                  >
                    Cron Expression
                  </button>
                </div>
              {:else}
                <span class="text-xs text-slate-500 uppercase">{scheduleType}</span>
              {/if}
            </div>

            {#if scheduleType === 'weekly'}
              <ScheduleGrid schedule={weeklySchedule} disabled={!isAdmin} on:change={handleScheduleChange} />
            {:else}
              <CronScheduleInput schedule={cronSchedule} disabled={!isAdmin} on:change={handleCronScheduleChange} />
            {/if}
          </div>

          <!-- Resource Selection Section -->
          <div class="bg-slate-800 border border-slate-700 rounded-lg p-5">
            <h2 class="text-sm font-medium text-slate-300 uppercase tracking-wider mb-4">Resource Selection</h2>
            <p class="text-xs text-slate-500 mb-4">
              Resources matching this selector are affected by this policy
            </p>

            <ResourceSelector value={resourceSelector} disabled={!isAdmin} on:change={handleResourceSelectorChange} />
          </div>

          <!-- Actions -->
          {#if isAdmin}
            <div class="flex items-center justify-end gap-3 pt-4">
              <button
                type="button"
                on:click={() => goto('/policies')}
                class="px-4 py-2 text-sm font-medium text-slate-300 hover:text-white bg-slate-700 hover:bg-slate-600 rounded transition-colors"
              >
                Cancel
              </button>
              <button
                type="submit"
                disabled={saving}
                class="px-4 py-2 bg-emerald-600 hover:bg-emerald-500 disabled:bg-emerald-800 text-white text-sm font-medium rounded transition-colors disabled:cursor-not-allowed"
              >
                {saving ? 'Saving...' : 'Save Changes'}
              </button>
            </div>
          {:else}
            <div class="flex items-center justify-end pt-4">
              <button
                type="button"
                on:click={() => goto('/policies')}
                class="px-4 py-2 text-sm font-medium text-slate-300 hover:text-white bg-slate-700 hover:bg-slate-600 rounded transition-colors"
              >
                Back to Policies
              </button>
            </div>
          {/if}
        </form>
      {/if}
    </div>
  </main>
</div>
