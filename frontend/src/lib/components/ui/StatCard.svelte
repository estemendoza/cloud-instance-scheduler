<script lang="ts">
  import clsx from 'clsx';

  export let title: string;
  export let value: string | number;
  export let subtitle: string = '';
  export let trend: 'up' | 'down' | 'neutral' | null = null;
  export let loading: boolean = false;

  const trendColors = {
    up: 'text-green-600',
    down: 'text-red-600',
    neutral: 'text-gray-500'
  };
</script>

<div class="bg-white rounded-lg shadow p-6">
  <p class="text-sm font-medium text-gray-600">{title}</p>

  {#if loading}
    <div class="h-9 mt-2 bg-gray-200 rounded animate-pulse"></div>
  {:else}
    <p class="text-3xl font-bold text-gray-900 mt-2">{value}</p>
  {/if}

  {#if subtitle}
    <p class={clsx('text-xs mt-1', trend ? trendColors[trend] : 'text-gray-500')}>
      {subtitle}
    </p>
  {/if}
</div>
