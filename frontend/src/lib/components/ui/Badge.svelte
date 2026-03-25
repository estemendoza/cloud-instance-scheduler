<script lang="ts">
  import clsx from 'clsx';
  import type { Snippet } from 'svelte';

  let {
    variant = 'neutral',
    size = 'md',
    class: className,
    children,
  }: {
    variant?: 'success' | 'warning' | 'danger' | 'info' | 'neutral';
    size?: 'sm' | 'md';
    class?: string;
    children?: Snippet;
  } = $props();

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

  const classes = $derived(clsx(
    baseClasses,
    variantClasses[variant],
    sizeClasses[size],
    className
  ));
</script>

<span class={classes}>
  {@render children?.()}
</span>
