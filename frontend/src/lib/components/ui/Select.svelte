<script lang="ts">
  import clsx from 'clsx';

  interface Option {
    value: string;
    label: string;
  }

  export let options: Option[] = [];
  export let value: string = '';
  export let placeholder: string = 'Select...';
  export let label: string = '';
  export let id: string = '';
  export let disabled: boolean = false;

  const baseClasses =
    'block w-full rounded-md border-gray-300 shadow-sm focus:ring-indigo-500 focus:border-indigo-500 sm:text-sm disabled:bg-gray-100 disabled:cursor-not-allowed';
</script>

<div class="w-full">
  {#if label}
    <label for={id} class="block text-sm font-medium text-gray-700 mb-1">
      {label}
    </label>
  {/if}

  <select {id} bind:value {disabled} class={clsx(baseClasses, $$props.class)} on:change>
    <option value="">{placeholder}</option>
    {#each options as option}
      <option value={option.value}>{option.label}</option>
    {/each}
  </select>
</div>
