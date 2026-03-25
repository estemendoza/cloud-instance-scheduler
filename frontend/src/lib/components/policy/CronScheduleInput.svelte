<script lang="ts">
  import type { CronSchedule } from '$lib/types/policy';

  let {
    schedule = $bindable({ start: '', stop: '' }),
    disabled = false,
    onchange,
  }: {
    schedule?: CronSchedule;
    disabled?: boolean;
    onchange?: (_value: CronSchedule) => void;
  } = $props();

  let startExpr = schedule.start || '';
  let stopExpr = schedule.stop || '';

  // Sync from prop
  $effect(() => {
    startExpr = schedule.start || '';
    stopExpr = schedule.stop || '';
  });

  // Cron field descriptions
  const CRON_FIELDS = '┌───── minute (0-59)\n│ ┌───── hour (0-23)\n│ │ ┌───── day of month (1-31)\n│ │ │ ┌───── month (1-12)\n│ │ │ │ ┌───── day of week (0-7, Sun=0 or 7)\n│ │ │ │ │\n* * * * *';

  interface Preset {
    label: string;
    start: string;
    stop: string;
    description: string;
  }

  const PRESETS: Preset[] = [
    { label: 'Weekdays 9-6', start: '0 9 * * 1-5', stop: '0 18 * * 1-5', description: 'Mon-Fri, 9am to 6pm' },
    { label: 'Weekdays 8-8', start: '0 8 * * 1-5', stop: '0 20 * * 1-5', description: 'Mon-Fri, 8am to 8pm' },
    { label: 'Every day 6a-10p', start: '0 6 * * *', stop: '0 22 * * *', description: 'Daily, 6am to 10pm' },
    { label: 'Business hours', start: '0 8 * * 1-5', stop: '0 17 * * 1-5', description: 'Mon-Fri, 8am to 5pm' },
  ];

  function applyPreset(preset: Preset) {
    if (disabled) return;
    startExpr = preset.start;
    stopExpr = preset.stop;
    emitChange();
  }

  function emitChange() {
    const newSchedule: CronSchedule = { start: startExpr.trim(), stop: stopExpr.trim() };
    onchange?.(newSchedule);
  }

  function handleInput() {
    emitChange();
  }

  // Basic client-side validation
  function isLikelyValidCron(expr: string): boolean {
    if (!expr.trim()) return false;
    const parts = expr.trim().split(/\s+/);
    return parts.length === 5;
  }

  const startValid = $derived(isLikelyValidCron(startExpr));
  const stopValid = $derived(isLikelyValidCron(stopExpr));
</script>

<div class="space-y-4">
  <!-- Presets -->
  {#if !disabled}
    <div class="flex items-center gap-2 flex-wrap">
      <span class="text-xs text-slate-500 uppercase tracking-wider">Presets:</span>
      {#each PRESETS as preset}
        <button
          type="button"
          onclick={() => applyPreset(preset)}
          class="px-2 py-1 text-xs text-slate-400 hover:text-slate-200 bg-slate-800 hover:bg-slate-700 border border-slate-700 rounded transition-colors"
          title={preset.description}
        >
          {preset.label}
        </button>
      {/each}
    </div>
  {/if}

  <!-- Cron reference -->
  <div class="px-3 py-2 bg-slate-800/50 border border-slate-700/50 rounded">
    <pre class="text-[10px] font-mono text-slate-500 leading-tight">{CRON_FIELDS}</pre>
  </div>

  <!-- Start expression -->
  <div>
    <label class="block text-xs font-medium text-slate-400 uppercase tracking-wider mb-1.5">
      Start (when to turn ON) <span class="text-red-500">*</span>
    </label>
    <div class="flex items-center gap-2">
      <input
        type="text"
        bind:value={startExpr}
        oninput={handleInput}
        placeholder="0 9 * * 1-5"
        {disabled}
        class="flex-1 px-3 py-2 bg-slate-900 border rounded text-sm font-mono text-slate-100 placeholder-slate-600 focus:outline-none focus:ring-1 focus:ring-emerald-500 focus:border-emerald-500 {startExpr && !startValid ? 'border-red-500' : 'border-slate-600'}"
      />
      {#if startExpr}
        <span class="text-xs {startValid ? 'text-emerald-500' : 'text-red-400'}">
          {startValid ? 'valid' : 'invalid'}
        </span>
      {/if}
    </div>
  </div>

  <!-- Stop expression -->
  <div>
    <label class="block text-xs font-medium text-slate-400 uppercase tracking-wider mb-1.5">
      Stop (when to turn OFF) <span class="text-red-500">*</span>
    </label>
    <div class="flex items-center gap-2">
      <input
        type="text"
        bind:value={stopExpr}
        oninput={handleInput}
        placeholder="0 18 * * 1-5"
        {disabled}
        class="flex-1 px-3 py-2 bg-slate-900 border rounded text-sm font-mono text-slate-100 placeholder-slate-600 focus:outline-none focus:ring-1 focus:ring-emerald-500 focus:border-emerald-500 {stopExpr && !stopValid ? 'border-red-500' : 'border-slate-600'}"
      />
      {#if stopExpr}
        <span class="text-xs {stopValid ? 'text-emerald-500' : 'text-red-400'}">
          {stopValid ? 'valid' : 'invalid'}
        </span>
      {/if}
    </div>
  </div>

  <!-- Help text -->
  <div class="flex items-center gap-2 px-2 py-1.5 bg-slate-800/50 border border-slate-700/50 rounded text-xs text-slate-400">
    <svg class="w-3.5 h-3.5 text-slate-500 flex-shrink-0" fill="none" viewBox="0 0 24 24" stroke="currentColor" stroke-width="2">
      <path stroke-linecap="round" stroke-linejoin="round" d="M13 16h-1v-4h-1m1-4h.01M21 12a9 9 0 11-18 0 9 9 0 0118 0z" />
    </svg>
    <span>
      Instances will be started at the <strong>start</strong> cron time and stopped at the <strong>stop</strong> cron time.
      Common patterns: <code class="text-slate-300">1-5</code> = Mon-Fri, <code class="text-slate-300">0,6</code> = weekends, <code class="text-slate-300">*/2</code> = every 2.
    </span>
  </div>
</div>
