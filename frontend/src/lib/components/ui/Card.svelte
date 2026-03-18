<script lang="ts">
  import clsx from 'clsx';
  import type { Snippet } from 'svelte';

  let {
    title = '',
    padding = true,
    class: className,
    children,
  }: {
    title?: string;
    padding?: boolean;
    class?: string;
    children?: Snippet;
  } = $props();

  const baseClasses = 'bg-white rounded-lg shadow';

  const classes = $derived(clsx(
    baseClasses,
    padding && 'p-6',
    className
  ));
</script>

<div class={classes}>
  {#if title}
    <h3 class="text-lg font-medium text-gray-900 mb-4">
      {title}
    </h3>
  {/if}

  {@render children?.()}
</div>
