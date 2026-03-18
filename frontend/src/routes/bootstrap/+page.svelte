<script lang="ts">
  import { goto } from '$app/navigation';
  import { organizationsAPI } from '$lib/api/endpoints/organizations';
  import { usersAPI } from '$lib/api/endpoints/users';
  import { authAPI } from '$lib/api/endpoints/auth';
  import { authStore } from '$lib/stores/auth';
  import LogoOrbit from '$lib/components/ui/LogoOrbit.svelte';
  import type { Organization } from '$lib/types/organization';

  let step = $state(1);
  let loading = $state(false);
  let error = $state('');

  // Step 1: Organization
  let orgName = $state('');
  let orgSlug = $state('');
  let createdOrg = $state<Organization | null>(null);

  // Step 2: User
  let userEmail = $state('');
  let userPassword = $state('');
  let userFullName = $state('');
  let createdUserId = $state('');

  // Auto-generate slug from name
  $effect(() => {
    if (orgName) {
      orgSlug = orgName
        .toLowerCase()
        .replace(/[^a-z0-9]+/g, '-')
        .replace(/^-|-$/g, '');
    }
  });

  async function createOrganization() {
    error = '';
    loading = true;

    try {
      createdOrg = await organizationsAPI.create({
        name: orgName,
        slug: orgSlug
      });

      step = 2;
    } catch (err: any) {
      error = err.message || 'Failed to create organization';
    } finally {
      loading = false;
    }
  }

  async function createUser() {
    if (!createdOrg) return;

    error = '';
    loading = true;

    try {
      const user = await usersAPI.create({
        email: userEmail,
        password: userPassword,
        full_name: userFullName || undefined,
        role: 'admin',
        organization_id: createdOrg.id
      });

      createdUserId = user.id;
      step = 3;
    } catch (err: any) {
      error = err.message || 'Failed to create user';
    } finally {
      loading = false;
    }
  }

  async function completeSetup() {
    if (!createdUserId) return;

    error = '';
    loading = true;

    try {
      // Get JWT tokens via bootstrap endpoint
      const tokenResponse = await authAPI.bootstrap(createdUserId);

      // Store tokens and user data
      authStore.login(tokenResponse);

      // Redirect to dashboard
      goto('/');
    } catch (err: any) {
      error = err.message || 'Failed to complete setup';
    } finally {
      loading = false;
    }
  }

  const stepLabels = ['Organization', 'Admin User', 'Complete'];
</script>

<svelte:head>
  <title>Bootstrap - Cloud Instance Scheduler</title>
</svelte:head>

<div class="min-h-screen bg-slate-900 flex items-center justify-center p-4">
  <div class="w-full max-w-md">
    <!-- Header -->
    <div class="text-center mb-8">
      <div class="inline-flex items-center justify-center w-12 h-12 bg-slate-800 border border-slate-700 rounded mb-4">
        <LogoOrbit className="w-6 h-6 text-emerald-500" />
      </div>
      <h1 class="text-xl font-semibold text-slate-100 tracking-tight">
        Cloud Instance Scheduler
      </h1>
      <p class="text-sm text-slate-500 mt-1">Initial Setup</p>
    </div>

    <!-- Progress Indicator -->
    <div class="flex items-center justify-between mb-6 px-4">
      {#each [1, 2, 3] as s, i}
        <div class="flex items-center">
          <div class="flex flex-col items-center">
            <div
              class="w-8 h-8 rounded flex items-center justify-center text-xs font-mono font-medium border {step >= s
                ? 'bg-emerald-600 border-emerald-500 text-white'
                : 'bg-slate-800 border-slate-700 text-slate-500'}"
            >
              {s}
            </div>
            <span class="text-xs text-slate-500 mt-1.5 font-mono">{stepLabels[i]}</span>
          </div>
          {#if s < 3}
            <div
              class="w-16 h-px mx-3 mb-5 {step > s ? 'bg-emerald-600' : 'bg-slate-700'}"
            />
          {/if}
        </div>
      {/each}
    </div>

    <!-- Main Card -->
    <div class="bg-slate-800 border border-slate-700 rounded-lg p-6">
      {#if error}
        <div class="mb-4 p-3 bg-red-900/30 border border-red-800 rounded">
          <p class="text-sm text-red-400 font-mono">{error}</p>
        </div>
      {/if}

      <!-- Step 1: Create Organization -->
      {#if step === 1}
        <div>
          <h2 class="text-sm font-medium text-slate-400 uppercase tracking-wider mb-6">
            Create Organization
          </h2>

          <form onsubmit={(e) => { e.preventDefault(); createOrganization(); }}>
            <div class="space-y-4">
              <div>
                <label for="org-name" class="block text-xs font-medium text-slate-400 uppercase tracking-wider mb-2">
                  Organization Name
                </label>
                <input
                  id="org-name"
                  type="text"
                  bind:value={orgName}
                  placeholder="My Company"
                  required
                  disabled={loading}
                  class="block w-full px-3 py-2 bg-slate-900 border border-slate-600 rounded text-slate-100 placeholder-slate-500 text-sm focus:outline-none focus:ring-1 focus:ring-emerald-500 focus:border-emerald-500 disabled:opacity-50"
                />
              </div>

              <div>
                <label for="org-slug" class="block text-xs font-medium text-slate-400 uppercase tracking-wider mb-2">
                  Organization Slug
                </label>
                <input
                  id="org-slug"
                  type="text"
                  bind:value={orgSlug}
                  placeholder="my-company"
                  required
                  disabled={loading}
                  class="block w-full px-3 py-2 bg-slate-900 border border-slate-600 rounded text-slate-100 placeholder-slate-500 text-sm font-mono focus:outline-none focus:ring-1 focus:ring-emerald-500 focus:border-emerald-500 disabled:opacity-50"
                />
                <p class="text-xs text-slate-500 mt-1.5">Used in URLs. Must be unique.</p>
              </div>

              <button
                type="submit"
                disabled={loading}
                class="w-full mt-2 px-4 py-2.5 bg-emerald-600 hover:bg-emerald-500 disabled:bg-emerald-800 text-white text-sm font-medium rounded transition-colors focus:outline-none focus:ring-2 focus:ring-emerald-500 focus:ring-offset-2 focus:ring-offset-slate-800 disabled:cursor-not-allowed"
              >
                {loading ? 'Creating...' : 'Continue'}
              </button>
            </div>
          </form>
        </div>
      {/if}

      <!-- Step 2: Create User -->
      {#if step === 2}
        <div>
          <h2 class="text-sm font-medium text-slate-400 uppercase tracking-wider mb-6">
            Create Admin User
          </h2>

          <form onsubmit={(e) => { e.preventDefault(); createUser(); }}>
            <div class="space-y-4">
              <div>
                <label for="user-email" class="block text-xs font-medium text-slate-400 uppercase tracking-wider mb-2">
                  Email
                </label>
                <input
                  id="user-email"
                  type="email"
                  bind:value={userEmail}
                  placeholder="admin@example.com"
                  required
                  disabled={loading}
                  class="block w-full px-3 py-2 bg-slate-900 border border-slate-600 rounded text-slate-100 placeholder-slate-500 text-sm focus:outline-none focus:ring-1 focus:ring-emerald-500 focus:border-emerald-500 disabled:opacity-50"
                />
              </div>

              <div>
                <label for="user-password" class="block text-xs font-medium text-slate-400 uppercase tracking-wider mb-2">
                  Password
                </label>
                <input
                  id="user-password"
                  type="password"
                  bind:value={userPassword}
                  placeholder="••••••••"
                  required
                  disabled={loading}
                  class="block w-full px-3 py-2 bg-slate-900 border border-slate-600 rounded text-slate-100 placeholder-slate-500 text-sm focus:outline-none focus:ring-1 focus:ring-emerald-500 focus:border-emerald-500 disabled:opacity-50"
                />
              </div>

              <div>
                <label for="user-fullname" class="block text-xs font-medium text-slate-400 uppercase tracking-wider mb-2">
                  Full Name <span class="text-slate-600">(optional)</span>
                </label>
                <input
                  id="user-fullname"
                  type="text"
                  bind:value={userFullName}
                  placeholder="John Doe"
                  disabled={loading}
                  class="block w-full px-3 py-2 bg-slate-900 border border-slate-600 rounded text-slate-100 placeholder-slate-500 text-sm focus:outline-none focus:ring-1 focus:ring-emerald-500 focus:border-emerald-500 disabled:opacity-50"
                />
              </div>

              <p class="text-xs text-slate-500">
                This user will have admin privileges.
              </p>

              <button
                type="submit"
                disabled={loading}
                class="w-full mt-2 px-4 py-2.5 bg-emerald-600 hover:bg-emerald-500 disabled:bg-emerald-800 text-white text-sm font-medium rounded transition-colors focus:outline-none focus:ring-2 focus:ring-emerald-500 focus:ring-offset-2 focus:ring-offset-slate-800 disabled:cursor-not-allowed"
              >
                {loading ? 'Creating...' : 'Continue'}
              </button>
            </div>
          </form>
        </div>
      {/if}

      <!-- Step 3: Complete Setup -->
      {#if step === 3}
        <div>
          <h2 class="text-sm font-medium text-slate-400 uppercase tracking-wider mb-6">
            Complete Setup
          </h2>

          <div class="mb-6 p-4 bg-emerald-900/20 border border-emerald-800 rounded">
            <div class="flex items-start gap-3">
              <svg class="w-5 h-5 text-emerald-500 mt-0.5 flex-shrink-0" fill="none" viewBox="0 0 24 24" stroke="currentColor" stroke-width="2">
                <path stroke-linecap="round" stroke-linejoin="round" d="M9 12l2 2 4-4m6 2a9 9 0 11-18 0 9 9 0 0118 0z" />
              </svg>
              <div>
                <p class="text-sm text-emerald-400 font-medium">
                  Organization and user created successfully
                </p>
                <p class="text-xs text-emerald-500/80 mt-1">
                  Click below to complete setup and access your dashboard.
                </p>
              </div>
            </div>
          </div>

          <p class="text-slate-400 text-sm mb-6">
            You can create API keys later from the Settings page for programmatic access.
          </p>

          <button
            onclick={completeSetup}
            disabled={loading}
            class="w-full px-4 py-2.5 bg-emerald-600 hover:bg-emerald-500 disabled:bg-emerald-800 text-white text-sm font-medium rounded transition-colors focus:outline-none focus:ring-2 focus:ring-emerald-500 focus:ring-offset-2 focus:ring-offset-slate-800 disabled:cursor-not-allowed"
          >
            {#if loading}
              <span class="inline-flex items-center">
                <svg class="animate-spin -ml-1 mr-2 h-4 w-4 text-white" fill="none" viewBox="0 0 24 24">
                  <circle class="opacity-25" cx="12" cy="12" r="10" stroke="currentColor" stroke-width="4"></circle>
                  <path class="opacity-75" fill="currentColor" d="M4 12a8 8 0 018-8V0C5.373 0 0 5.373 0 12h4zm2 5.291A7.962 7.962 0 014 12H0c0 3.042 1.135 5.824 3 7.938l3-2.647z"></path>
                </svg>
                Completing setup...
              </span>
            {:else}
              Go to Dashboard
            {/if}
          </button>
        </div>
      {/if}
    </div>

    <!-- Footer -->
    <p class="text-center text-xs text-slate-600 mt-6">
      Initial system configuration
    </p>
  </div>
</div>
