<script lang="ts">
  import { onMount } from 'svelte';
  import { calculatorAPI } from '$lib/api/endpoints/calculator';
  import Sidebar from '$lib/components/layout/Sidebar.svelte';
  import type {
    InstanceTypeInfo,
    EstimateResponse,
    ScheduleEstimateResponse,
    WeeklySchedule
  } from '$lib/types/calculator';

  // Tab state
  let activeTab: 'estimate' | 'compare' | 'schedule' = 'estimate';

  // Data
  let regions: string[] = [];
  let instanceTypes: InstanceTypeInfo[] = [];
  let filteredInstanceTypes: InstanceTypeInfo[] = [];
  let loading = true;
  let calculating = false;

  // Estimate form
  let estimateRegion = '';
  let estimateInstanceType = '';
  let estimateHoursPerDay = 8;
  let estimateDaysPerWeek = 5;
  let estimateResult: EstimateResponse | null = null;

  // Compare form
  let compareInstances: { region: string; instance_type: string }[] = [
    { region: '', instance_type: '' },
    { region: '', instance_type: '' }
  ];
  let compareHoursPerDay = 8;
  let compareDaysPerWeek = 5;
  let compareResults: EstimateResponse[] = [];

  // Schedule form
  let scheduleRegion = '';
  let scheduleInstanceType = '';
  let schedule: WeeklySchedule = {
    monday: [{ start: '09:00', end: '18:00' }],
    tuesday: [{ start: '09:00', end: '18:00' }],
    wednesday: [{ start: '09:00', end: '18:00' }],
    thursday: [{ start: '09:00', end: '18:00' }],
    friday: [{ start: '09:00', end: '18:00' }],
  };
  let scheduleResult: ScheduleEstimateResponse | null = null;

  const DAYS = ['monday', 'tuesday', 'wednesday', 'thursday', 'friday', 'saturday', 'sunday'] as const;
  const DAY_LABELS: Record<string, string> = {
    monday: 'Mon', tuesday: 'Tue', wednesday: 'Wed',
    thursday: 'Thu', friday: 'Fri', saturday: 'Sat', sunday: 'Sun'
  };

  onMount(async () => {
    await loadData();
  });

  async function loadData() {
    loading = true;
    try {
      [regions, instanceTypes] = await Promise.all([
        calculatorAPI.getRegions(),
        calculatorAPI.getInstanceTypes()
      ]);
      filteredInstanceTypes = instanceTypes;

      // Set defaults
      if (regions.length > 0) {
        estimateRegion = regions[0];
        scheduleRegion = regions[0];
        compareInstances = compareInstances.map(i => ({ ...i, region: regions[0] }));
      }
    } catch (err) {
      console.error('Failed to load data:', err);
    } finally {
      loading = false;
    }
  }

  function filterInstanceTypes(region: string) {
    if (!region) {
      filteredInstanceTypes = instanceTypes;
    } else {
      filteredInstanceTypes = instanceTypes.filter(i => i.region === region);
    }
  }

  $: filterInstanceTypes(estimateRegion);

  async function calculateEstimate() {
    if (!estimateRegion || !estimateInstanceType) return;
    calculating = true;
    try {
      estimateResult = await calculatorAPI.estimate({
        region: estimateRegion,
        instance_type: estimateInstanceType,
        hours_per_day: estimateHoursPerDay,
        days_per_week: estimateDaysPerWeek
      });
    } catch (err) {
      console.error('Estimate failed:', err);
    } finally {
      calculating = false;
    }
  }

  async function calculateCompare() {
    const validInstances = compareInstances.filter(i => i.region && i.instance_type);
    if (validInstances.length === 0) return;

    calculating = true;
    try {
      const response = await calculatorAPI.compare({
        instances: validInstances,
        hours_per_day: compareHoursPerDay,
        days_per_week: compareDaysPerWeek
      });
      compareResults = response.estimates;
    } catch (err) {
      console.error('Compare failed:', err);
    } finally {
      calculating = false;
    }
  }

  async function calculateSchedule() {
    if (!scheduleRegion || !scheduleInstanceType) return;
    calculating = true;
    try {
      scheduleResult = await calculatorAPI.scheduleEstimate({
        region: scheduleRegion,
        instance_type: scheduleInstanceType,
        schedule
      });
    } catch (err) {
      console.error('Schedule estimate failed:', err);
    } finally {
      calculating = false;
    }
  }

  function addCompareInstance() {
    if (compareInstances.length < 4) {
      compareInstances = [...compareInstances, { region: regions[0] || '', instance_type: '' }];
    }
  }

  function removeCompareInstance(index: number) {
    if (compareInstances.length > 2) {
      compareInstances = compareInstances.filter((_, i) => i !== index);
    }
  }

  function toggleDay(day: string) {
    if (schedule[day as keyof WeeklySchedule]) {
      const { [day as keyof WeeklySchedule]: _, ...rest } = schedule;
      schedule = rest as WeeklySchedule;
    } else {
      schedule = { ...schedule, [day]: [{ start: '09:00', end: '18:00' }] };
    }
  }

  function updateDayTime(day: string, field: 'start' | 'end', value: string) {
    if (schedule[day as keyof WeeklySchedule]) {
      schedule = {
        ...schedule,
        [day]: [{ ...schedule[day as keyof WeeklySchedule]![0], [field]: value }]
      };
    }
  }

  function formatCurrency(value: number): string {
    return new Intl.NumberFormat('en-US', {
      style: 'currency',
      currency: 'USD',
      minimumFractionDigits: 2,
      maximumFractionDigits: 2
    }).format(value);
  }

  function getInstanceTypesForRegion(region: string): InstanceTypeInfo[] {
    if (!region) return [];
    return instanceTypes.filter(i => i.region === region);
  }
</script>

<svelte:head>
  <title>Calculator - Cloud Instance Scheduler</title>
</svelte:head>

<div class="flex h-screen bg-slate-900">
  <Sidebar />

  <main class="flex-1 overflow-auto pt-14 lg:pt-0">
    <div class="p-6">
      <!-- Header -->
      <div class="mb-6">
        <h1 class="text-xl font-semibold text-slate-100">Cost Calculator</h1>
        <p class="text-sm text-slate-500 mt-1">Estimate cloud instance costs with different configurations</p>
      </div>

      {#if loading}
        <div class="flex items-center justify-center py-12">
          <div class="animate-spin rounded-full h-8 w-8 border-2 border-slate-700 border-t-emerald-500"></div>
        </div>
      {:else}
        <!-- Tabs -->
        <div class="flex border-b border-slate-700 mb-6">
          <button
            on:click={() => activeTab = 'estimate'}
            class="px-4 py-2 text-sm font-medium transition-colors {activeTab === 'estimate' ? 'text-emerald-400 border-b-2 border-emerald-400' : 'text-slate-400 hover:text-slate-300'}"
          >
            Estimate
          </button>
          <button
            on:click={() => activeTab = 'compare'}
            class="px-4 py-2 text-sm font-medium transition-colors {activeTab === 'compare' ? 'text-emerald-400 border-b-2 border-emerald-400' : 'text-slate-400 hover:text-slate-300'}"
          >
            Compare
          </button>
          <button
            on:click={() => activeTab = 'schedule'}
            class="px-4 py-2 text-sm font-medium transition-colors {activeTab === 'schedule' ? 'text-emerald-400 border-b-2 border-emerald-400' : 'text-slate-400 hover:text-slate-300'}"
          >
            Schedule
          </button>
        </div>

        <!-- Estimate Tab -->
        {#if activeTab === 'estimate'}
          <div class="grid grid-cols-1 lg:grid-cols-2 gap-6">
            <!-- Form -->
            <div class="bg-slate-800 border border-slate-700 rounded-lg p-5">
              <h2 class="text-sm font-medium text-slate-300 uppercase tracking-wider mb-4">Configuration</h2>

              <div class="space-y-4">
                <div>
                  <label class="block text-sm text-slate-400 mb-1">Region</label>
                  <select
                    bind:value={estimateRegion}
                    class="w-full px-3 py-2 bg-slate-700 border border-slate-600 rounded text-slate-200 text-sm focus:outline-none focus:border-emerald-500"
                  >
                    {#each regions as region}
                      <option value={region}>{region}</option>
                    {/each}
                  </select>
                </div>

                <div>
                  <label class="block text-sm text-slate-400 mb-1">Instance Type</label>
                  <select
                    bind:value={estimateInstanceType}
                    class="w-full px-3 py-2 bg-slate-700 border border-slate-600 rounded text-slate-200 text-sm focus:outline-none focus:border-emerald-500"
                  >
                    <option value="">Select instance type</option>
                    {#each filteredInstanceTypes as type}
                      <option value={type.instance_type}>{type.instance_type} - {formatCurrency(type.hourly_rate)}/hr</option>
                    {/each}
                  </select>
                </div>

                <div class="grid grid-cols-2 gap-4">
                  <div>
                    <label class="block text-sm text-slate-400 mb-1">Hours/Day</label>
                    <input
                      type="number"
                      min="1"
                      max="24"
                      bind:value={estimateHoursPerDay}
                      class="w-full px-3 py-2 bg-slate-700 border border-slate-600 rounded text-slate-200 text-sm focus:outline-none focus:border-emerald-500"
                    />
                  </div>
                  <div>
                    <label class="block text-sm text-slate-400 mb-1">Days/Week</label>
                    <input
                      type="number"
                      min="1"
                      max="7"
                      bind:value={estimateDaysPerWeek}
                      class="w-full px-3 py-2 bg-slate-700 border border-slate-600 rounded text-slate-200 text-sm focus:outline-none focus:border-emerald-500"
                    />
                  </div>
                </div>

                <button
                  on:click={calculateEstimate}
                  disabled={calculating || !estimateInstanceType}
                  class="w-full px-4 py-2 bg-emerald-600 hover:bg-emerald-500 disabled:bg-slate-600 disabled:cursor-not-allowed text-white text-sm font-medium rounded transition-colors"
                >
                  {calculating ? 'Calculating...' : 'Calculate'}
                </button>
              </div>
            </div>

            <!-- Results -->
            <div class="bg-slate-800 border border-slate-700 rounded-lg p-5">
              <h2 class="text-sm font-medium text-slate-300 uppercase tracking-wider mb-4">Cost Breakdown</h2>

              {#if estimateResult && !estimateResult.error}
                <div class="space-y-4">
                  <div class="text-center pb-4 border-b border-slate-700">
                    <p class="text-3xl font-semibold text-emerald-400 font-mono">
                      {formatCurrency(estimateResult.monthly_cost)}
                    </p>
                    <p class="text-xs text-slate-500 mt-1">Est. Monthly Cost</p>
                  </div>

                  <dl class="space-y-3">
                    <div class="flex justify-between items-center py-2 border-b border-slate-700/50">
                      <dt class="text-sm text-slate-400">Hourly Rate</dt>
                      <dd class="text-sm font-mono text-slate-200">{formatCurrency(estimateResult.hourly_rate)}</dd>
                    </div>
                    <div class="flex justify-between items-center py-2 border-b border-slate-700/50">
                      <dt class="text-sm text-slate-400">Daily Cost</dt>
                      <dd class="text-sm font-mono text-slate-200">{formatCurrency(estimateResult.daily_cost)}</dd>
                    </div>
                    <div class="flex justify-between items-center py-2 border-b border-slate-700/50">
                      <dt class="text-sm text-slate-400">Weekly Cost</dt>
                      <dd class="text-sm font-mono text-slate-200">{formatCurrency(estimateResult.weekly_cost)}</dd>
                    </div>
                    <div class="flex justify-between items-center py-2 border-b border-slate-700/50">
                      <dt class="text-sm text-slate-400">Annual Cost</dt>
                      <dd class="text-sm font-mono text-emerald-400">{formatCurrency(estimateResult.annual_cost)}</dd>
                    </div>
                  </dl>
                </div>
              {:else if estimateResult?.error}
                <p class="text-red-400 text-sm">{estimateResult.error}</p>
              {:else}
                <div class="text-center py-8 text-slate-500">
                  <p>Configure your instance and click Calculate</p>
                </div>
              {/if}
            </div>
          </div>
        {/if}

        <!-- Compare Tab -->
        {#if activeTab === 'compare'}
          <div class="space-y-6">
            <!-- Form -->
            <div class="bg-slate-800 border border-slate-700 rounded-lg p-5">
              <div class="flex items-center justify-between mb-4">
                <h2 class="text-sm font-medium text-slate-300 uppercase tracking-wider">Instances to Compare</h2>
                {#if compareInstances.length < 4}
                  <button
                    on:click={addCompareInstance}
                    class="text-xs text-emerald-400 hover:text-emerald-300"
                  >
                    + Add Instance
                  </button>
                {/if}
              </div>

              <div class="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-4 gap-4 mb-4">
                {#each compareInstances as instance, index}
                  <div class="p-3 bg-slate-700/50 rounded space-y-3">
                    <div class="flex items-center justify-between">
                      <span class="text-xs text-slate-400">Instance {index + 1}</span>
                      {#if compareInstances.length > 2}
                        <button
                          on:click={() => removeCompareInstance(index)}
                          class="text-xs text-red-400 hover:text-red-300"
                        >
                          Remove
                        </button>
                      {/if}
                    </div>
                    <select
                      bind:value={instance.region}
                      class="w-full px-2 py-1.5 bg-slate-700 border border-slate-600 rounded text-slate-200 text-xs focus:outline-none focus:border-emerald-500"
                    >
                      {#each regions as region}
                        <option value={region}>{region}</option>
                      {/each}
                    </select>
                    <select
                      bind:value={instance.instance_type}
                      class="w-full px-2 py-1.5 bg-slate-700 border border-slate-600 rounded text-slate-200 text-xs focus:outline-none focus:border-emerald-500"
                    >
                      <option value="">Select type</option>
                      {#each getInstanceTypesForRegion(instance.region) as type}
                        <option value={type.instance_type}>{type.instance_type}</option>
                      {/each}
                    </select>
                  </div>
                {/each}
              </div>

              <div class="flex items-end gap-4">
                <div>
                  <label class="block text-sm text-slate-400 mb-1">Hours/Day</label>
                  <input
                    type="number"
                    min="1"
                    max="24"
                    bind:value={compareHoursPerDay}
                    class="w-24 px-3 py-2 bg-slate-700 border border-slate-600 rounded text-slate-200 text-sm focus:outline-none focus:border-emerald-500"
                  />
                </div>
                <div>
                  <label class="block text-sm text-slate-400 mb-1">Days/Week</label>
                  <input
                    type="number"
                    min="1"
                    max="7"
                    bind:value={compareDaysPerWeek}
                    class="w-24 px-3 py-2 bg-slate-700 border border-slate-600 rounded text-slate-200 text-sm focus:outline-none focus:border-emerald-500"
                  />
                </div>
                <button
                  on:click={calculateCompare}
                  disabled={calculating}
                  class="px-4 py-2 bg-emerald-600 hover:bg-emerald-500 disabled:bg-slate-600 text-white text-sm font-medium rounded transition-colors"
                >
                  {calculating ? 'Calculating...' : 'Compare'}
                </button>
              </div>
            </div>

            <!-- Results -->
            {#if compareResults.length > 0}
              <div class="bg-slate-800 border border-slate-700 rounded-lg overflow-hidden">
                <table class="w-full">
                  <thead>
                    <tr class="border-b border-slate-700">
                      <th class="px-4 py-3 text-left text-xs font-medium text-slate-400 uppercase">Instance</th>
                      <th class="px-4 py-3 text-right text-xs font-medium text-slate-400 uppercase">Hourly</th>
                      <th class="px-4 py-3 text-right text-xs font-medium text-slate-400 uppercase">Daily</th>
                      <th class="px-4 py-3 text-right text-xs font-medium text-slate-400 uppercase">Weekly</th>
                      <th class="px-4 py-3 text-right text-xs font-medium text-slate-400 uppercase">Monthly</th>
                      <th class="px-4 py-3 text-right text-xs font-medium text-slate-400 uppercase">Annual</th>
                    </tr>
                  </thead>
                  <tbody class="divide-y divide-slate-700">
                    {#each compareResults as result, _index}
                      {@const isLowest = result.monthly_cost === Math.min(...compareResults.map(r => r.monthly_cost))}
                      <tr class="{isLowest ? 'bg-emerald-900/20' : ''}">
                        <td class="px-4 py-3">
                          <div class="flex items-center gap-2">
                            <span class="text-sm font-medium text-slate-200">{result.instance_type}</span>
                            {#if isLowest}
                              <span class="text-xs bg-emerald-600 text-white px-1.5 py-0.5 rounded">Lowest</span>
                            {/if}
                          </div>
                          <span class="text-xs text-slate-500">{result.region}</span>
                        </td>
                        <td class="px-4 py-3 text-right text-sm font-mono text-slate-300">{formatCurrency(result.hourly_rate)}</td>
                        <td class="px-4 py-3 text-right text-sm font-mono text-slate-300">{formatCurrency(result.daily_cost)}</td>
                        <td class="px-4 py-3 text-right text-sm font-mono text-slate-300">{formatCurrency(result.weekly_cost)}</td>
                        <td class="px-4 py-3 text-right text-sm font-mono {isLowest ? 'text-emerald-400' : 'text-slate-300'}">{formatCurrency(result.monthly_cost)}</td>
                        <td class="px-4 py-3 text-right text-sm font-mono {isLowest ? 'text-emerald-400' : 'text-slate-300'}">{formatCurrency(result.annual_cost)}</td>
                      </tr>
                    {/each}
                  </tbody>
                </table>
              </div>
            {/if}
          </div>
        {/if}

        <!-- Schedule Tab -->
        {#if activeTab === 'schedule'}
          <div class="grid grid-cols-1 lg:grid-cols-2 gap-6">
            <!-- Form -->
            <div class="bg-slate-800 border border-slate-700 rounded-lg p-5">
              <h2 class="text-sm font-medium text-slate-300 uppercase tracking-wider mb-4">Configuration</h2>

              <div class="space-y-4">
                <div>
                  <label class="block text-sm text-slate-400 mb-1">Region</label>
                  <select
                    bind:value={scheduleRegion}
                    class="w-full px-3 py-2 bg-slate-700 border border-slate-600 rounded text-slate-200 text-sm focus:outline-none focus:border-emerald-500"
                  >
                    {#each regions as region}
                      <option value={region}>{region}</option>
                    {/each}
                  </select>
                </div>

                <div>
                  <label class="block text-sm text-slate-400 mb-1">Instance Type</label>
                  <select
                    bind:value={scheduleInstanceType}
                    class="w-full px-3 py-2 bg-slate-700 border border-slate-600 rounded text-slate-200 text-sm focus:outline-none focus:border-emerald-500"
                  >
                    <option value="">Select instance type</option>
                    {#each getInstanceTypesForRegion(scheduleRegion) as type}
                      <option value={type.instance_type}>{type.instance_type} - {formatCurrency(type.hourly_rate)}/hr</option>
                    {/each}
                  </select>
                </div>

                <div>
                  <label class="block text-sm text-slate-400 mb-2">Weekly Schedule</label>
                  <div class="space-y-2">
                    {#each DAYS as day}
                      <div class="flex items-center gap-3">
                        <button
                          on:click={() => toggleDay(day)}
                          class="w-12 text-xs font-medium py-1 rounded {schedule[day] ? 'bg-emerald-600 text-white' : 'bg-slate-700 text-slate-400'}"
                        >
                          {DAY_LABELS[day]}
                        </button>
                        {#if schedule[day]}
                          <input
                            type="time"
                            value={schedule[day]?.[0]?.start || '09:00'}
                            on:change={(e) => updateDayTime(day, 'start', e.currentTarget.value)}
                            class="px-2 py-1 bg-slate-700 border border-slate-600 rounded text-slate-200 text-xs"
                          />
                          <span class="text-slate-500">to</span>
                          <input
                            type="time"
                            value={schedule[day]?.[0]?.end || '18:00'}
                            on:change={(e) => updateDayTime(day, 'end', e.currentTarget.value)}
                            class="px-2 py-1 bg-slate-700 border border-slate-600 rounded text-slate-200 text-xs"
                          />
                        {:else}
                          <span class="text-xs text-slate-500">Not running</span>
                        {/if}
                      </div>
                    {/each}
                  </div>
                </div>

                <button
                  on:click={calculateSchedule}
                  disabled={calculating || !scheduleInstanceType}
                  class="w-full px-4 py-2 bg-emerald-600 hover:bg-emerald-500 disabled:bg-slate-600 disabled:cursor-not-allowed text-white text-sm font-medium rounded transition-colors"
                >
                  {calculating ? 'Calculating...' : 'Calculate'}
                </button>
              </div>
            </div>

            <!-- Results -->
            <div class="bg-slate-800 border border-slate-700 rounded-lg p-5">
              <h2 class="text-sm font-medium text-slate-300 uppercase tracking-wider mb-4">Cost Breakdown</h2>

              {#if scheduleResult && !scheduleResult.error}
                <div class="space-y-4">
                  <div class="text-center pb-4 border-b border-slate-700">
                    <p class="text-3xl font-semibold text-emerald-400 font-mono">
                      {formatCurrency(scheduleResult.monthly_cost)}
                    </p>
                    <p class="text-xs text-slate-500 mt-1">Est. Monthly Cost</p>
                  </div>

                  <dl class="space-y-3">
                    <div class="flex justify-between items-center py-2 border-b border-slate-700/50">
                      <dt class="text-sm text-slate-400">Running Hours/Week</dt>
                      <dd class="text-sm font-mono text-slate-200">{scheduleResult.running_hours_per_week} hrs</dd>
                    </div>
                    <div class="flex justify-between items-center py-2 border-b border-slate-700/50">
                      <dt class="text-sm text-slate-400">Hourly Rate</dt>
                      <dd class="text-sm font-mono text-slate-200">{formatCurrency(scheduleResult.hourly_rate)}</dd>
                    </div>
                    <div class="flex justify-between items-center py-2 border-b border-slate-700/50">
                      <dt class="text-sm text-slate-400">Weekly Cost</dt>
                      <dd class="text-sm font-mono text-slate-200">{formatCurrency(scheduleResult.weekly_cost)}</dd>
                    </div>
                    <div class="flex justify-between items-center py-2 border-b border-slate-700/50">
                      <dt class="text-sm text-slate-400">Annual Cost</dt>
                      <dd class="text-sm font-mono text-slate-200">{formatCurrency(scheduleResult.annual_cost)}</dd>
                    </div>
                  </dl>

                  <!-- Savings vs 24/7 -->
                  <div class="mt-6 p-4 bg-emerald-900/20 border border-emerald-800/50 rounded">
                    <h3 class="text-sm font-medium text-emerald-400 mb-3">Savings vs 24/7</h3>
                    <dl class="space-y-2">
                      <div class="flex justify-between items-center">
                        <dt class="text-sm text-slate-400">24/7 Monthly Cost</dt>
                        <dd class="text-sm font-mono text-slate-300">{formatCurrency(scheduleResult.vs_24x7.monthly_24x7_cost)}</dd>
                      </div>
                      <div class="flex justify-between items-center">
                        <dt class="text-sm text-slate-400">Monthly Savings</dt>
                        <dd class="text-sm font-mono text-emerald-400">{formatCurrency(scheduleResult.vs_24x7.monthly_savings)}</dd>
                      </div>
                      <div class="flex justify-between items-center">
                        <dt class="text-sm text-slate-400">Savings Percent</dt>
                        <dd class="text-sm font-mono text-emerald-400">{scheduleResult.vs_24x7.savings_percent}%</dd>
                      </div>
                    </dl>
                  </div>
                </div>
              {:else if scheduleResult?.error}
                <p class="text-red-400 text-sm">{scheduleResult.error}</p>
              {:else}
                <div class="text-center py-8 text-slate-500">
                  <p>Configure your schedule and click Calculate</p>
                </div>
              {/if}
            </div>
          </div>
        {/if}
      {/if}
    </div>
  </main>
</div>
