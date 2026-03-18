<script lang="ts">
  import { goto } from '$app/navigation';
  import { policiesAPI } from '$lib/api/endpoints/policies';
  import { authStore } from '$lib/stores/auth';
  import { notify } from '$lib/utils/toast';
  import Sidebar from '$lib/components/layout/Sidebar.svelte';
  import ScheduleGrid from '$lib/components/policy/ScheduleGrid.svelte';
  import CronScheduleInput from '$lib/components/policy/CronScheduleInput.svelte';
  import TimezoneSelect from '$lib/components/policy/TimezoneSelect.svelte';
  import ResourceSelector from '$lib/components/policy/ResourceSelector.svelte';
  import type { WeeklySchedule, CronSchedule, ResourceSelector as ResourceSelectorType, PolicyCreate, ScheduleType } from '$lib/types/policy';

  let name = $state('');
  let description = $state('');
  let timezone = $state('UTC');
  let scheduleType = $state<ScheduleType>('weekly');
  let weeklySchedule = $state<WeeklySchedule>({});
  let cronSchedule = $state<CronSchedule>({ start: '', stop: '' });
  let resourceSelector = $state<ResourceSelectorType>({ tags: {} });
  let isEnabled = $state(true);

  let loading = $state(false);
  let error = $state('');

  let isAdmin = $derived($authStore.user?.role === 'admin');

  // Redirect if not admin
  $effect(() => {
    if ($authStore.user && !isAdmin) {
      goto('/policies');
    }
  });

  async function handleSubmit() {
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

    loading = true;

    try {
      const schedule = scheduleType === 'weekly' ? weeklySchedule : cronSchedule;
      const policy: PolicyCreate = {
        name: name.trim(),
        description: description.trim() || undefined,
        timezone,
        schedule_type: scheduleType,
        schedule,
        resource_selector: resourceSelector,
        is_enabled: isEnabled
      };

      await policiesAPI.create(policy);
      notify.success('Policy created successfully');
      goto('/policies');
    } catch (err: any) {
      error = err.message || 'Failed to create policy';
      notify.error(error);
    } finally {
      loading = false;
    }
  }

  function handleScheduleChange(value: WeeklySchedule) {
    weeklySchedule = value;
  }

  function handleCronScheduleChange(value: CronSchedule) {
    cronSchedule = value;
  }

  function handleTimezoneChange(value: string) {
    timezone = value;
  }

  function handleResourceSelectorChange(value: ResourceSelectorType) {
    resourceSelector = value;
  }
</script>

<svelte:head>
  <title>Create Policy - Cloud Instance Scheduler</title>
</svelte:head>

<div class="flex h-screen bg-slate-900">
  <Sidebar />

  <main class="flex-1 overflow-auto pt-14 lg:pt-0">
    <div class="p-6 max-w-4xl">
      <!-- Header -->
      <div class="mb-6">
        <button
          onclick={() => goto('/policies')}
          class="flex items-center gap-1 text-sm text-slate-400 hover:text-slate-200 mb-2"
        >
          <svg class="w-4 h-4" fill="none" viewBox="0 0 24 24" stroke="currentColor">
            <path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M15 19l-7-7 7-7" />
          </svg>
          Back to Policies
        </button>
        <h1 class="text-xl font-semibold text-slate-100">Create Policy</h1>
        <p class="text-sm text-slate-500 mt-1">Define when your cloud resources should be running</p>
      </div>

      {#if error}
        <div class="mb-4 p-3 bg-red-900/30 border border-red-800 rounded">
          <p class="text-sm text-red-400">{error}</p>
        </div>
      {/if}

      <form onsubmit={(e) => { e.preventDefault(); handleSubmit(); }} class="space-y-6">
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
                placeholder="e.g., Development Hours"
                class="w-full px-3 py-2 bg-slate-900 border border-slate-600 rounded text-sm text-slate-100 placeholder-slate-500 focus:outline-none focus:ring-1 focus:ring-emerald-500 focus:border-emerald-500"
              />
            </div>

            <div>
              <label for="description" class="block text-xs font-medium text-slate-400 uppercase tracking-wider mb-2">
                Description
              </label>
              <textarea
                id="description"
                bind:value={description}
                rows="2"
                placeholder="Optional description..."
                class="w-full px-3 py-2 bg-slate-900 border border-slate-600 rounded text-sm text-slate-100 placeholder-slate-500 focus:outline-none focus:ring-1 focus:ring-emerald-500 focus:border-emerald-500 resize-none"
              />
            </div>

            <div>
              <label class="block text-xs font-medium text-slate-400 uppercase tracking-wider mb-2">
                Timezone <span class="text-red-500">*</span>
              </label>
              <div class="max-w-xs">
                <TimezoneSelect value={timezone} onchange={handleTimezoneChange} />
              </div>
              <p class="text-xs text-slate-500 mt-1">Schedule times will be in this timezone</p>
            </div>

            <div class="flex items-center gap-3">
              <label class="flex items-center gap-2 cursor-pointer">
                <input
                  type="checkbox"
                  bind:checked={isEnabled}
                  class="w-4 h-4 text-emerald-600 bg-slate-900 border-slate-600 rounded focus:ring-emerald-500 focus:ring-offset-slate-800"
                />
                <span class="text-sm text-slate-300">Enable policy immediately</span>
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
                Define when resources should be <span class="text-emerald-500">running</span>.
                Outside these hours, resources will be stopped.
              </p>
            </div>
            <div class="flex items-center bg-slate-900 border border-slate-700 rounded-lg p-0.5">
              <button
                type="button"
                onclick={() => scheduleType = 'weekly'}
                class="px-3 py-1.5 text-xs font-medium rounded-md transition-colors {scheduleType === 'weekly' ? 'bg-slate-700 text-slate-100' : 'text-slate-400 hover:text-slate-300'}"
              >
                Weekly Grid
              </button>
              <button
                type="button"
                onclick={() => scheduleType = 'cron'}
                class="px-3 py-1.5 text-xs font-medium rounded-md transition-colors {scheduleType === 'cron' ? 'bg-slate-700 text-slate-100' : 'text-slate-400 hover:text-slate-300'}"
              >
                Cron Expression
              </button>
            </div>
          </div>

          {#if scheduleType === 'weekly'}
            <ScheduleGrid schedule={weeklySchedule} onchange={handleScheduleChange} />
          {:else}
            <CronScheduleInput schedule={cronSchedule} onchange={handleCronScheduleChange} />
          {/if}
        </div>

        <!-- Resource Selection Section -->
        <div class="bg-slate-800 border border-slate-700 rounded-lg p-5">
          <h2 class="text-sm font-medium text-slate-300 uppercase tracking-wider mb-4">Resource Selection</h2>
          <p class="text-xs text-slate-500 mb-4">
            Choose which resources this policy applies to
          </p>

          <ResourceSelector value={resourceSelector} onchange={handleResourceSelectorChange} />
        </div>

        <!-- Actions -->
        <div class="flex items-center justify-end gap-3 pt-4">
          <button
            type="button"
            onclick={() => goto('/policies')}
            class="px-4 py-2 text-sm font-medium text-slate-300 hover:text-white bg-slate-700 hover:bg-slate-600 rounded transition-colors"
          >
            Cancel
          </button>
          <button
            type="submit"
            disabled={loading}
            class="px-4 py-2 bg-emerald-600 hover:bg-emerald-500 disabled:bg-emerald-800 text-white text-sm font-medium rounded transition-colors disabled:cursor-not-allowed"
          >
            {loading ? 'Creating...' : 'Create Policy'}
          </button>
        </div>
      </form>
    </div>
  </main>
</div>
