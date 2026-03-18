<script lang="ts">
  import { IconCheck, IconX } from '@tabler/icons-svelte';
  import Badge from './Badge.svelte';
  import clsx from 'clsx';

  interface TimelineItem {
    id: string;
    action: string;
    success: boolean;
    error_message: string | null;
    executed_at: string;
    desired_state: string;
    actual_state_before: string;
  }

  let {
    items = [],
    loading = false,
  }: {
    items?: TimelineItem[];
    loading?: boolean;
  } = $props();

  function formatDate(isoDate: string): string {
    return new Date(isoDate).toLocaleString();
  }
</script>

<div class="flow-root">
  {#if loading}
    <div class="space-y-4">
      {#each Array(3) as _}
        <div class="h-16 bg-gray-200 rounded animate-pulse"></div>
      {/each}
    </div>
  {:else if items.length === 0}
    <p class="text-gray-500 text-center py-4">No execution history</p>
  {:else}
    <ul class="-mb-8">
      {#each items as item, index}
        <li>
          <div class="relative pb-8">
            {#if index !== items.length - 1}
              <span class="absolute top-4 left-4 -ml-px h-full w-0.5 bg-gray-200"></span>
            {/if}
            <div class="relative flex space-x-3">
              <div>
                <span
                  class={clsx(
                    'h-8 w-8 rounded-full flex items-center justify-center ring-8 ring-white',
                    item.success ? 'bg-green-500' : 'bg-red-500'
                  )}
                >
                  {#if item.success}
                    <IconCheck size={16} class="text-white" />
                  {:else}
                    <IconX size={16} class="text-white" />
                  {/if}
                </span>
              </div>
              <div class="min-w-0 flex-1">
                <div class="flex items-center gap-2">
                  <Badge variant={item.success ? 'success' : 'danger'}>
                    {item.action}
                  </Badge>
                  <span class="text-sm text-gray-500">
                    {item.actual_state_before} → {item.desired_state}
                  </span>
                </div>
                <p class="text-xs text-gray-500 mt-1">
                  {formatDate(item.executed_at)}
                </p>
                {#if item.error_message}
                  <p class="text-xs text-red-600 mt-1">{item.error_message}</p>
                {/if}
              </div>
            </div>
          </div>
        </li>
      {/each}
    </ul>
  {/if}
</div>
