<script lang="ts">
  import { page } from '$app/stores';
  import { authStore } from '$lib/stores/auth';
  import { goto } from '$app/navigation';
  import {
    IconDashboard,
    IconServer,
    IconHistory,
    IconCalendar,
    IconCalculator,
    IconShield,
    IconSettings,
    IconLogout,
    IconUser,
    IconMenu2,
    IconX
  } from '@tabler/icons-svelte';
  import clsx from 'clsx';
  import LogoOrbit from '$lib/components/ui/LogoOrbit.svelte';
  import { systemStore } from '$lib/stores/system';

  // Mobile sidebar state
  let isOpen = false;

  $: currentPath = $page.url.pathname;
  $: isAdmin = $authStore.user?.role === 'admin';

  // Close sidebar on route change (mobile)
  $: if (currentPath) {
    isOpen = false;
  }

  interface NavItem {
    label: string;
    href: string;
    icon: any;
    adminOnly?: boolean;
  }

  const navItems: NavItem[] = [
    { label: 'Dashboard', href: '/', icon: IconDashboard },
    { label: 'Resources', href: '/resources', icon: IconServer },
    { label: 'Executions', href: '/executions', icon: IconHistory },
    { label: 'Policies', href: '/policies', icon: IconCalendar },
    { label: 'Overrides', href: '/overrides', icon: IconShield },
    { label: 'Calculator', href: '/calculator', icon: IconCalculator },
    { label: 'Settings', href: '/settings', icon: IconSettings, adminOnly: true }
  ];

  function handleLogout() {
    if (confirm('Are you sure you want to logout?')) {
      authStore.logout();
      goto('/login');
    }
  }

  function isActive(href: string): boolean {
    if (href === '/') {
      return currentPath === '/';
    }
    return currentPath.startsWith(href);
  }

  function toggleSidebar() {
    isOpen = !isOpen;
  }

  function closeSidebar() {
    isOpen = false;
  }
</script>

<!-- Mobile Header Bar -->
<div class="lg:hidden fixed top-0 left-0 right-0 z-40 bg-slate-900 border-b border-slate-800 px-4 py-3 flex items-center justify-between">
  <div class="flex items-center gap-2">
    <div class="w-7 h-7 bg-slate-800 border border-slate-700 rounded flex items-center justify-center">
      <LogoOrbit className="w-3.5 h-3.5 text-emerald-500" />
    </div>
    <span class="text-sm font-semibold text-slate-100">CIS</span>
  </div>
  <button
    on:click={toggleSidebar}
    class="p-2 text-slate-400 hover:text-slate-200 hover:bg-slate-800 rounded transition-colors"
    aria-label="Toggle menu"
  >
    {#if isOpen}
      <IconX size={20} />
    {:else}
      <IconMenu2 size={20} />
    {/if}
  </button>
</div>

<!-- Mobile Overlay -->
{#if isOpen}
  <div
    class="lg:hidden fixed inset-0 z-40 bg-black/50"
    on:click={closeSidebar}
    on:keypress={(e) => e.key === 'Escape' && closeSidebar()}
    role="button"
    tabindex="0"
    aria-label="Close menu"
  />
{/if}

<!-- Sidebar -->
<aside
  class={clsx(
    'fixed lg:relative z-50 w-56 bg-slate-900 border-r border-slate-800 flex flex-col h-screen flex-shrink-0 transition-transform duration-200',
    'lg:translate-x-0',
    isOpen ? 'translate-x-0' : '-translate-x-full'
  )}
>
  <!-- Header (hidden on mobile, shown in mobile bar instead) -->
  <div class="hidden lg:block p-4 border-b border-slate-800">
    <div class="flex items-center gap-2">
      <div class="w-16 h-16 bg-slate-800 border border-slate-700 rounded-lg flex items-center justify-center p-2">
        <LogoOrbit className="w-full h-full text-emerald-500" />
      </div>
      <div>
        <h1 class="text-sm font-semibold text-slate-100 leading-tight">
          CIS
        </h1>
        <p class="text-[10px] text-slate-500 font-mono">{$systemStore.version ? `v${$systemStore.version}` : ''}</p>
      </div>
    </div>
  </div>

  <!-- Mobile close button area -->
  <div class="lg:hidden p-4 border-b border-slate-800 flex items-center justify-between">
    <span class="text-sm font-medium text-slate-400">Menu</span>
    <button
      on:click={closeSidebar}
      class="p-1 text-slate-400 hover:text-slate-200"
      aria-label="Close menu"
    >
      <IconX size={18} />
    </button>
  </div>

  <!-- Navigation -->
  <nav class="flex-1 p-3 space-y-1 overflow-y-auto">
    {#each navItems as item}
      {#if !item.adminOnly || isAdmin}
        <a
          href={item.href}
          on:click={closeSidebar}
          class={clsx(
            'flex items-center gap-3 px-3 py-2 rounded text-sm font-medium transition-colors',
            isActive(item.href)
              ? 'bg-slate-800 text-emerald-500 border border-slate-700'
              : 'text-slate-400 hover:text-slate-200 hover:bg-slate-800/50'
          )}
        >
          <svelte:component this={item.icon} size={18} stroke={1.5} />
          {item.label}
        </a>
      {/if}
    {/each}
  </nav>

  <!-- User Section -->
  <div class="p-3 border-t border-slate-800">
    {#if $authStore.user}
      <a
        href="/profile"
        on:click={closeSidebar}
        class="flex items-center gap-2.5 mb-3 px-2 py-1.5 rounded hover:bg-slate-800/50 transition-colors group"
      >
        <div
          class="w-8 h-8 rounded bg-slate-800 border border-slate-700 flex items-center justify-center flex-shrink-0"
        >
          <IconUser size={16} class="text-slate-400" />
        </div>
        <div class="flex-1 min-w-0">
          <p class="text-sm font-medium text-slate-200 truncate group-hover:text-emerald-400 transition-colors">
            {$authStore.user.full_name || $authStore.user.email.split('@')[0]}
          </p>
          <div class="flex items-center gap-1.5">
            <span
              class="inline-flex items-center px-1.5 py-0.5 rounded text-[10px] font-medium uppercase tracking-wider {$authStore.user.role === 'admin' ? 'bg-emerald-900/50 text-emerald-400 border border-emerald-800' : 'bg-slate-800 text-slate-400 border border-slate-700'}"
            >
              {$authStore.user.role}
            </span>
          </div>
        </div>
      </a>
    {/if}

    <button
      on:click={handleLogout}
      class="w-full flex items-center gap-2 px-3 py-2 text-sm font-medium text-slate-400 hover:text-red-400 hover:bg-red-900/20 rounded transition-colors"
    >
      <IconLogout size={18} stroke={1.5} />
      Logout
    </button>
  </div>
</aside>
