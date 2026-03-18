<script lang="ts">
  import { onMount } from 'svelte';
  import { authStore } from '$lib/stores/auth';
  import { usersAPI } from '$lib/api/endpoints/users';
  import { mfaAPI } from '$lib/api/endpoints/mfa';
  import { notify } from '$lib/utils/toast';
  import Sidebar from '$lib/components/layout/Sidebar.svelte';
  import { apiKeysAPI } from '$lib/api/endpoints/apiKeys';
  import type { APIKey, APIKeyCreated } from '$lib/types/apiKey';
  import {
    IconUser,
    IconLock,
    IconShieldLock,
    IconKey,
    IconPlus,
    IconTrash,
    IconCopy,
    IconCheck,
    IconX,
    IconAlertTriangle,
  } from '@tabler/icons-svelte';
  import type { MfaSetupResponse } from '$lib/types/user';
  import QRCode from 'qrcode';

  // Tabs
  type TabId = 'profile' | 'password' | 'security' | 'api-keys';

  interface Tab {
    id: TabId;
    label: string;
    icon: any;
  }

  const tabs: Tab[] = [
    { id: 'profile', label: 'Profile', icon: IconUser },
    { id: 'password', label: 'Password', icon: IconLock },
    { id: 'security', label: 'Security', icon: IconShieldLock },
    { id: 'api-keys', label: 'API Keys', icon: IconKey },
  ];

  let activeTab = $state<TabId>('profile');

  // Profile state
  let fullName = $state($authStore.user?.full_name || '');
  let profileLoading = $state(false);

  // Password state
  let currentPassword = $state('');
  let newPassword = $state('');
  let confirmPassword = $state('');
  let passwordLoading = $state(false);

  // MFA state
  let mfaEnabled = $state(false);
  let mfaLoading = $state(false);
  let mfaSetupData = $state<MfaSetupResponse | null>(null);
  let mfaVerifyCode = $state('');
  let mfaDisablePassword = $state('');
  let mfaDisableCode = $state('');
  let showDisableForm = $state(false);

  $effect(() => { mfaVerifyCode = mfaVerifyCode.replace(/\D/g, '').slice(0, 6); });
  $effect(() => { mfaDisableCode = mfaDisableCode.replace(/\D/g, '').slice(0, 6); });
  let secretCopied = $state(false);

  // API Keys state
  let apiKeys = $state<APIKey[]>([]);
  let apiKeysLoading = $state(false);
  let apiKeysLoaded = $state(false);
  let showApiKeyModal = $state(false);
  let newKeyName = $state('');
  let newKeyLoading = $state(false);
  let createdKey = $state<APIKeyCreated | null>(null);
  let deleteConfirmKeyId = $state<string | null>(null);
  let keyCopied = $state(false);

  onMount(async () => {
    try {
      const status = await mfaAPI.status();
      mfaEnabled = status.enabled;
    } catch {
      // Ignore — MFA status fetch is best-effort
    }
  });

  async function handleProfileUpdate() {
    profileLoading = true;
    try {
      const updated = await usersAPI.updateProfile({ full_name: fullName });
      authStore.setUser(updated);
      notify.success('Profile updated');
    } catch (err: any) {
      notify.error(err.message || 'Failed to update profile');
    } finally {
      profileLoading = false;
    }
  }

  async function handlePasswordChange() {
    if (newPassword !== confirmPassword) {
      notify.error('Passwords do not match');
      return;
    }
    if (newPassword.length < 8) {
      notify.error('Password must be at least 8 characters');
      return;
    }
    passwordLoading = true;
    try {
      await usersAPI.changePassword({
        current_password: currentPassword,
        new_password: newPassword,
      });
      notify.success('Password changed successfully');
      currentPassword = '';
      newPassword = '';
      confirmPassword = '';
    } catch (err: any) {
      notify.error(err.message || 'Failed to change password');
    } finally {
      passwordLoading = false;
    }
  }

  async function handleMfaSetup() {
    mfaLoading = true;
    try {
      mfaSetupData = await mfaAPI.setup();
    } catch (err: any) {
      notify.error(err.message || 'Failed to start MFA setup');
    } finally {
      mfaLoading = false;
    }
  }

  async function handleMfaVerify() {
    mfaLoading = true;
    try {
      await mfaAPI.verify(mfaVerifyCode);
      mfaEnabled = true;
      mfaSetupData = null;
      mfaVerifyCode = '';
      notify.success('MFA enabled successfully');
    } catch (err: any) {
      notify.error(err.message || 'Invalid verification code');
    } finally {
      mfaLoading = false;
    }
  }

  async function handleMfaDisable() {
    mfaLoading = true;
    try {
      await mfaAPI.disable(mfaDisablePassword, mfaDisableCode);
      mfaEnabled = false;
      showDisableForm = false;
      mfaDisablePassword = '';
      mfaDisableCode = '';
      notify.success('MFA disabled');
    } catch (err: any) {
      notify.error(err.message || 'Failed to disable MFA');
    } finally {
      mfaLoading = false;
    }
  }

  function cancelMfaSetup() {
    mfaSetupData = null;
    mfaVerifyCode = '';
  }

  // API Keys functions
  async function loadApiKeys() {
    apiKeysLoading = true;
    try {
      apiKeys = await apiKeysAPI.list();
    } catch (err: any) {
      notify.error(err.message || 'Failed to load API keys');
    } finally {
      apiKeysLoading = false;
      apiKeysLoaded = true;
    }
  }

  function openApiKeyModal() {
    newKeyName = '';
    createdKey = null;
    keyCopied = false;
    showApiKeyModal = true;
  }

  function closeApiKeyModal() {
    showApiKeyModal = false;
    createdKey = null;
    newKeyName = '';
    keyCopied = false;
  }

  async function createApiKey() {
    if (!newKeyName.trim()) {
      notify.error('Name is required');
      return;
    }
    newKeyLoading = true;
    try {
      createdKey = await apiKeysAPI.create({ name: newKeyName.trim() });
      await loadApiKeys();
    } catch (err: any) {
      notify.error(err.message || 'Failed to create API key');
    } finally {
      newKeyLoading = false;
    }
  }

  async function deleteApiKey(keyId: string) {
    try {
      await apiKeysAPI.delete(keyId);
      notify.success('API key revoked');
      await loadApiKeys();
    } catch (err: any) {
      notify.error(err.message || 'Failed to revoke API key');
    }
    deleteConfirmKeyId = null;
  }

  function copyKey() {
    if (createdKey) {
      navigator.clipboard.writeText(createdKey.key);
      keyCopied = true;
      notify.success('Copied to clipboard');
      setTimeout(() => keyCopied = false, 2000);
    }
  }

  function formatKeyDate(date: string | null): string {
    if (!date) return 'Never';
    const d = new Date(date);
    const now = new Date();
    const diff = now.getTime() - d.getTime();
    const minutes = Math.floor(diff / 60000);
    if (minutes < 1) return 'Just now';
    if (minutes < 60) return `${minutes}m ago`;
    const hours = Math.floor(minutes / 60);
    if (hours < 24) return `${hours}h ago`;
    const days = Math.floor(hours / 24);
    return `${days}d ago`;
  }

  // Load API keys when switching to that tab
  $effect(() => {
    if (activeTab === 'api-keys' && !apiKeysLoaded && !apiKeysLoading) {
      loadApiKeys();
    }
  });

  let qrDataUrl = $state('');

  $effect(() => {
    if (mfaSetupData?.provisioning_uri) {
      QRCode.toDataURL(mfaSetupData.provisioning_uri, {
        width: 200,
        margin: 2,
        color: { dark: '#000000', light: '#ffffff' }
      }).then(url => { qrDataUrl = url; });
    } else {
      qrDataUrl = '';
    }
  });

  async function copySecret() {
    if (mfaSetupData) {
      await navigator.clipboard.writeText(mfaSetupData.secret);
      secretCopied = true;
      setTimeout(() => { secretCopied = false; }, 2000);
    }
  }
</script>

<svelte:head>
  <title>Profile - CIS</title>
</svelte:head>

<div class="flex h-screen bg-slate-900">
  <Sidebar />

  <main class="flex-1 overflow-auto pt-14 lg:pt-0">
    <div class="p-6">
      <!-- Header -->
      <div class="mb-6">
        <h1 class="text-xl font-semibold text-slate-100">Profile</h1>
        <p class="text-sm text-slate-500 mt-1">Manage your account settings</p>
      </div>

      <!-- Tabs -->
      <div class="flex items-center gap-1 mb-6 border-b border-slate-800 overflow-x-auto">
        {#each tabs as tab}
          <button
            onclick={() => activeTab = tab.id}
            class="flex items-center gap-2 px-4 py-2.5 text-sm font-medium whitespace-nowrap transition-colors border-b-2 -mb-px {activeTab === tab.id
              ? 'text-emerald-500 border-emerald-500'
              : 'text-slate-400 border-transparent hover:text-slate-200 hover:border-slate-600'}"
          >
            <svelte:component this={tab.icon} size={16} stroke={1.5} />
            {tab.label}
          </button>
        {/each}
      </div>

      <!-- Tab Content -->
      {#if activeTab === 'profile'}
        <!-- Profile Tab -->
        <div class="max-w-xl">
          <h2 class="text-sm font-medium text-slate-300 uppercase tracking-wider mb-4">Profile Information</h2>

          <div class="space-y-4">
            <!-- Email (read-only) -->
            <div>
              <label for="profileEmail" class="block text-xs font-medium text-slate-400 uppercase tracking-wider mb-1.5">Email</label>
              <input
                id="profileEmail"
                type="email"
                value={$authStore.user?.email}
                disabled
                class="w-full px-3 py-2 bg-slate-900 border border-slate-700 rounded text-slate-400 text-sm cursor-not-allowed"
              />
            </div>

            <!-- Role (read-only) -->
            <div>
              <label for="profileRole" class="block text-xs font-medium text-slate-400 uppercase tracking-wider mb-1.5">Role</label>
              <span class="inline-flex items-center px-2 py-1 rounded text-xs font-medium uppercase tracking-wider {$authStore.user?.role === 'admin' ? 'bg-emerald-900/50 text-emerald-400 border border-emerald-800' : 'bg-slate-700 text-slate-300 border border-slate-600'}">
                {$authStore.user?.role}
              </span>
            </div>

            <!-- Organization (read-only) -->
            {#if $authStore.user?.organization}
              <div>
                <label for="profileOrg" class="block text-xs font-medium text-slate-400 uppercase tracking-wider mb-1.5">Organization</label>
                <input
                  id="profileOrg"
                  type="text"
                  value={$authStore.user.organization.name}
                  disabled
                  class="w-full px-3 py-2 bg-slate-900 border border-slate-700 rounded text-slate-400 text-sm cursor-not-allowed"
                />
              </div>
            {/if}

            <!-- Full Name (editable) -->
            <form onsubmit={(e) => { e.preventDefault(); handleProfileUpdate(); }}>
              <label for="fullName" class="block text-xs font-medium text-slate-400 uppercase tracking-wider mb-1.5">Full Name</label>
              <div class="flex gap-3">
                <input
                  id="fullName"
                  type="text"
                  bind:value={fullName}
                  placeholder="Your full name"
                  class="flex-1 px-3 py-2 bg-slate-900 border border-slate-600 rounded text-slate-100 placeholder-slate-500 text-sm focus:outline-none focus:ring-1 focus:ring-emerald-500 focus:border-emerald-500"
                />
                <button
                  type="submit"
                  disabled={profileLoading}
                  class="px-4 py-2 bg-emerald-600 hover:bg-emerald-500 disabled:bg-emerald-800 text-white text-sm font-medium rounded transition-colors disabled:cursor-not-allowed"
                >
                  {profileLoading ? 'Saving...' : 'Save'}
                </button>
              </div>
            </form>
          </div>
        </div>

      {:else if activeTab === 'password'}
        <!-- Password Tab -->
        <div class="max-w-xl">
          <h2 class="text-sm font-medium text-slate-300 uppercase tracking-wider mb-4">Change Password</h2>

          <form onsubmit={(e) => { e.preventDefault(); handlePasswordChange(); }} class="space-y-4">
            <div>
              <label for="currentPassword" class="block text-xs font-medium text-slate-400 uppercase tracking-wider mb-1.5">Current Password</label>
              <input
                id="currentPassword"
                type="password"
                bind:value={currentPassword}
                required
                class="w-full px-3 py-2 bg-slate-900 border border-slate-600 rounded text-slate-100 placeholder-slate-500 text-sm focus:outline-none focus:ring-1 focus:ring-emerald-500 focus:border-emerald-500"
              />
            </div>

            <div>
              <label for="newPassword" class="block text-xs font-medium text-slate-400 uppercase tracking-wider mb-1.5">New Password</label>
              <input
                id="newPassword"
                type="password"
                bind:value={newPassword}
                required
                minlength="8"
                class="w-full px-3 py-2 bg-slate-900 border border-slate-600 rounded text-slate-100 placeholder-slate-500 text-sm focus:outline-none focus:ring-1 focus:ring-emerald-500 focus:border-emerald-500"
              />
              <p class="text-xs text-slate-500 mt-1">Minimum 8 characters</p>
            </div>

            <div>
              <label for="confirmPassword" class="block text-xs font-medium text-slate-400 uppercase tracking-wider mb-1.5">Confirm New Password</label>
              <input
                id="confirmPassword"
                type="password"
                bind:value={confirmPassword}
                required
                minlength="8"
                class="w-full px-3 py-2 bg-slate-900 border border-slate-600 rounded text-slate-100 placeholder-slate-500 text-sm focus:outline-none focus:ring-1 focus:ring-emerald-500 focus:border-emerald-500"
              />
            </div>

            <button
              type="submit"
              disabled={passwordLoading || !currentPassword || !newPassword || !confirmPassword}
              class="px-4 py-2 bg-emerald-600 hover:bg-emerald-500 disabled:bg-emerald-800 text-white text-sm font-medium rounded transition-colors disabled:cursor-not-allowed"
            >
              {passwordLoading ? 'Changing...' : 'Change Password'}
            </button>
          </form>
        </div>

      {:else if activeTab === 'security'}
        <!-- Security Tab -->
        <div class="max-w-xl">
          <h2 class="text-sm font-medium text-slate-300 uppercase tracking-wider mb-4">Two-Factor Authentication</h2>

          {#if mfaEnabled && !showDisableForm}
            <!-- MFA is enabled -->
            <div class="bg-slate-800 border border-slate-700 rounded-lg p-5">
              <div class="flex items-center justify-between">
                <div class="flex items-center gap-3">
                  <div class="w-10 h-10 rounded-lg bg-emerald-900/30 border border-emerald-800 flex items-center justify-center">
                    <IconShieldLock size={20} class="text-emerald-400" />
                  </div>
                  <div>
                    <p class="text-sm font-medium text-slate-200">TOTP Authenticator</p>
                    <span class="inline-flex items-center px-1.5 py-0.5 rounded text-[10px] font-medium uppercase tracking-wider bg-emerald-900/50 text-emerald-400 border border-emerald-800">
                      Enabled
                    </span>
                  </div>
                </div>
                <button
                  onclick={() => { showDisableForm = true; }}
                  class="px-3 py-1.5 text-sm font-medium text-red-400 hover:text-red-300 hover:bg-red-900/20 border border-red-800/50 rounded transition-colors"
                >
                  Disable
                </button>
              </div>
            </div>

          {:else if mfaEnabled && showDisableForm}
            <!-- Disable MFA form -->
            <div class="bg-slate-800 border border-slate-700 rounded-lg p-5">
              <p class="text-sm text-slate-400 mb-4">Enter your password and a current TOTP code to disable MFA.</p>

              <form onsubmit={(e) => { e.preventDefault(); handleMfaDisable(); }} class="space-y-4">
                <div>
                  <label for="mfaDisablePassword" class="block text-xs font-medium text-slate-400 uppercase tracking-wider mb-1.5">Password</label>
                  <input
                    id="mfaDisablePassword"
                    type="password"
                    bind:value={mfaDisablePassword}
                    required
                    class="w-full px-3 py-2 bg-slate-900 border border-slate-600 rounded text-slate-100 text-sm focus:outline-none focus:ring-1 focus:ring-emerald-500 focus:border-emerald-500"
                  />
                </div>

                <div>
                  <label for="mfaDisableCode" class="block text-xs font-medium text-slate-400 uppercase tracking-wider mb-1.5">TOTP Code</label>
                  <input
                    id="mfaDisableCode"
                    type="text"
                    bind:value={mfaDisableCode}
                    required
                    maxlength="6"

                    placeholder="000000"
                    inputmode="numeric"
                    autocomplete="one-time-code"
                    class="w-48 px-3 py-2 bg-slate-900 border border-slate-600 rounded text-slate-100 text-sm font-mono tracking-widest focus:outline-none focus:ring-1 focus:ring-emerald-500 focus:border-emerald-500"
                  />
                </div>

                <div class="flex gap-3">
                  <button
                    type="submit"
                    disabled={mfaLoading || !mfaDisablePassword || !mfaDisableCode}
                    class="px-4 py-2 bg-red-600 hover:bg-red-500 disabled:bg-red-800 text-white text-sm font-medium rounded transition-colors disabled:cursor-not-allowed"
                  >
                    {mfaLoading ? 'Disabling...' : 'Confirm Disable'}
                  </button>
                  <button
                    type="button"
                    onclick={() => { showDisableForm = false; mfaDisablePassword = ''; mfaDisableCode = ''; }}
                    class="px-4 py-2 text-sm font-medium text-slate-400 hover:text-slate-200 bg-slate-700 hover:bg-slate-600 rounded transition-colors"
                  >
                    Cancel
                  </button>
                </div>
              </form>
            </div>

          {:else if mfaSetupData}
            <!-- MFA setup in progress -->
            <div class="bg-slate-800 border border-slate-700 rounded-lg p-5 space-y-5">
              <p class="text-sm text-slate-400">
                Scan this QR code with your authenticator app (Google Authenticator, Authy, etc.), or enter the secret manually.
              </p>

              <!-- QR code -->
              <div class="flex justify-center p-4 bg-white rounded-lg w-fit mx-auto">
                {#if qrDataUrl}
                  <img
                    src={qrDataUrl}
                    alt="MFA QR Code"
                    width="200"
                    height="200"
                  />
                {:else}
                  <div class="w-[200px] h-[200px] flex items-center justify-center">
                    <div class="animate-spin rounded-full h-8 w-8 border-2 border-slate-300 border-t-slate-600"></div>
                  </div>
                {/if}
              </div>

              <!-- Manual secret -->
              <div>
                <label for="mfaSecret" class="block text-xs font-medium text-slate-400 uppercase tracking-wider mb-1.5">Manual Entry Secret</label>
                <div class="flex items-center gap-2">
                  <code class="flex-1 px-3 py-2 bg-slate-900 border border-slate-700 rounded text-sm text-slate-300 font-mono tracking-wider">{mfaSetupData.secret}</code>
                  <button
                    onclick={copySecret}
                    class="p-2 text-slate-400 hover:text-slate-200 hover:bg-slate-700 rounded transition-colors"
                    title="Copy secret"
                  >
                    {#if secretCopied}
                      <IconCheck size={16} class="text-emerald-400" />
                    {:else}
                      <IconCopy size={16} />
                    {/if}
                  </button>
                </div>
              </div>

              <!-- Verify code -->
              <form onsubmit={(e) => { e.preventDefault(); handleMfaVerify(); }}>
                <label for="mfaVerifyCode" class="block text-xs font-medium text-slate-400 uppercase tracking-wider mb-1.5">Verification Code</label>
                <div class="flex gap-3">
                  <input
                    id="mfaVerifyCode"
                    type="text"
                    bind:value={mfaVerifyCode}
                    required
                    maxlength="6"

                    placeholder="000000"
                    inputmode="numeric"
                    autocomplete="one-time-code"
                    class="w-48 px-3 py-2 bg-slate-900 border border-slate-600 rounded text-slate-100 text-sm font-mono tracking-widest focus:outline-none focus:ring-1 focus:ring-emerald-500 focus:border-emerald-500"
                  />
                  <button
                    type="submit"
                    disabled={mfaLoading || mfaVerifyCode.length !== 6}
                    class="px-4 py-2 bg-emerald-600 hover:bg-emerald-500 disabled:bg-emerald-800 text-white text-sm font-medium rounded transition-colors disabled:cursor-not-allowed"
                  >
                    {mfaLoading ? 'Verifying...' : 'Verify & Enable'}
                  </button>
                </div>
              </form>

              <button
                onclick={cancelMfaSetup}
                class="text-sm text-slate-500 hover:text-slate-300 transition-colors"
              >
                Cancel setup
              </button>
            </div>

          {:else}
            <!-- MFA not enabled -->
            <div class="bg-slate-800 border border-slate-700 rounded-lg p-5">
              <div class="flex items-center gap-3 mb-4">
                <div class="w-10 h-10 rounded-lg bg-slate-700 border border-slate-600 flex items-center justify-center">
                  <IconShieldLock size={20} class="text-slate-400" />
                </div>
                <div>
                  <p class="text-sm font-medium text-slate-200">TOTP Authenticator</p>
                  <span class="inline-flex items-center px-1.5 py-0.5 rounded text-[10px] font-medium uppercase tracking-wider bg-slate-700 text-slate-400 border border-slate-600">
                    Disabled
                  </span>
                </div>
              </div>
              <p class="text-sm text-slate-400 mb-4">
                Add an extra layer of security by requiring a TOTP code from your authenticator app on every login.
              </p>
              <button
                onclick={handleMfaSetup}
                disabled={mfaLoading}
                class="px-4 py-2 bg-emerald-600 hover:bg-emerald-500 disabled:bg-emerald-800 text-white text-sm font-medium rounded transition-colors disabled:cursor-not-allowed"
              >
                {mfaLoading ? 'Setting up...' : 'Enable MFA'}
              </button>
            </div>
          {/if}
        </div>

      {:else if activeTab === 'api-keys'}
        <!-- API Keys Tab -->
        <div>
          <div class="flex items-center justify-between mb-1">
            <h2 class="text-sm font-medium text-slate-300 uppercase tracking-wider">API Keys</h2>
            <button
              onclick={openApiKeyModal}
              class="flex items-center gap-1.5 px-3 py-1.5 bg-emerald-600 hover:bg-emerald-500 text-white text-sm font-medium rounded transition-colors"
            >
              <IconPlus size={16} stroke={2} />
              New Key
            </button>
          </div>
          <p class="text-sm text-slate-500 mb-4">Manage API keys for programmatic access to the CIS API.</p>

          {#if apiKeysLoading}
            <div class="flex items-center justify-center py-12">
              <div class="animate-spin rounded-full h-8 w-8 border-2 border-slate-700 border-t-emerald-500"></div>
            </div>
          {:else if apiKeys.length === 0}
            <div class="text-center py-12 bg-slate-800/50 border border-slate-700 rounded-lg">
              <IconKey size={40} class="mx-auto text-slate-600 mb-3" stroke={1} />
              <p class="text-slate-400 mb-2">No API keys created</p>
              <p class="text-sm text-slate-500 mb-4">Create an API key for programmatic access to the scheduler</p>
              <button
                onclick={openApiKeyModal}
                class="inline-flex items-center gap-1.5 px-3 py-1.5 bg-emerald-600 hover:bg-emerald-500 text-white text-sm font-medium rounded transition-colors"
              >
                <IconPlus size={16} stroke={2} />
                Create Your First Key
              </button>
            </div>
          {:else}
            <div class="space-y-3">
              {#each apiKeys as key (key.id)}
                <div class="bg-slate-800 border border-slate-700 rounded-lg p-4">
                  <div class="flex items-start justify-between gap-4">
                    <div class="flex-1 min-w-0">
                      <div class="flex items-center gap-2 mb-1">
                        <IconKey size={16} class="text-slate-500" />
                        <h3 class="text-sm font-medium text-slate-200">{key.name}</h3>
                        {#if key.days_until_expiry != null && key.days_until_expiry === 0}
                          <span class="inline-flex items-center gap-1 px-1.5 py-0.5 rounded text-xs font-medium bg-red-900/50 text-red-400 border border-red-800">
                            <IconAlertTriangle size={12} />
                            Expired
                          </span>
                        {:else if key.expires_soon}
                          <span class="inline-flex items-center gap-1 px-1.5 py-0.5 rounded text-xs font-medium bg-amber-900/50 text-amber-400 border border-amber-800">
                            <IconAlertTriangle size={12} />
                            Expires in {key.days_until_expiry}d
                          </span>
                        {:else if key.days_until_expiry != null && key.days_until_expiry > 0}
                          <span class="inline-flex items-center px-1.5 py-0.5 rounded text-xs font-medium bg-slate-700 text-slate-400 border border-slate-600">
                            {key.days_until_expiry}d remaining
                          </span>
                        {:else}
                          <span class="inline-flex items-center px-1.5 py-0.5 rounded text-xs font-medium bg-slate-700 text-slate-500 border border-slate-600">
                            No expiry
                          </span>
                        {/if}
                      </div>
                      <p class="text-xs text-slate-500">
                        <span class="font-mono text-slate-400">{key.prefix}...</span>
                        <span class="mx-1.5">·</span>
                        Created {formatKeyDate(key.created_at)}
                        <span class="mx-1.5">·</span>
                        {#if key.last_used_at}
                          Used {formatKeyDate(key.last_used_at)}
                        {:else}
                          Never used
                        {/if}
                        {#if key.expires_at}
                          <span class="mx-1.5">·</span>
                          {#if key.days_until_expiry != null && key.days_until_expiry > 0}
                            Expires in {key.days_until_expiry} day{key.days_until_expiry === 1 ? '' : 's'}
                          {:else if key.days_until_expiry != null && key.days_until_expiry === 0}
                            <span class="text-red-400">Expired</span>
                          {/if}
                        {/if}
                      </p>
                    </div>

                    <div class="flex items-center gap-2 flex-shrink-0">
                      {#if deleteConfirmKeyId === key.id}
                        <span class="text-xs text-red-400 mr-2">Revoke?</span>
                        <button
                          onclick={() => deleteApiKey(key.id)}
                          class="px-2 py-1 text-xs text-red-400 hover:text-red-300 bg-red-900/30 hover:bg-red-900/50 border border-red-800 rounded transition-colors"
                        >
                          Yes
                        </button>
                        <button
                          onclick={() => deleteConfirmKeyId = null}
                          class="px-2 py-1 text-xs text-slate-400 hover:text-slate-200 bg-slate-700 hover:bg-slate-600 rounded transition-colors"
                        >
                          No
                        </button>
                      {:else}
                        <button
                          onclick={() => deleteConfirmKeyId = key.id}
                          class="flex items-center gap-1 px-2 py-1 text-xs text-slate-400 hover:text-red-400 bg-slate-700 hover:bg-slate-600 rounded transition-colors"
                        >
                          <IconTrash size={14} />
                          Revoke
                        </button>
                      {/if}
                    </div>
                  </div>
                </div>
              {/each}
            </div>
          {/if}
        </div>
      {/if}
    </div>
  </main>
</div>

<!-- API Key Modal -->
{#if showApiKeyModal}
  <div class="fixed inset-0 z-50 flex items-center justify-center p-4">
    <!-- Backdrop -->
    <div
      class="absolute inset-0 bg-black/60"
      onclick={closeApiKeyModal}
      onkeypress={(e) => e.key === 'Escape' && closeApiKeyModal()}
      role="button"
      tabindex="0"
      aria-label="Close modal"
    ></div>

    <!-- Modal -->
    <div class="relative bg-slate-800 border border-slate-700 rounded-lg w-full max-w-md">
      <!-- Header -->
      <div class="flex items-center justify-between p-4 border-b border-slate-700">
        <h2 class="text-lg font-medium text-slate-100">
          {createdKey ? 'API Key Created' : 'Create API Key'}
        </h2>
        <button
          onclick={closeApiKeyModal}
          class="p-1 text-slate-400 hover:text-slate-200 transition-colors"
        >
          <IconX size={20} />
        </button>
      </div>

      <!-- Content -->
      <div class="p-4">
        {#if createdKey}
          <!-- Success state - show the key -->
          <div class="space-y-4">
            <div class="flex items-start gap-3 p-3 bg-amber-900/30 border border-amber-800 rounded">
              <IconAlertTriangle size={20} class="text-amber-500 flex-shrink-0 mt-0.5" />
              <p class="text-sm text-amber-200">
                Copy this key now. You won't be able to see it again.
              </p>
            </div>

            <div>
              <label class="block text-xs font-medium text-slate-400 uppercase tracking-wider mb-2">
                Your API Key
              </label>
              <div class="flex items-center gap-2">
                <code class="flex-1 px-3 py-2 bg-slate-900 border border-slate-600 rounded text-sm text-emerald-400 font-mono break-all">
                  {createdKey.key}
                </code>
                <button
                  onclick={copyKey}
                  class="flex-shrink-0 p-2 text-slate-400 hover:text-emerald-400 bg-slate-700 hover:bg-slate-600 rounded transition-colors"
                  title="Copy to clipboard"
                >
                  {#if keyCopied}
                    <IconCheck size={18} class="text-emerald-500" />
                  {:else}
                    <IconCopy size={18} />
                  {/if}
                </button>
              </div>
            </div>

            <div class="flex justify-end pt-2">
              <button
                onclick={closeApiKeyModal}
                class="px-4 py-2 bg-emerald-600 hover:bg-emerald-500 text-white text-sm font-medium rounded transition-colors"
              >
                Done
              </button>
            </div>
          </div>
        {:else}
          <!-- Create form -->
          <form onsubmit={(e) => { e.preventDefault(); createApiKey(); }} class="space-y-4">
            <div>
              <label for="key-name" class="block text-xs font-medium text-slate-400 uppercase tracking-wider mb-2">
                Name <span class="text-red-500">*</span>
              </label>
              <input
                id="key-name"
                type="text"
                bind:value={newKeyName}
                placeholder="e.g., CI/CD Pipeline"
                class="w-full px-3 py-2 bg-slate-900 border border-slate-600 rounded text-sm text-slate-100 placeholder-slate-500 focus:outline-none focus:ring-1 focus:ring-emerald-500 focus:border-emerald-500"
              />
              <p class="mt-1.5 text-xs text-slate-500">
                Give this key a descriptive name so you can identify it later.
              </p>
            </div>

            <div class="flex items-center justify-end gap-3 pt-2">
              <button
                type="button"
                onclick={closeApiKeyModal}
                class="px-4 py-2 text-sm font-medium text-slate-300 hover:text-white bg-slate-700 hover:bg-slate-600 rounded transition-colors"
              >
                Cancel
              </button>
              <button
                type="submit"
                disabled={newKeyLoading || !newKeyName.trim()}
                class="px-4 py-2 bg-emerald-600 hover:bg-emerald-500 disabled:bg-emerald-800 text-white text-sm font-medium rounded transition-colors disabled:cursor-not-allowed"
              >
                {#if newKeyLoading}
                  Creating...
                {:else}
                  Create Key
                {/if}
              </button>
            </div>
          </form>
        {/if}
      </div>
    </div>
  </div>
{/if}
