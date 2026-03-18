<script lang="ts">
  import clsx from 'clsx';

  interface Option {
    value: string;
    label: string;
  }

  let {
    options = [],
    value = $bindable(''),
    placeholder = 'Select...',
    label = '',
    id = '',
    disabled = false,
    class: className,
    onchange,
  }: {
    options?: Option[];
    value?: string;
    placeholder?: string;
    label?: string;
    id?: string;
    disabled?: boolean;
    class?: string;
    onchange?: (e: Event) => void;
  } = $props();

  const baseClasses =
    'block w-full rounded-md border-gray-300 shadow-sm focus:ring-indigo-500 focus:border-indigo-500 sm:text-sm disabled:bg-gray-100 disabled:cursor-not-allowed';
</script>

<div class="w-full">
  {#if label}
    <label for={id} class="block text-sm font-medium text-gray-700 mb-1">
      {label}
    </label>
  {/if}

  <select {id} bind:value {disabled} class={clsx(baseClasses, className)} {onchange}>
    <option value="">{placeholder}</option>
    {#each options as option}
      <option value={option.value}>{option.label}</option>
    {/each}
  </select>
</div>
