<script lang="ts">
  import { createEventDispatcher } from 'svelte';

  let {
    value = $bindable(''),
    disabled = false,
  }: {
    value?: string;
    disabled?: boolean;
  } = $props();

  const dispatch = createEventDispatcher<{ change: string }>();

  let searchQuery = $state('');
  let isOpen = $state(false);
  let highlightedIndex = $state(0);

  // Common timezones grouped by region
  const TIMEZONES = [
    // Americas
    'America/New_York',
    'America/Chicago',
    'America/Denver',
    'America/Los_Angeles',
    'America/Phoenix',
    'America/Anchorage',
    'America/Toronto',
    'America/Vancouver',
    'America/Mexico_City',
    'America/Sao_Paulo',
    'America/Buenos_Aires',
    // Europe
    'Europe/London',
    'Europe/Dublin',
    'Europe/Paris',
    'Europe/Berlin',
    'Europe/Amsterdam',
    'Europe/Madrid',
    'Europe/Rome',
    'Europe/Zurich',
    'Europe/Stockholm',
    'Europe/Warsaw',
    'Europe/Moscow',
    // Asia
    'Asia/Dubai',
    'Asia/Kolkata',
    'Asia/Singapore',
    'Asia/Hong_Kong',
    'Asia/Shanghai',
    'Asia/Tokyo',
    'Asia/Seoul',
    'Asia/Bangkok',
    'Asia/Jakarta',
    // Pacific
    'Pacific/Auckland',
    'Pacific/Sydney',
    'Australia/Melbourne',
    'Australia/Perth',
    'Pacific/Honolulu',
    // UTC
    'UTC'
  ];

  const filteredTimezones = $derived(searchQuery
    ? TIMEZONES.filter(tz => tz.toLowerCase().includes(searchQuery.toLowerCase()))
    : TIMEZONES);

  $effect(() => {
    if (filteredTimezones.length > 0 && highlightedIndex >= filteredTimezones.length) {
      highlightedIndex = 0;
    }
  });

  function selectTimezone(tz: string) {
    value = tz;
    isOpen = false;
    searchQuery = '';
    dispatch('change', tz);
  }

  function handleKeydown(event: KeyboardEvent) {
    if (!isOpen) {
      if (event.key === 'Enter' || event.key === ' ' || event.key === 'ArrowDown') {
        event.preventDefault();
        isOpen = true;
      }
      return;
    }

    switch (event.key) {
      case 'ArrowDown':
        event.preventDefault();
        highlightedIndex = (highlightedIndex + 1) % filteredTimezones.length;
        break;
      case 'ArrowUp':
        event.preventDefault();
        highlightedIndex = highlightedIndex === 0 ? filteredTimezones.length - 1 : highlightedIndex - 1;
        break;
      case 'Enter':
        event.preventDefault();
        if (filteredTimezones[highlightedIndex]) {
          selectTimezone(filteredTimezones[highlightedIndex]);
        }
        break;
      case 'Escape':
        event.preventDefault();
        isOpen = false;
        searchQuery = '';
        break;
    }
  }

  function formatTimezone(tz: string): string {
    // Make it more readable
    return tz.replace(/_/g, ' ');
  }

  function handleBlur(event: FocusEvent) {
    // Check if focus is moving outside the component
    const relatedTarget = event.relatedTarget as HTMLElement;
    if (!relatedTarget?.closest('.timezone-select')) {
      isOpen = false;
      searchQuery = '';
    }
  }
</script>

<div class="timezone-select relative" onfocusout={handleBlur}>
  <!-- Trigger Button -->
  <button
    type="button"
    class="w-full px-3 py-2 bg-slate-900 border border-slate-600 rounded text-left text-sm text-slate-100 focus:outline-none focus:ring-1 focus:ring-emerald-500 focus:border-emerald-500 disabled:opacity-50 disabled:cursor-not-allowed"
    onclick={() => !disabled && (isOpen = !isOpen)}
    onkeydown={handleKeydown}
    {disabled}
    aria-expanded={isOpen}
    aria-haspopup="listbox"
  >
    <span class={value ? 'text-slate-100' : 'text-slate-500'}>
      {value ? formatTimezone(value) : 'Select timezone...'}
    </span>
    <svg
      class="absolute right-3 top-1/2 -translate-y-1/2 w-4 h-4 text-slate-500 transition-transform {isOpen ? 'rotate-180' : ''}"
      fill="none"
      viewBox="0 0 24 24"
      stroke="currentColor"
    >
      <path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M19 9l-7 7-7-7" />
    </svg>
  </button>

  <!-- Dropdown -->
  {#if isOpen}
    <div class="absolute z-50 w-full mt-1 bg-slate-800 border border-slate-700 rounded-lg shadow-xl max-h-64 overflow-hidden">
      <!-- Search Input -->
      <div class="p-2 border-b border-slate-700">
        <input
          type="text"
          bind:value={searchQuery}
          placeholder="Search timezones..."
          class="w-full px-2.5 py-1.5 bg-slate-900 border border-slate-600 rounded text-sm text-slate-100 placeholder-slate-500 focus:outline-none focus:ring-1 focus:ring-emerald-500 focus:border-emerald-500"
          onkeydown={handleKeydown}
        />
      </div>

      <!-- Options List -->
      <ul
        class="overflow-y-auto max-h-48"
        role="listbox"
      >
        {#if filteredTimezones.length === 0}
          <li class="px-3 py-2 text-sm text-slate-500">No timezones found</li>
        {:else}
          {#each filteredTimezones as tz, index}
            <li
              role="option"
              aria-selected={tz === value}
              class="px-3 py-2 text-sm cursor-pointer transition-colors {tz === value ? 'bg-emerald-600/20 text-emerald-400' : index === highlightedIndex ? 'bg-slate-700 text-slate-100' : 'text-slate-300 hover:bg-slate-700'}"
              onmousedown={(e) => { e.preventDefault(); selectTimezone(tz); }}
              onmouseenter={() => highlightedIndex = index}
            >
              <span class="font-mono text-xs">{formatTimezone(tz)}</span>
            </li>
          {/each}
        {/if}
      </ul>
    </div>
  {/if}
</div>
