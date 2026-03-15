<script lang="ts">
  import clsx from 'clsx';

  export let variant: 'success' | 'warning' | 'danger' | 'info' | 'neutral' = 'neutral';
  export let size: 'sm' | 'md' = 'md';

  const baseClasses = 'inline-flex items-center font-medium rounded-full';

  const variantClasses = {
    success: 'bg-green-100 text-green-800',
    warning: 'bg-yellow-100 text-yellow-800',
    danger: 'bg-red-100 text-red-800',
    info: 'bg-blue-100 text-blue-800',
    neutral: 'bg-gray-100 text-gray-800'
  };

  const sizeClasses = {
    sm: 'px-2 py-0.5 text-xs',
    md: 'px-2.5 py-0.5 text-sm'
  };

  $: classes = clsx(
    baseClasses,
    variantClasses[variant],
    sizeClasses[size],
    $$props.class
  );
</script>

<span class={classes}>
  <slot />
</span>
