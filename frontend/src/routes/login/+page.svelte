<script lang="ts">
  import { goto } from '$app/navigation';
  import { systemStore } from '$lib/stores/system';
  import { authAPI } from '$lib/api/endpoints/auth';
  import { mfaAPI } from '$lib/api/endpoints/mfa';
  import { authStore } from '$lib/stores/auth';
  import LogoOrbit from '$lib/components/ui/LogoOrbit.svelte';
  import type { TokenResponse, MfaRequiredResponse } from '$lib/types/user';

  let email = '';
  let password = '';
  let loading = false;
  let error = '';

  // MFA state
  let mfaToken = '';
  let mfaCode = '';
  let showMfaStep = false;

  function isMfaRequired(response: TokenResponse | MfaRequiredResponse): response is MfaRequiredResponse {
    return 'mfa_required' in response && response.mfa_required;
  }

  async function handleLogin() {
    error = '';
    loading = true;

    try {
      const response = await authAPI.login({ email, password });

      if (isMfaRequired(response)) {
        mfaToken = response.mfa_token;
        showMfaStep = true;
      } else {
        authStore.login(response);
        goto('/');
      }
    } catch (err: any) {
      if (err.status === 401) {
        error = 'Invalid email or password';
      } else {
        error = err.message || 'Login failed. Please try again.';
      }
    } finally {
      loading = false;
    }
  }

  async function handleMfaSubmit() {
    error = '';
    loading = true;

    try {
      const response = await mfaAPI.validate(mfaToken, mfaCode);
      authStore.login(response);
      goto('/');
    } catch (err: any) {
      if (err.status === 401) {
        error = 'Invalid verification code';
      } else {
        error = err.message || 'MFA verification failed';
      }
    } finally {
      loading = false;
    }
  }

  function backToLogin() {
    showMfaStep = false;
    mfaToken = '';
    mfaCode = '';
    error = '';
  }
</script>

<svelte:head>
  <title>Login - Cloud Instance Scheduler</title>
</svelte:head>

<div class="min-h-screen bg-slate-900 flex items-center justify-center p-4">
  <div class="w-full max-w-sm">
    <!-- Header -->
    <div class="text-center mb-8">
      <div class="inline-flex items-center justify-center w-20 h-20 bg-slate-800 border border-slate-700 rounded mb-4">
        <LogoOrbit className="w-12 h-12 text-emerald-500" />
      </div>
      <h1 class="text-xl font-semibold text-slate-100 tracking-tight">
        Cloud Instance Scheduler
      </h1>
      <p class="text-sm text-slate-500 mt-1 font-mono">{$systemStore.version ? `v${$systemStore.version}` : ''}</p>
    </div>

    <!-- Login Card -->
    <div class="bg-slate-800 border border-slate-700 rounded-lg p-6">
      <h2 class="text-sm font-medium text-slate-400 uppercase tracking-wider mb-6">
        {showMfaStep ? 'Two-Factor Authentication' : 'Authenticate'}
      </h2>

      {#if error}
        <div class="mb-4 p-3 bg-red-900/30 border border-red-800 rounded">
          <p class="text-sm text-red-400 font-mono">{error}</p>
        </div>
      {/if}

      {#if showMfaStep}
        <!-- MFA Step -->
        <form on:submit|preventDefault={handleMfaSubmit}>
          <div class="space-y-4">
            <p class="text-sm text-slate-400">
              Enter the 6-digit code from your authenticator app.
            </p>
            <div>
              <label for="mfaCode" class="block text-xs font-medium text-slate-400 uppercase tracking-wider mb-2">
                Verification Code
              </label>
              <input
                id="mfaCode"
                type="text"
                bind:value={mfaCode}
                placeholder="000000"
                required
                maxlength="6"
                pattern="[0-9]{6}"
                inputmode="numeric"
                autocomplete="one-time-code"
                disabled={loading}
                class="block w-full px-3 py-2 bg-slate-900 border border-slate-600 rounded text-slate-100 placeholder-slate-500 text-sm font-mono tracking-widest text-center focus:outline-none focus:ring-1 focus:ring-emerald-500 focus:border-emerald-500 disabled:opacity-50"
              />
            </div>

            <button
              type="submit"
              disabled={loading || mfaCode.length !== 6}
              class="w-full mt-2 px-4 py-2.5 bg-emerald-600 hover:bg-emerald-500 disabled:bg-emerald-800 text-white text-sm font-medium rounded transition-colors focus:outline-none focus:ring-2 focus:ring-emerald-500 focus:ring-offset-2 focus:ring-offset-slate-800 disabled:cursor-not-allowed"
            >
              {#if loading}
                <span class="inline-flex items-center justify-center">
                  <svg class="animate-spin -ml-1 mr-2 h-4 w-4 text-white" fill="none" viewBox="0 0 24 24">
                    <circle class="opacity-25" cx="12" cy="12" r="10" stroke="currentColor" stroke-width="4"></circle>
                    <path class="opacity-75" fill="currentColor" d="M4 12a8 8 0 018-8V0C5.373 0 0 5.373 0 12h4zm2 5.291A7.962 7.962 0 014 12H0c0 3.042 1.135 5.824 3 7.938l3-2.647z"></path>
                  </svg>
                  Verifying...
                </span>
              {:else}
                Verify
              {/if}
            </button>

            <button
              type="button"
              on:click={backToLogin}
              class="w-full text-sm text-slate-500 hover:text-slate-300 transition-colors"
            >
              Back to login
            </button>
          </div>
        </form>
      {:else}
        <!-- Login Step -->
        <form on:submit|preventDefault={handleLogin}>
          <div class="space-y-4">
            <div>
              <label for="email" class="block text-xs font-medium text-slate-400 uppercase tracking-wider mb-2">
                Email
              </label>
              <input
                id="email"
                type="email"
                bind:value={email}
                placeholder="admin@example.com"
                required
                disabled={loading}
                class="block w-full px-3 py-2 bg-slate-900 border border-slate-600 rounded text-slate-100 placeholder-slate-500 text-sm focus:outline-none focus:ring-1 focus:ring-emerald-500 focus:border-emerald-500 disabled:opacity-50"
              />
            </div>

            <div>
              <label for="password" class="block text-xs font-medium text-slate-400 uppercase tracking-wider mb-2">
                Password
              </label>
              <input
                id="password"
                type="password"
                bind:value={password}
                placeholder="••••••••"
                required
                disabled={loading}
                class="block w-full px-3 py-2 bg-slate-900 border border-slate-600 rounded text-slate-100 placeholder-slate-500 text-sm focus:outline-none focus:ring-1 focus:ring-emerald-500 focus:border-emerald-500 disabled:opacity-50"
              />
            </div>

            <button
              type="submit"
              disabled={loading}
              class="w-full mt-2 px-4 py-2.5 bg-emerald-600 hover:bg-emerald-500 disabled:bg-emerald-800 text-white text-sm font-medium rounded transition-colors focus:outline-none focus:ring-2 focus:ring-emerald-500 focus:ring-offset-2 focus:ring-offset-slate-800 disabled:cursor-not-allowed"
            >
              {#if loading}
                <span class="inline-flex items-center">
                  <svg class="animate-spin -ml-1 mr-2 h-4 w-4 text-white" fill="none" viewBox="0 0 24 24">
                    <circle class="opacity-25" cx="12" cy="12" r="10" stroke="currentColor" stroke-width="4"></circle>
                    <path class="opacity-75" fill="currentColor" d="M4 12a8 8 0 018-8V0C5.373 0 0 5.373 0 12h4zm2 5.291A7.962 7.962 0 014 12H0c0 3.042 1.135 5.824 3 7.938l3-2.647z"></path>
                  </svg>
                  Authenticating...
                </span>
              {:else}
                Sign In
              {/if}
            </button>
          </div>
        </form>
      {/if}
    </div>

    <!-- Footer -->
    <p class="text-center text-xs text-slate-600 mt-6">
      Secure access to infrastructure management
    </p>
  </div>
</div>
