<script lang="ts">
  import clsx from 'clsx';

  let {
    type = 'text',
    value = $bindable(''),
    placeholder = '',
    disabled = false,
    required = false,
    label = '',
    error = '',
    id = '',
    class: className,
    oninput,
    onchange,
    onblur,
  }: {
    type?: 'text' | 'email' | 'password' | 'number';
    value?: string | number;
    placeholder?: string;
    disabled?: boolean;
    required?: boolean;
    label?: string;
    error?: string;
    id?: string;
    class?: string;
    oninput?: (_e: Event) => void;
    onchange?: (_e: Event) => void;
    onblur?: (_e: FocusEvent) => void;
  } = $props();

  const baseClasses = 'block w-full rounded-md shadow-sm focus:ring-indigo-500 focus:border-indigo-500 sm:text-sm disabled:bg-gray-100 disabled:cursor-not-allowed';

  const inputClasses = $derived(clsx(
    baseClasses,
    error ? 'border-red-300' : 'border-gray-300',
    className
  ));
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
      {oninput}
      {onchange}
      {onblur}
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
      {oninput}
      {onchange}
      {onblur}
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
      {oninput}
      {onchange}
      {onblur}
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
      {oninput}
      {onchange}
      {onblur}
    />
  {/if}

  {#if error}
    <p class="mt-1 text-sm text-red-600">{error}</p>
  {/if}
</div>
