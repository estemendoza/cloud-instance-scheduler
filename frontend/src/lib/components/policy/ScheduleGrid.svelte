<script lang="ts">
  import { createEventDispatcher } from 'svelte';
  import { DAYS_OF_WEEK, DAY_LABELS, type WeeklySchedule, type TimeWindow } from '$lib/types/policy';

  export let schedule: WeeklySchedule = {};
  export let disabled = false;

  const dispatch = createEventDispatcher<{ change: WeeklySchedule }>();

  // Grid state: 7 days × 24 hours
  // true = running (active), false = stopped
  let grid: boolean[][] = Array(7).fill(null).map(() => Array(24).fill(false));

  // Drag state
  let isDragging = false;
  let dragMode: 'add' | 'remove' = 'add';

  // Initialize grid from schedule prop
  $: initializeFromSchedule(schedule);

  function initializeFromSchedule(sched: WeeklySchedule) {
    // Reset grid
    grid = Array(7).fill(null).map(() => Array(24).fill(false));

    // Fill in from schedule
    DAYS_OF_WEEK.forEach((day, dayIndex) => {
      const windows = sched[day] || [];
      for (const window of windows) {
        const startHour = parseInt(window.start.split(':')[0], 10);
        const endHour = parseInt(window.end.split(':')[0], 10);
        // Mark hours from start to end-1 as active
        for (let h = startHour; h < endHour; h++) {
          grid[dayIndex][h] = true;
        }
      }
    });

    grid = grid; // Trigger reactivity
  }

  function handleMouseDown(dayIndex: number, hour: number, event: MouseEvent) {
    if (disabled) return;
    event.preventDefault();

    isDragging = true;
    // If cell is already active, we're removing; otherwise adding
    dragMode = grid[dayIndex][hour] ? 'remove' : 'add';

    // Apply to starting cell
    grid[dayIndex][hour] = dragMode === 'add';
    grid = grid;
  }

  function handleMouseEnter(dayIndex: number, hour: number) {
    if (!isDragging || disabled) return;

    grid[dayIndex][hour] = dragMode === 'add';
    grid = grid;
  }

  function handleMouseUp() {
    if (isDragging) {
      isDragging = false;
      emitChange();
    }
  }

  function convertGridToSchedule(): WeeklySchedule {
    const result: WeeklySchedule = {};

    DAYS_OF_WEEK.forEach((day, dayIndex) => {
      const windows: TimeWindow[] = [];
      let windowStart: number | null = null;

      for (let hour = 0; hour <= 24; hour++) {
        const isActive = hour < 24 ? grid[dayIndex][hour] : false;

        if (isActive && windowStart === null) {
          // Start of a new window
          windowStart = hour;
        } else if (!isActive && windowStart !== null) {
          // End of current window
          windows.push({
            start: formatHour(windowStart),
            end: formatHour(hour)
          });
          windowStart = null;
        }
      }

      if (windows.length > 0) {
        result[day] = windows;
      }
    });

    return result;
  }

  function formatHour(hour: number): string {
    return `${hour.toString().padStart(2, '0')}:00`;
  }

  function emitChange() {
    const newSchedule = convertGridToSchedule();
    dispatch('change', newSchedule);
  }

  // Quick actions
  function setWeekdays9to5() {
    grid = Array(7).fill(null).map((_, dayIndex) => {
      return Array(24).fill(false).map((_, hour) => {
        // Monday-Friday (0-4), 9am-6pm
        return dayIndex < 5 && hour >= 9 && hour < 18;
      });
    });
    emitChange();
  }

  function setAllDay() {
    grid = Array(7).fill(null).map(() => Array(24).fill(true));
    emitChange();
  }

  function clearAll() {
    grid = Array(7).fill(null).map(() => Array(24).fill(false));
    emitChange();
  }

  // Format hour label
  function formatHourLabel(hour: number): string {
    if (hour === 0) return '12a';
    if (hour === 12) return '12p';
    if (hour < 12) return `${hour}a`;
    return `${hour - 12}p`;
  }
</script>

<svelte:window on:mouseup={handleMouseUp} />

<div class="schedule-grid">
  <!-- Quick Actions -->
  {#if !disabled}
    <div class="flex items-center gap-2 mb-3">
      <span class="text-xs text-slate-500 uppercase tracking-wider">Quick:</span>
      <button
        type="button"
        on:click={setWeekdays9to5}
        class="px-2 py-1 text-xs text-slate-400 hover:text-slate-200 bg-slate-800 hover:bg-slate-700 border border-slate-700 rounded transition-colors"
      >
        Weekdays 9-6
      </button>
      <button
        type="button"
        on:click={setAllDay}
        class="px-2 py-1 text-xs text-slate-400 hover:text-slate-200 bg-slate-800 hover:bg-slate-700 border border-slate-700 rounded transition-colors"
      >
        24/7
      </button>
      <button
        type="button"
        on:click={clearAll}
        class="px-2 py-1 text-xs text-slate-400 hover:text-slate-200 bg-slate-800 hover:bg-slate-700 border border-slate-700 rounded transition-colors"
      >
        Clear
      </button>
    </div>
  {/if}

  <!-- Help Tip -->
  <div class="flex items-center gap-2 mb-3 px-2 py-1.5 bg-slate-800/50 border border-slate-700/50 rounded text-xs text-slate-400">
    <svg class="w-3.5 h-3.5 text-slate-500 flex-shrink-0" fill="none" viewBox="0 0 24 24" stroke="currentColor" stroke-width="2">
      <path stroke-linecap="round" stroke-linejoin="round" d="M13 16h-1v-4h-1m1-4h.01M21 12a9 9 0 11-18 0 9 9 0 0118 0z" />
    </svg>
    <span>Click and drag to paint hours. Green = running, dark = stopped.</span>
  </div>

  <!-- Grid Container -->
  <div class="overflow-x-auto">
    <div class="inline-block min-w-full">
      <!-- Header Row (Days) -->
      <div class="flex">
        <!-- Empty corner cell -->
        <div class="w-10 flex-shrink-0"></div>

        {#each DAYS_OF_WEEK as day, _dayIndex}
          <div class="flex-1 min-w-[3rem] text-center">
            <span class="text-xs font-medium text-slate-400 uppercase tracking-wider">
              {DAY_LABELS[day]}
            </span>
          </div>
        {/each}
      </div>

      <!-- Grid Rows (Hours) -->
      <div
        class="mt-1 border border-slate-700 rounded overflow-hidden select-none"
        role="grid"
        aria-label="Weekly schedule grid"
      >
        {#each Array(24) as _, hour}
          <div class="flex {hour > 0 ? 'border-t border-slate-800' : ''}">
            <!-- Hour Label -->
            <div class="w-10 flex-shrink-0 flex items-center justify-end pr-2">
              <span class="text-[10px] font-mono text-slate-500">
                {formatHourLabel(hour)}
              </span>
            </div>

            <!-- Day Cells -->
            {#each DAYS_OF_WEEK as day, dayIndex}
              <button
                type="button"
                class="flex-1 min-w-[3rem] h-5 transition-colors {dayIndex > 0 ? 'border-l border-slate-800' : ''} {grid[dayIndex][hour] ? 'bg-emerald-600/80 hover:bg-emerald-500/80' : 'bg-slate-850 hover:bg-slate-800'} {disabled ? 'cursor-not-allowed opacity-60' : 'cursor-crosshair'}"
                on:mousedown={(e) => handleMouseDown(dayIndex, hour, e)}
                on:mouseenter={() => handleMouseEnter(dayIndex, hour)}
                disabled={disabled}
                aria-label="{DAY_LABELS[day]} {formatHour(hour)} - {grid[dayIndex][hour] ? 'Running' : 'Stopped'}"
                aria-pressed={grid[dayIndex][hour]}
              />
            {/each}
          </div>
        {/each}
      </div>
    </div>
  </div>

  <!-- Legend -->
  <div class="flex items-center gap-4 mt-3">
    <div class="flex items-center gap-1.5">
      <div class="w-3 h-3 bg-emerald-600/80 rounded-sm"></div>
      <span class="text-xs text-slate-400">Running</span>
    </div>
    <div class="flex items-center gap-1.5">
      <div class="w-3 h-3 bg-slate-850 border border-slate-700 rounded-sm"></div>
      <span class="text-xs text-slate-400">Stopped</span>
    </div>
  </div>
</div>

<style>
  .bg-slate-850 {
    background-color: rgb(18 24 33);
  }
</style>
