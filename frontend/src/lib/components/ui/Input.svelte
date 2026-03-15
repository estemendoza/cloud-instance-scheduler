<script lang="ts">
  import clsx from 'clsx';

  export let type: 'text' | 'email' | 'password' | 'number' = 'text';
  export let value: string | number = '';
  export let placeholder = '';
  export let disabled = false;
  export let required = false;
  export let label = '';
  export let error = '';
  export let id = '';

  const baseClasses = 'block w-full rounded-md shadow-sm focus:ring-indigo-500 focus:border-indigo-500 sm:text-sm disabled:bg-gray-100 disabled:cursor-not-allowed';

  $: inputClasses = clsx(
    baseClasses,
    error ? 'border-red-300' : 'border-gray-300',
    $$props.class
  );
</script>

<div class="w-full">
  {#if label}
    <label for={id} class="block text-sm font-medium text-gray-700 mb-1">
      {label}
      {#if required}
        <span class="text-red-500">*</span>
      {/if}
    </label>
  {/if}

  {#if type === 'number'}
    <input
      {id}
      type="number"
      {placeholder}
      {disabled}
      {required}
      bind:value
      class={inputClasses}
      on:input
      on:change
      on:blur
    />
  {:else if type === 'email'}
    <input
      {id}
      type="email"
      {placeholder}
      {disabled}
      {required}
      bind:value
      class={inputClasses}
      on:input
      on:change
      on:blur
    />
  {:else if type === 'password'}
    <input
      {id}
      type="password"
      {placeholder}
      {disabled}
      {required}
      bind:value
      class={inputClasses}
      on:input
      on:change
      on:blur
    />
  {:else}
    <input
      {id}
      type="text"
      {placeholder}
      {disabled}
      {required}
      bind:value
      class={inputClasses}
      on:input
      on:change
      on:blur
    />
  {/if}

  {#if error}
    <p class="mt-1 text-sm text-red-600">{error}</p>
  {/if}
</div>
