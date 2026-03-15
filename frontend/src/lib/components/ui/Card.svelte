<script lang="ts">
  import clsx from 'clsx';

  export let title = '';
  export let padding = true;

  const baseClasses = 'bg-white rounded-lg shadow';

  $: classes = clsx(
    baseClasses,
    padding && 'p-6',
    $$props.class
  );
</script>

<div class={classes}>
  {#if title}
    <h3 class="text-lg font-medium text-gray-900 mb-4">
      {title}
    </h3>
  {/if}

  <slot />
</div>
