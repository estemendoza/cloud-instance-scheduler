<script lang="ts">
  import { goto } from '$app/navigation';
  import { onMount } from 'svelte';
  import { authStore } from '$lib/stores/auth';
  import { providerMetadata, providerLabels, providerTypes, loadProviderMetadata, getProviderMeta } from '$lib/stores/providers';
  import { cloudAccountsAPI } from '$lib/api/endpoints/cloudAccounts';
  import { usersAPI } from '$lib/api/endpoints/users';
  import { organizationsAPI } from '$lib/api/endpoints/organizations';
  import { notify } from '$lib/utils/toast';
  import Sidebar from '$lib/components/layout/Sidebar.svelte';
  import type { CloudAccount, CloudAccountCreate, CloudAccountUpdate } from '$lib/types/cloudAccount';
  import type { User, UserCreate, UserUpdate, UserRole } from '$lib/types/user';
  import type { Organization, OrganizationUpdate } from '$lib/types/organization';
  import { ROLE_LABELS } from '$lib/types/user';
  import { IconChevronDown, IconChevronUp } from '@tabler/icons-svelte';
  import { pricingJobsAPI } from '$lib/api/endpoints/pricingJobs';
  import type { PricingJobRun, PricingStatusSummary, GcpAccountOption } from '$lib/api/endpoints/pricingJobs';
  import {
    IconCloud,
    IconUsers,
    IconBuilding,
    IconPlus,
    IconRefresh,
    IconEdit,
    IconTrash,
    IconX,
    IconAlertTriangle,
    IconCurrencyDollar,
  } from '@tabler/icons-svelte';

  type TabId = 'cloud-accounts' | 'users' | 'organization' | 'pricing';

  interface Tab {
    id: TabId;
    label: string;
    icon: any;
  }

  const tabs: Tab[] = [
    { id: 'cloud-accounts', label: 'Cloud Accounts', icon: IconCloud },
    { id: 'users', label: 'Users', icon: IconUsers },
    { id: 'organization', label: 'Organization', icon: IconBuilding },
    { id: 'pricing', label: 'Pricing', icon: IconCurrencyDollar }
  ];

  let activeTab = $state<TabId>('cloud-accounts');

  // Cloud accounts state
  let accounts = $state<CloudAccount[]>([]);
  let loading = $state(true);
  let syncing = $state<Record<string, boolean>>({});

  // Modal state
  let showModal = $state(false);
  let modalMode = $state<'add' | 'edit'>('add');
  let editingAccount = $state<CloudAccount | null>(null);

  // Form state
  let formName = $state('');
  let formProvider = $state('aws');
  let formCredentials = $state<Record<string, string>>({});

  // Derive current provider's metadata from the store
  let currentMeta = $derived(getProviderMeta($providerMetadata, formProvider));
  let credentialFields = $derived(currentMeta?.credential_fields ?? []);
  let regionsList = $derived(currentMeta?.regions ?? []);
  let regionLabel = $derived(currentMeta?.region_label ?? 'Regions');
  let formIsActive = $state(true);
  let formSelectedRegions = $state<string[]>([]);
  let formAllRegions = $state(true); // true = scan all regions
  let showRegionSelector = $state(false);
  let formError = $state('');
  let formLoading = $state(false);

  // Delete confirmation
  let showDeleteModal = $state(false);
  let deleteConfirmAccount = $state<CloudAccount | null>(null);
  let deleteConfirmText = $state('');

  // Users state
  let users = $state<User[]>([]);
  let usersLoading = $state(false);
  let usersLoaded = $state(false);
  let showUserModal = $state(false);
  let userModalMode = $state<'add' | 'edit'>('add');
  let editingUser = $state<User | null>(null);
  let userFormEmail = $state('');
  let userFormName = $state('');
  let userFormPassword = $state('');
  let userFormRole = $state<UserRole>('viewer');
  let userFormIsActive = $state(true);
  let userFormLoading = $state(false);
  let userFormError = $state('');
  let deleteConfirmUserId = $state<string | null>(null);

  const roleOptions: UserRole[] = ['admin', 'operator', 'viewer'];

  // Organization state
  let organization = $state<Organization | null>(null);
  let orgLoading = $state(false);
  let showOrgModal = $state(false);
  let orgFormName = $state('');
  let orgFormSlug = $state('');
  let orgFormLoading = $state(false);
  let orgFormError = $state('');

  let isAdmin = $derived($authStore.user?.role === 'admin');
  let currentUserId = $derived($authStore.user?.id);

  // Redirect if not admin
  $effect(() => {
    if ($authStore.user && !isAdmin) {
      goto('/');
    }
  });

  onMount(async () => {
    await loadProviderMetadata();
    await loadAccounts();
  });

  async function loadAccounts() {
    loading = true;
    try {
      accounts = await cloudAccountsAPI.list();
    } catch (err: any) {
      notify.error(err.message || 'Failed to load cloud accounts');
    } finally {
      loading = false;
    }
  }

  function openAddModal() {
    modalMode = 'add';
    editingAccount = null;
    formName = '';
    formProvider = $providerTypes[0] || 'aws';
    formCredentials = {};
    formIsActive = true;
    formSelectedRegions = [];
    formAllRegions = true;
    showRegionSelector = false;
    formError = '';
    showModal = true;
  }

  function openEditModal(account: CloudAccount) {
    modalMode = 'edit';
    editingAccount = account;
    formName = account.name;
    formProvider = account.provider_type;
    // Pre-populate non-secret credential fields from hints
    formCredentials = {};
    const meta = getProviderMeta($providerMetadata, account.provider_type);
    if (account.credential_hints && meta) {
      for (const field of meta.credential_fields) {
        if (field.type === 'text' && account.credential_hints[field.key]) {
          formCredentials[field.key] = account.credential_hints[field.key];
        }
      }
    }
    formIsActive = account.is_active;
    formSelectedRegions = account.selected_regions || [];
    formAllRegions = !account.selected_regions || account.selected_regions.length === 0;
    showRegionSelector = false;
    formError = '';
    showModal = true;
  }

  function closeModal() {
    showModal = false;
    editingAccount = null;
  }

  async function handleSubmit() {
    formError = '';

    if (!formName.trim()) {
      formError = 'Name is required';
      return;
    }

    // Validate required credentials for new accounts
    if (modalMode === 'add') {
      const requiredFields = credentialFields.filter(f => f.required);
      for (const field of requiredFields) {
        if (!formCredentials[field.key]?.trim()) {
          formError = `${field.label} is required`;
          return;
        }
      }
    }

    formLoading = true;

    try {
      // Determine selected regions (null = all regions)
      const selectedRegions = formAllRegions ? null : formSelectedRegions;

      if (modalMode === 'add') {
        const data: CloudAccountCreate = {
          name: formName.trim(),
          provider_type: formProvider,
          credentials: formCredentials,
          is_active: formIsActive,
          selected_regions: selectedRegions
        };
        await cloudAccountsAPI.create(data);
        notify.success('Cloud account added successfully');
      } else if (editingAccount) {
        const data: CloudAccountUpdate = {
          name: formName.trim(),
          is_active: formIsActive,
          selected_regions: selectedRegions
        };
        // Only include credentials if user entered a secret field
        // (non-secret fields are pre-populated from hints and don't count)
        const secretFields = credentialFields
          .filter(f => f.type === 'password' || f.type === 'textarea')
          .map(f => f.key);
        const hasNewSecrets = secretFields.some(k => formCredentials[k]?.trim());
        if (hasNewSecrets) {
          data.credentials = formCredentials;
        }
        await cloudAccountsAPI.update(editingAccount.id, data);
        notify.success('Cloud account updated successfully');
      }
      closeModal();
      await loadAccounts();
    } catch (err: any) {
      formError = err.message || 'Operation failed';
      notify.error(formError);
    } finally {
      formLoading = false;
    }
  }

  async function handleSync(account: CloudAccount) {
    syncing[account.id] = true;
    try {
      const result = await cloudAccountsAPI.sync(account.id);
      notify.success(`Synced ${result.total} resources (${result.created} new, ${result.updated} updated)`);
      await loadAccounts();
    } catch (err: any) {
      notify.error(err.message || 'Sync failed');
    } finally {
      syncing[account.id] = false;
    }
  }

  function openDeleteModal(account: CloudAccount) {
    deleteConfirmAccount = account;
    deleteConfirmText = '';
    showDeleteModal = true;
  }

  function closeDeleteModal() {
    showDeleteModal = false;
    deleteConfirmAccount = null;
    deleteConfirmText = '';
  }

  async function confirmDelete() {
    if (!deleteConfirmAccount) return;
    try {
      await cloudAccountsAPI.delete(deleteConfirmAccount.id);
      notify.success('Cloud account deleted');
      closeDeleteModal();
      await loadAccounts();
    } catch (err: any) {
      notify.error(err.message || 'Failed to delete account');
    }
  }

  function formatLastSync(date: string | null): string {
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

  const COLOR_CLASSES: Record<string, string> = {
    orange: 'bg-orange-900/50 text-orange-400 border-orange-800',
    blue: 'bg-blue-900/50 text-blue-400 border-blue-800',
    red: 'bg-red-900/50 text-red-400 border-red-800',
    green: 'bg-green-900/50 text-green-400 border-green-800',
    purple: 'bg-purple-900/50 text-purple-400 border-purple-800',
    cyan: 'bg-cyan-900/50 text-cyan-400 border-cyan-800',
    yellow: 'bg-yellow-900/50 text-yellow-400 border-yellow-800',
    pink: 'bg-pink-900/50 text-pink-400 border-pink-800',
    slate: 'bg-slate-800 text-slate-400 border-slate-700',
  };

  function getProviderColor(providerType: string): string {
    const meta = getProviderMeta($providerMetadata, providerType);
    return COLOR_CLASSES[meta?.color ?? 'slate'] ?? COLOR_CLASSES.slate;
  }

  function formatRegions(regions: string[] | null): string {
    if (!regions || regions.length === 0) return 'All regions';
    if (regions.length === 1) return '1 region';
    return `${regions.length} regions`;
  }

  function toggleRegion(regionCode: string) {
    if (formSelectedRegions.includes(regionCode)) {
      formSelectedRegions = formSelectedRegions.filter(r => r !== regionCode);
    } else {
      formSelectedRegions = [...formSelectedRegions, regionCode];
    }
  }

  // Users functions
  async function loadUsers() {
    usersLoading = true;
    try {
      users = await usersAPI.list();
    } catch (err: any) {
      notify.error(err.message || 'Failed to load users');
    } finally {
      usersLoading = false;
      usersLoaded = true;
    }
  }

  function openAddUserModal() {
    userModalMode = 'add';
    editingUser = null;
    userFormEmail = '';
    userFormName = '';
    userFormPassword = '';
    userFormRole = 'viewer';
    userFormIsActive = true;
    userFormError = '';
    showUserModal = true;
  }

  function openEditUserModal(user: User) {
    userModalMode = 'edit';
    editingUser = user;
    userFormEmail = user.email;
    userFormName = user.full_name || '';
    userFormPassword = '';
    userFormRole = user.role;
    userFormIsActive = user.is_active;
    userFormError = '';
    showUserModal = true;
  }

  function closeUserModal() {
    showUserModal = false;
    editingUser = null;
  }

  async function handleUserSubmit() {
    userFormError = '';

    if (userModalMode === 'add') {
      if (!userFormEmail.trim()) {
        userFormError = 'Email is required';
        return;
      }
      if (!userFormPassword.trim()) {
        userFormError = 'Password is required';
        return;
      }
    }

    userFormLoading = true;

    try {
      if (userModalMode === 'add') {
        const data: UserCreate = {
          email: userFormEmail.trim(),
          password: userFormPassword,
          full_name: userFormName.trim() || undefined,
          role: userFormRole,
          is_active: userFormIsActive,
          organization_id: $authStore.user?.organization_id || ''
        };
        await usersAPI.create(data);
        notify.success('User added successfully');
      } else if (editingUser) {
        const data: UserUpdate = {
          full_name: userFormName.trim() || undefined,
          role: userFormRole,
          is_active: userFormIsActive
        };
        await usersAPI.update(editingUser.id, data);
        notify.success('User updated successfully');
      }
      closeUserModal();
      await loadUsers();
    } catch (err: any) {
      userFormError = err.message || 'Operation failed';
      notify.error(userFormError);
    } finally {
      userFormLoading = false;
    }
  }

  async function deleteUser(userId: string) {
    try {
      await usersAPI.delete(userId);
      notify.success('User deleted');
      await loadUsers();
    } catch (err: any) {
      notify.error(err.message || 'Failed to delete user');
    }
    deleteConfirmUserId = null;
  }

  function getRoleColor(role: UserRole): string {
    switch (role) {
      case 'admin': return 'bg-purple-900/50 text-purple-400 border-purple-800';
      case 'operator': return 'bg-blue-900/50 text-blue-400 border-blue-800';
      case 'viewer': return 'bg-slate-700 text-slate-400 border-slate-600';
      default: return 'bg-slate-700 text-slate-400 border-slate-600';
    }
  }

  // Load users when switching to that tab
  $effect(() => {
    if (activeTab === 'users' && !usersLoaded && !usersLoading) {
      loadUsers();
    }
  });

  // Organization functions
  async function loadOrganization() {
    if (!$authStore.user?.organization_id) return;
    orgLoading = true;
    try {
      organization = await organizationsAPI.get($authStore.user.organization_id);
    } catch (err: any) {
      notify.error(err.message || 'Failed to load organization');
    } finally {
      orgLoading = false;
    }
  }

  function openOrgModal() {
    if (!organization) return;
    orgFormName = organization.name;
    orgFormSlug = organization.slug;
    orgFormError = '';
    showOrgModal = true;
  }

  function closeOrgModal() {
    showOrgModal = false;
  }

  function validateSlug(slug: string): boolean {
    return /^[a-z0-9-]+$/.test(slug);
  }

  async function handleOrgSubmit() {
    orgFormError = '';

    if (!orgFormName.trim()) {
      orgFormError = 'Name is required';
      return;
    }

    if (!orgFormSlug.trim()) {
      orgFormError = 'Slug is required';
      return;
    }

    if (!validateSlug(orgFormSlug)) {
      orgFormError = 'Slug must contain only lowercase letters, numbers, and hyphens';
      return;
    }

    if (!organization) return;

    orgFormLoading = true;

    try {
      const data: OrganizationUpdate = {
        name: orgFormName.trim(),
        slug: orgFormSlug.trim()
      };
      organization = await organizationsAPI.update(organization.id, data);
      notify.success('Organization updated successfully');
      closeOrgModal();
    } catch (err: any) {
      orgFormError = err.message || 'Failed to update organization';
      notify.error(orgFormError);
    } finally {
      orgFormLoading = false;
    }
  }

  // Load organization when switching to that tab
  $effect(() => {
    if (activeTab === 'organization' && !organization && !orgLoading) {
      loadOrganization();
    }
  });

  // Pricing tab state
  let pricingStatus = $state<PricingStatusSummary | null>(null);
  let pricingJobs = $state<PricingJobRun[]>([]);
  let gcpAccounts = $state<GcpAccountOption[]>([]);
  let selectedGcpAccountId = $state('');
  let pricingLoading = $state(false);
  let pricingLoaded = $state(false);
  let triggerLoading = $state(false);
  let pollInterval: ReturnType<typeof setInterval> | null = null;

  $effect(() => {
    if (activeTab === 'pricing' && !pricingLoaded && !pricingLoading) {
      loadPricingData();
    }
  });

  async function loadPricingData() {
    pricingLoading = true;
    try {
      const [statusData, jobsData, gcpData] = await Promise.all([
        pricingJobsAPI.getStatus(),
        pricingJobsAPI.list({ limit: 50 }),
        pricingJobsAPI.getGcpAccounts(),
      ]);
      pricingStatus = statusData;
      pricingJobs = jobsData;
      gcpAccounts = gcpData;
      // Auto-select first GCP account if available and none selected
      if (!selectedGcpAccountId && gcpAccounts.length > 0) {
        selectedGcpAccountId = gcpAccounts[0].id;
      }
    } catch (err: any) {
      notify.error(err.message || 'Failed to load pricing status');
    } finally {
      pricingLoading = false;
      pricingLoaded = true;
    }
  }

  async function triggerPricingUpdate(providerType?: string) {
    triggerLoading = true;
    try {
      const result = await pricingJobsAPI.trigger(providerType, selectedGcpAccountId || undefined);
      notify.success(result.message);
      startPolling(result.job_ids);
    } catch (err: any) {
      notify.error(err.message || 'Failed to trigger pricing update');
    } finally {
      triggerLoading = false;
    }
  }

  function startPolling(jobIds: string[]) {
    if (pollInterval) clearInterval(pollInterval);
    pollInterval = setInterval(async () => {
      try {
        const jobs = await Promise.all(jobIds.map(id => pricingJobsAPI.get(id)));
        const allDone = jobs.every(j => j.status === 'completed' || j.status === 'failed');
        if (allDone) {
          if (pollInterval) clearInterval(pollInterval);
          pollInterval = null;
          pricingLoaded = false;
          await loadPricingData();
          const failed = jobs.filter(j => j.status === 'failed');
          if (failed.length > 0) {
            notify.error(`${failed.length} provider(s) failed to update`);
          } else {
            notify.success('Pricing update completed');
          }
        }
      } catch {
        // ignore polling errors
      }
    }, 5000);
  }

  function getProviderStatusColor(status: string): string {
    switch (status) {
      case 'success': return 'bg-emerald-500';
      case 'failed': return 'bg-red-500';
      case 'running': return 'bg-amber-500 animate-pulse';
      default: return 'bg-slate-500';
    }
  }

  function getJobStatusClasses(status: string): string {
    switch (status) {
      case 'completed': return 'bg-emerald-900/50 text-emerald-400 border-emerald-800';
      case 'failed': return 'bg-red-900/50 text-red-400 border-red-800';
      case 'running': return 'bg-amber-900/50 text-amber-400 border-amber-800';
      case 'pending': return 'bg-slate-700 text-slate-400 border-slate-600';
      default: return 'bg-slate-700 text-slate-400 border-slate-600';
    }
  }

  function formatDuration(seconds: number | null): string {
    if (seconds === null) return '—';
    if (seconds < 60) return `${seconds.toFixed(1)}s`;
    return `${Math.floor(seconds / 60)}m ${Math.round(seconds % 60)}s`;
  }

  function pricingTimeAgo(dateStr: string): string {
    const diff = Date.now() - new Date(dateStr).getTime();
    const mins = Math.floor(diff / 60000);
    if (mins < 1) return 'just now';
    if (mins < 60) return `${mins}m ago`;
    const hrs = Math.floor(mins / 60);
    if (hrs < 24) return `${hrs}h ago`;
    const days = Math.floor(hrs / 24);
    return `${days}d ago`;
  }
</script>

<svelte:head>
  <title>Settings - Cloud Instance Scheduler</title>
</svelte:head>

<div class="flex h-screen bg-slate-900">
  <Sidebar />

  <main class="flex-1 overflow-auto pt-14 lg:pt-0">
    <div class="p-6">
      <!-- Header -->
      <div class="mb-6">
        <h1 class="text-xl font-semibold text-slate-100">Settings</h1>
        <p class="text-sm text-slate-500 mt-1">Manage cloud accounts and system configuration</p>
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
      {#if activeTab === 'cloud-accounts'}
        <!-- Cloud Accounts Tab -->
        <div>
          <div class="flex items-center justify-between mb-1">
            <h2 class="text-sm font-medium text-slate-300 uppercase tracking-wider">Cloud Accounts</h2>
            <button
              onclick={openAddModal}
              class="flex items-center gap-1.5 px-3 py-1.5 bg-emerald-600 hover:bg-emerald-500 text-white text-sm font-medium rounded transition-colors"
            >
              <IconPlus size={16} stroke={2} />
              Add Account
            </button>
          </div>
          <p class="text-sm text-slate-500 mb-4">Connect your AWS, Azure, or GCP accounts to discover and manage cloud instances.</p>

          {#if loading}
            <div class="flex items-center justify-center py-12">
              <div class="animate-spin rounded-full h-8 w-8 border-2 border-slate-700 border-t-emerald-500"></div>
            </div>
          {:else if accounts.length === 0}
            <div class="text-center py-12 bg-slate-800/50 border border-slate-700 rounded-lg">
              <IconCloud size={40} class="mx-auto text-slate-600 mb-3" stroke={1} />
              <p class="text-slate-400 mb-2">No cloud accounts configured</p>
              <p class="text-sm text-slate-500 mb-4">Add a cloud account to start discovering and managing resources</p>
              <button
                onclick={openAddModal}
                class="inline-flex items-center gap-1.5 px-3 py-1.5 bg-emerald-600 hover:bg-emerald-500 text-white text-sm font-medium rounded transition-colors"
              >
                <IconPlus size={16} stroke={2} />
                Add Your First Account
              </button>
            </div>
          {:else}
            <div class="space-y-3">
              {#each accounts as account (account.id)}
                <div class="bg-slate-800 border border-slate-700 rounded-lg p-4">
                  <div class="flex items-start justify-between gap-4">
                    <div class="flex-1 min-w-0">
                      <div class="flex items-center gap-2 mb-1">
                        <span class="inline-flex items-center px-2 py-0.5 rounded text-xs font-medium uppercase tracking-wider border {getProviderColor(account.provider_type)}">
                          {$providerLabels[account.provider_type] || account.provider_type}
                        </span>
                        <h3 class="text-sm font-medium text-slate-200 truncate">{account.name}</h3>
                        {#if account.is_active}
                          <span class="w-2 h-2 bg-emerald-500 rounded-full" title="Active"></span>
                        {:else}
                          <span class="w-2 h-2 bg-slate-500 rounded-full" title="Inactive"></span>
                        {/if}
                      </div>
                      <p class="text-xs text-slate-500">
                        {formatRegions(account.selected_regions)} ·
                        Last sync: {formatLastSync(account.last_sync_at)}
                      </p>
                    </div>

                    <div class="flex items-center gap-2 flex-shrink-0">
                        <button
                          onclick={() => handleSync(account)}
                          disabled={syncing[account.id]}
                          class="flex items-center gap-1 px-2 py-1 text-xs text-slate-400 hover:text-emerald-400 bg-slate-700 hover:bg-slate-600 rounded transition-colors disabled:opacity-50"
                          title="Sync resources"
                        >
                          <IconRefresh size={14} class={syncing[account.id] ? 'animate-spin' : ''} />
                          Sync
                        </button>
                        <button
                          onclick={() => openEditModal(account)}
                          class="flex items-center gap-1 px-2 py-1 text-xs text-slate-400 hover:text-slate-200 bg-slate-700 hover:bg-slate-600 rounded transition-colors"
                          title="Edit account"
                        >
                          <IconEdit size={14} />
                          Edit
                        </button>
                        <button
                          onclick={() => openDeleteModal(account)}
                          class="flex items-center gap-1 px-2 py-1 text-xs text-slate-400 hover:text-red-400 bg-slate-700 hover:bg-slate-600 rounded transition-colors"
                          title="Delete account"
                        >
                          <IconTrash size={14} />
                        </button>
                    </div>
                  </div>
                </div>
              {/each}
            </div>
          {/if}
        </div>

      {:else if activeTab === 'users'}
        <!-- Users Tab -->
        <div>
          <div class="flex items-center justify-between mb-1">
            <h2 class="text-sm font-medium text-slate-300 uppercase tracking-wider">Users</h2>
            <button
              onclick={openAddUserModal}
              class="flex items-center gap-1.5 px-3 py-1.5 bg-emerald-600 hover:bg-emerald-500 text-white text-sm font-medium rounded transition-colors"
            >
              <IconPlus size={16} stroke={2} />
              Add User
            </button>
          </div>
          <p class="text-sm text-slate-500 mb-4">Manage users and their roles within your organization.</p>

          {#if usersLoading}
            <div class="flex items-center justify-center py-12">
              <div class="animate-spin rounded-full h-8 w-8 border-2 border-slate-700 border-t-emerald-500"></div>
            </div>
          {:else if users.length === 0}
            <div class="text-center py-12 bg-slate-800/50 border border-slate-700 rounded-lg">
              <IconUsers size={40} class="mx-auto text-slate-600 mb-3" stroke={1} />
              <p class="text-slate-400 mb-2">No users found</p>
              <p class="text-sm text-slate-500 mb-4">Add team members to your organization</p>
              <button
                onclick={openAddUserModal}
                class="inline-flex items-center gap-1.5 px-3 py-1.5 bg-emerald-600 hover:bg-emerald-500 text-white text-sm font-medium rounded transition-colors"
              >
                <IconPlus size={16} stroke={2} />
                Add Your First User
              </button>
            </div>
          {:else}
            <div class="space-y-3">
              {#each users as user (user.id)}
                <div class="bg-slate-800 border border-slate-700 rounded-lg p-4">
                  <div class="flex items-start justify-between gap-4">
                    <div class="flex-1 min-w-0">
                      <div class="flex items-center gap-2 mb-1">
                        <h3 class="text-sm font-medium text-slate-200">
                          {user.email}
                          {#if user.id === currentUserId}
                            <span class="text-slate-500 font-normal">(You)</span>
                          {/if}
                        </h3>
                        <span class="inline-flex items-center px-2 py-0.5 rounded text-xs font-medium uppercase tracking-wider border {getRoleColor(user.role)}">
                          {ROLE_LABELS[user.role]}
                        </span>
                        {#if user.is_active}
                          <span class="w-2 h-2 bg-emerald-500 rounded-full" title="Active"></span>
                        {:else}
                          <span class="w-2 h-2 bg-slate-500 rounded-full" title="Inactive"></span>
                        {/if}
                      </div>
                      <p class="text-xs text-slate-500">
                        {user.full_name || 'No name set'}
                        {#if !user.is_active}
                          <span class="mx-1.5">·</span>
                          <span class="text-amber-500">Inactive</span>
                        {/if}
                      </p>
                    </div>

                    <div class="flex items-center gap-2 flex-shrink-0">
                      {#if deleteConfirmUserId === user.id}
                        <span class="text-xs text-red-400 mr-2">Delete?</span>
                        <button
                          onclick={() => deleteUser(user.id)}
                          class="px-2 py-1 text-xs text-red-400 hover:text-red-300 bg-red-900/30 hover:bg-red-900/50 border border-red-800 rounded transition-colors"
                        >
                          Yes
                        </button>
                        <button
                          onclick={() => deleteConfirmUserId = null}
                          class="px-2 py-1 text-xs text-slate-400 hover:text-slate-200 bg-slate-700 hover:bg-slate-600 rounded transition-colors"
                        >
                          No
                        </button>
                      {:else}
                        <button
                          onclick={() => openEditUserModal(user)}
                          class="flex items-center gap-1 px-2 py-1 text-xs text-slate-400 hover:text-slate-200 bg-slate-700 hover:bg-slate-600 rounded transition-colors"
                          title="Edit user"
                        >
                          <IconEdit size={14} />
                          Edit
                        </button>
                        {#if user.id !== currentUserId}
                          <button
                            onclick={() => deleteConfirmUserId = user.id}
                            class="flex items-center gap-1 px-2 py-1 text-xs text-slate-400 hover:text-red-400 bg-slate-700 hover:bg-slate-600 rounded transition-colors"
                            title="Delete user"
                          >
                            <IconTrash size={14} />
                          </button>
                        {/if}
                      {/if}
                    </div>
                  </div>
                </div>
              {/each}
            </div>
          {/if}
        </div>

      {:else if activeTab === 'organization'}
        <!-- Organization Tab -->
        <div>
          <div class="flex items-center justify-between mb-1">
            <h2 class="text-sm font-medium text-slate-300 uppercase tracking-wider">Organization</h2>
          </div>
          <p class="text-sm text-slate-500 mb-4">View and update your organization's name and identifier.</p>

          {#if orgLoading}
            <div class="flex items-center justify-center py-12">
              <div class="animate-spin rounded-full h-8 w-8 border-2 border-slate-700 border-t-emerald-500"></div>
            </div>
          {:else if organization}
            <div class="bg-slate-800 border border-slate-700 rounded-lg p-6">
              <div class="space-y-4">
                <div>
                  <label class="block text-xs font-medium text-slate-400 uppercase tracking-wider mb-1">Name</label>
                  <p class="text-sm text-slate-200">{organization.name}</p>
                </div>
                <div>
                  <label class="block text-xs font-medium text-slate-400 uppercase tracking-wider mb-1">Slug</label>
                  <p class="text-sm text-slate-200 font-mono">{organization.slug}</p>
                </div>
              </div>
              <div class="mt-6 pt-4 border-t border-slate-700">
                <button
                  onclick={openOrgModal}
                  class="flex items-center gap-1.5 px-3 py-1.5 text-sm text-slate-300 hover:text-white bg-slate-700 hover:bg-slate-600 rounded transition-colors"
                >
                  <IconEdit size={16} />
                  Edit
                </button>
              </div>
            </div>
          {:else}
            <div class="text-center py-12 bg-slate-800/50 border border-slate-700 rounded-lg">
              <IconBuilding size={40} class="mx-auto text-slate-600 mb-3" stroke={1} />
              <p class="text-slate-400">Unable to load organization</p>
            </div>
          {/if}
        </div>

      {:else if activeTab === 'pricing'}
        <!-- Pricing Tab -->
        <div>
          <div class="mb-1">
            <h2 class="text-sm font-medium text-slate-300 uppercase tracking-wider">Pricing</h2>
          </div>
          <p class="text-sm text-slate-500 mb-4">Monitor and trigger cloud instance pricing updates. Pricing data is used to calculate potential savings.</p>
          {#if pricingLoading}
            <div class="flex items-center justify-center py-12">
              <div class="animate-spin rounded-full h-8 w-8 border-2 border-slate-700 border-t-emerald-500"></div>
            </div>
          {:else}
            <!-- Status Overview -->
            <div class="bg-slate-800 border border-slate-700 rounded-lg p-6 mb-6">
              <div class="flex items-center justify-between mb-4">
                <div>
                  <h2 class="text-sm font-medium text-slate-300 uppercase tracking-wider">Pricing Update Status</h2>
                  {#if pricingStatus?.next_scheduled_utc}
                    <p class="text-xs text-slate-500 mt-1">Next scheduled: {pricingStatus.next_scheduled_utc}</p>
                  {/if}
                </div>
                <button
                  onclick={() => triggerPricingUpdate()}
                  disabled={triggerLoading || (pricingStatus?.is_running ?? false)}
                  class="flex items-center gap-1.5 px-3 py-1.5 text-sm font-medium bg-emerald-600 hover:bg-emerald-500 text-white rounded transition-colors disabled:opacity-50 disabled:cursor-not-allowed"
                >
                  {#if triggerLoading || pricingStatus?.is_running}
                    <div class="animate-spin rounded-full h-4 w-4 border-2 border-white/30 border-t-white"></div>
                    {pricingStatus?.is_running ? 'Running...' : 'Starting...'}
                  {:else}
                    <IconRefresh size={16} />
                    Update Now
                  {/if}
                </button>
              </div>

              <!-- Provider Status Cards -->
              <div class="grid grid-cols-1 md:grid-cols-3 gap-4">
                {#each ['aws', 'azure', 'gcp'] as ptype}
                  {@const prov = pricingStatus?.providers?.[ptype]}
                  <div class="bg-slate-900 border border-slate-700 rounded-lg p-4">
                    <div class="flex items-center justify-between mb-3">
                      <span class="text-sm font-medium text-slate-200">{ptype.toUpperCase()}</span>
                      <div class="flex items-center gap-1.5">
                        <div class="w-2 h-2 rounded-full {getProviderStatusColor(prov?.status || 'never_run')}"></div>
                        <span class="text-xs text-slate-500 capitalize">{prov?.status?.replace('_', ' ') || 'never run'}</span>
                      </div>
                    </div>

                    {#if prov?.last_run}
                      <div class="space-y-1">
                        <p class="text-xs text-slate-400">
                          Last run: {pricingTimeAgo(prov.last_run.started_at)}
                        </p>
                        <p class="text-xs text-slate-400">
                          {prov.last_run.records_updated ?? 0} records updated
                        </p>
                        {#if prov.last_run.duration_seconds !== null}
                          <p class="text-xs text-slate-500">
                            Duration: {formatDuration(prov.last_run.duration_seconds)}
                          </p>
                        {/if}
                        {#if prov.last_run.error_message}
                          <p class="text-xs text-red-400 mt-1 break-words">{prov.last_run.error_message}</p>
                        {/if}
                      </div>
                    {:else}
                      <p class="text-xs text-slate-500">No runs recorded</p>
                    {/if}

                    <!-- GCP Account Selector -->
                    {#if ptype === 'gcp'}
                      <div class="mt-3 pt-3 border-t border-slate-700">
                        {#if gcpAccounts.length > 0}
                          <label for="gcp-pricing-account" class="block text-xs text-slate-500 mb-1.5">Account for pricing</label>
                          <select
                            id="gcp-pricing-account"
                            bind:value={selectedGcpAccountId}
                            class="w-full bg-slate-800 border border-slate-600 text-slate-300 text-xs rounded px-2 py-1.5 focus:border-emerald-500 focus:ring-1 focus:ring-emerald-500 focus:outline-none"
                          >
                            {#each gcpAccounts as acct}
                              <option value={acct.id}>
                                {acct.name}{acct.project_id ? ` (${acct.project_id})` : ''}
                              </option>
                            {/each}
                          </select>
                          <p class="text-xs text-slate-500 mt-2">
                            GCP pricing is fetched only for instance types already discovered in your resources. The selected account's service account must have the <span class="text-slate-400">Cloud Billing API</span> enabled in its project.
                          </p>
                        {:else}
                          <div class="flex items-center gap-1.5 text-xs text-amber-400">
                            <IconAlertTriangle size={14} />
                            <span>No GCP accounts configured</span>
                          </div>
                          <p class="text-xs text-slate-500 mt-1">
                            Add a GCP cloud account to enable pricing updates
                          </p>
                        {/if}
                      </div>
                    {/if}
                  </div>
                {/each}
              </div>
            </div>

            <!-- Job History -->
            <div>
              <h2 class="text-sm font-medium text-slate-300 uppercase tracking-wider mb-4">Update History</h2>

              {#if pricingJobs.length === 0}
                <div class="text-center py-12 bg-slate-800/50 border border-slate-700 rounded-lg">
                  <IconCurrencyDollar size={40} class="mx-auto text-slate-600 mb-3" stroke={1} />
                  <p class="text-slate-400">No pricing updates recorded</p>
                  <p class="text-xs text-slate-500 mt-1">Updates will appear here after the next scheduled or manual run</p>
                </div>
              {:else}
                <div class="space-y-3">
                  {#each pricingJobs as job}
                    <div class="bg-slate-800 border border-slate-700 rounded-lg p-4">
                      <div class="flex items-start justify-between gap-4">
                        <div class="min-w-0">
                          <div class="flex items-center gap-2 mb-1.5 flex-wrap">
                            <span class="inline-flex px-2 py-0.5 text-xs font-medium rounded bg-slate-700 text-slate-300 border border-slate-600">
                              {job.provider_type.toUpperCase()}
                            </span>
                            <span class="inline-flex px-2 py-0.5 text-xs font-medium rounded border {getJobStatusClasses(job.status)}">
                              {job.status}
                            </span>
                            <span class="text-xs text-slate-500">{job.trigger}</span>
                          </div>
                          <p class="text-xs text-slate-400">
                            {new Date(job.started_at).toLocaleString()}
                            {#if job.duration_seconds !== null}
                              <span class="text-slate-500 ml-2">{formatDuration(job.duration_seconds)}</span>
                            {/if}
                          </p>
                          {#if job.error_message}
                            <p class="text-xs text-red-400 mt-1.5 break-words">{job.error_message}</p>
                          {/if}
                        </div>
                        <div class="text-right flex-shrink-0">
                          {#if job.records_updated !== null}
                            <p class="text-sm font-mono text-slate-300">{job.records_updated}</p>
                            <p class="text-xs text-slate-500">records</p>
                          {/if}
                          {#if job.regions_requested !== null}
                            <p class="text-xs text-slate-500 mt-1">{job.regions_requested} region{job.regions_requested !== 1 ? 's' : ''}</p>
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
      {/if}
    </div>
  </main>
</div>

<!-- Add/Edit Modal -->
{#if showModal}
  <div class="fixed inset-0 z-50 flex items-center justify-center p-4">
    <!-- Backdrop -->
    <div
      class="absolute inset-0 bg-black/60"
      onclick={closeModal}
      onkeypress={(e) => e.key === 'Escape' && closeModal()}
      role="button"
      tabindex="0"
      aria-label="Close modal"
    ></div>

    <!-- Modal -->
    <div class="relative bg-slate-800 border border-slate-700 rounded-lg w-full max-w-lg max-h-[90vh] overflow-auto">
      <!-- Header -->
      <div class="flex items-center justify-between p-4 border-b border-slate-700">
        <h2 class="text-lg font-medium text-slate-100">
          {modalMode === 'add' ? 'Add Cloud Account' : 'Edit Cloud Account'}
        </h2>
        <button
          onclick={closeModal}
          class="p-1 text-slate-400 hover:text-slate-200 transition-colors"
        >
          <IconX size={20} />
        </button>
      </div>

      <!-- Form -->
      <form onsubmit={(e) => { e.preventDefault(); handleSubmit(); }} class="p-4 space-y-4">
        {#if formError}
          <div class="p-3 bg-red-900/30 border border-red-800 rounded">
            <p class="text-sm text-red-400">{formError}</p>
          </div>
        {/if}

        <!-- Name -->
        <div>
          <label for="account-name" class="block text-xs font-medium text-slate-400 uppercase tracking-wider mb-2">
            Name <span class="text-red-500">*</span>
          </label>
          <input
            id="account-name"
            type="text"
            bind:value={formName}
            placeholder="e.g., Production AWS"
            class="w-full px-3 py-2 bg-slate-900 border border-slate-600 rounded text-sm text-slate-100 placeholder-slate-500 focus:outline-none focus:ring-1 focus:ring-emerald-500 focus:border-emerald-500"
          />
        </div>

        <!-- Provider (only for add mode) -->
        {#if modalMode === 'add'}
          <div>
            <label class="block text-xs font-medium text-slate-400 uppercase tracking-wider mb-2">
              Provider <span class="text-red-500">*</span>
            </label>
            <div class="flex gap-2">
              {#each $providerMetadata as provider}
                <button
                  type="button"
                  onclick={() => { formProvider = provider.provider_type; formCredentials = {}; }}
                  class="flex-1 px-3 py-2 text-sm font-medium rounded border transition-colors {formProvider === provider.provider_type
                    ? 'bg-emerald-900/50 text-emerald-400 border-emerald-700'
                    : 'bg-slate-700 text-slate-400 border-slate-600 hover:text-slate-200'}"
                >
                  {provider.display_name}
                </button>
              {/each}
            </div>
          </div>
        {/if}

        <!-- Credentials -->
        <div>
          <label class="block text-xs font-medium text-slate-400 uppercase tracking-wider mb-2">
            Credentials
          </label>
          {#if modalMode === 'edit'}
            <p class="text-xs text-slate-500 mb-3">Leave all fields blank to keep existing credentials. To update, provide all required fields.</p>
          {/if}
          <div class="space-y-3">
            {#each credentialFields as field}
              <div>
                <label for="cred-{field.key}" class="block text-xs text-slate-500 mb-1">
                  {field.label} {field.required && modalMode === 'add' ? '*' : ''}
                </label>
                {#if field.type === 'textarea'}
                  <textarea
                    id="cred-{field.key}"
                    bind:value={formCredentials[field.key]}
                    placeholder={field.placeholder || (modalMode === 'edit' ? '(unchanged)' : '')}
                    autocomplete="off"
                    rows="4"
                    class="w-full px-3 py-2 bg-slate-900 border border-slate-600 rounded text-sm text-slate-100 placeholder-slate-500 focus:outline-none focus:ring-1 focus:ring-emerald-500 focus:border-emerald-500 font-mono text-xs resize-none"
                  />
                {:else if field.type === 'password'}
                  <input
                    id="cred-{field.key}"
                    type="password"
                    bind:value={formCredentials[field.key]}
                    placeholder={field.placeholder || (modalMode === 'edit' ? '(unchanged)' : '')}
                    autocomplete="new-password"
                    class="w-full px-3 py-2 bg-slate-900 border border-slate-600 rounded text-sm text-slate-100 placeholder-slate-500 focus:outline-none focus:ring-1 focus:ring-emerald-500 focus:border-emerald-500"
                  />
                {:else}
                  <input
                    id="cred-{field.key}"
                    type="text"
                    bind:value={formCredentials[field.key]}
                    placeholder={field.placeholder || ''}
                    class="w-full px-3 py-2 bg-slate-900 border border-slate-600 rounded text-sm text-slate-100 placeholder-slate-500 focus:outline-none focus:ring-1 focus:ring-emerald-500 focus:border-emerald-500"
                  />
                {/if}
              </div>
            {/each}
          </div>
        </div>

        <!-- Region/Zone Selection -->
        {#if regionsList.length > 0}
          <div>
            <label class="block text-xs font-medium text-slate-400 uppercase tracking-wider mb-2">
              {regionLabel} to Scan
            </label>
            <div class="space-y-2">
              <label class="flex items-center gap-2 cursor-pointer">
                <input
                  type="radio"
                  name="region-mode"
                  checked={formAllRegions}
                  onchange={() => { formAllRegions = true; formSelectedRegions = []; }}
                  class="w-4 h-4 text-emerald-600 bg-slate-900 border-slate-600 focus:ring-emerald-500"
                />
                <span class="text-sm text-slate-300">All regions</span>
                <span class="text-xs text-slate-500">(slower, scans everything)</span>
              </label>
              <label class="flex items-center gap-2 cursor-pointer">
                <input
                  type="radio"
                  name="region-mode"
                  checked={!formAllRegions}
                  onchange={() => formAllRegions = false}
                  class="w-4 h-4 text-emerald-600 bg-slate-900 border-slate-600 focus:ring-emerald-500"
                />
                <span class="text-sm text-slate-300">Select specific regions</span>
              </label>
            </div>

            {#if !formAllRegions}
              <div class="mt-3">
                <button
                  type="button"
                  onclick={() => showRegionSelector = !showRegionSelector}
                  class="flex items-center gap-2 w-full px-3 py-2 bg-slate-700 hover:bg-slate-600 border border-slate-600 rounded text-sm text-slate-300 transition-colors"
                >
                  <span class="flex-1 text-left">
                    {formSelectedRegions.length === 0
                      ? 'Select regions...'
                      : `${formSelectedRegions.length} region${formSelectedRegions.length === 1 ? '' : 's'} selected`}
                  </span>
                  {#if showRegionSelector}
                    <IconChevronUp size={16} />
                  {:else}
                    <IconChevronDown size={16} />
                  {/if}
                </button>

                {#if showRegionSelector}
                  <div class="mt-2 max-h-48 overflow-y-auto bg-slate-900 border border-slate-700 rounded p-2 space-y-1">
                    {#each regionsList as region}
                      <label class="flex items-center gap-2 px-2 py-1.5 rounded hover:bg-slate-800 cursor-pointer">
                        <input
                          type="checkbox"
                          checked={formSelectedRegions.includes(region.code)}
                          onchange={() => toggleRegion(region.code)}
                          class="w-3.5 h-3.5 text-emerald-600 bg-slate-900 border-slate-600 rounded focus:ring-emerald-500"
                        />
                        <span class="text-xs text-slate-300 font-mono">{region.code}</span>
                        <span class="text-xs text-slate-500">{region.name}</span>
                      </label>
                    {/each}
                  </div>
                {/if}
              </div>
            {/if}
          </div>
        {/if}

        <!-- Active toggle -->
        <div class="flex items-center gap-3">
          <label class="flex items-center gap-2 cursor-pointer">
            <input
              type="checkbox"
              bind:checked={formIsActive}
              class="w-4 h-4 text-emerald-600 bg-slate-900 border-slate-600 rounded focus:ring-emerald-500 focus:ring-offset-slate-800"
            />
            <span class="text-sm text-slate-300">Account is active</span>
          </label>
        </div>

        <!-- Actions -->
        <div class="flex items-center justify-end gap-3 pt-4 border-t border-slate-700">
          <button
            type="button"
            onclick={closeModal}
            class="px-4 py-2 text-sm font-medium text-slate-300 hover:text-white bg-slate-700 hover:bg-slate-600 rounded transition-colors"
          >
            Cancel
          </button>
          <button
            type="submit"
            disabled={formLoading}
            class="px-4 py-2 bg-emerald-600 hover:bg-emerald-500 disabled:bg-emerald-800 text-white text-sm font-medium rounded transition-colors disabled:cursor-not-allowed"
          >
            {#if formLoading}
              {modalMode === 'add' ? 'Adding...' : 'Saving...'}
            {:else}
              {modalMode === 'add' ? 'Add Account' : 'Save Changes'}
            {/if}
          </button>
        </div>
      </form>
    </div>
  </div>
{/if}

<!-- User Modal -->
{#if showUserModal}
  <div class="fixed inset-0 z-50 flex items-center justify-center p-4">
    <!-- Backdrop -->
    <div
      class="absolute inset-0 bg-black/60"
      onclick={closeUserModal}
      onkeypress={(e) => e.key === 'Escape' && closeUserModal()}
      role="button"
      tabindex="0"
      aria-label="Close modal"
    ></div>

    <!-- Modal -->
    <div class="relative bg-slate-800 border border-slate-700 rounded-lg w-full max-w-md">
      <!-- Header -->
      <div class="flex items-center justify-between p-4 border-b border-slate-700">
        <h2 class="text-lg font-medium text-slate-100">
          {userModalMode === 'add' ? 'Add User' : 'Edit User'}
        </h2>
        <button
          onclick={closeUserModal}
          class="p-1 text-slate-400 hover:text-slate-200 transition-colors"
        >
          <IconX size={20} />
        </button>
      </div>

      <!-- Form -->
      <form onsubmit={(e) => { e.preventDefault(); handleUserSubmit(); }} class="p-4 space-y-4">
        {#if userFormError}
          <div class="p-3 bg-red-900/30 border border-red-800 rounded">
            <p class="text-sm text-red-400">{userFormError}</p>
          </div>
        {/if}

        <!-- Email -->
        <div>
          <label for="user-email" class="block text-xs font-medium text-slate-400 uppercase tracking-wider mb-2">
            Email {#if userModalMode === 'add'}<span class="text-red-500">*</span>{/if}
          </label>
          {#if userModalMode === 'edit'}
            <p class="text-sm text-slate-300">{userFormEmail}</p>
          {:else}
            <input
              id="user-email"
              type="email"
              bind:value={userFormEmail}
              placeholder="user@example.com"
              class="w-full px-3 py-2 bg-slate-900 border border-slate-600 rounded text-sm text-slate-100 placeholder-slate-500 focus:outline-none focus:ring-1 focus:ring-emerald-500 focus:border-emerald-500"
            />
          {/if}
        </div>

        <!-- Full Name -->
        <div>
          <label for="user-name" class="block text-xs font-medium text-slate-400 uppercase tracking-wider mb-2">
            Full Name
          </label>
          <input
            id="user-name"
            type="text"
            bind:value={userFormName}
            placeholder="John Doe"
            class="w-full px-3 py-2 bg-slate-900 border border-slate-600 rounded text-sm text-slate-100 placeholder-slate-500 focus:outline-none focus:ring-1 focus:ring-emerald-500 focus:border-emerald-500"
          />
        </div>

        <!-- Password (only for add mode) -->
        {#if userModalMode === 'add'}
          <div>
            <label for="user-password" class="block text-xs font-medium text-slate-400 uppercase tracking-wider mb-2">
              Temporary Password <span class="text-red-500">*</span>
            </label>
            <input
              id="user-password"
              type="password"
              bind:value={userFormPassword}
              placeholder="Enter a temporary password"
              class="w-full px-3 py-2 bg-slate-900 border border-slate-600 rounded text-sm text-slate-100 placeholder-slate-500 focus:outline-none focus:ring-1 focus:ring-emerald-500 focus:border-emerald-500"
            />
            <p class="mt-1.5 text-xs text-slate-500">
              The user will use this password to log in for the first time.
            </p>
          </div>
        {/if}

        <!-- Role -->
        <div>
          <label class="block text-xs font-medium text-slate-400 uppercase tracking-wider mb-2">
            Role <span class="text-red-500">*</span>
          </label>
          <div class="flex gap-2">
            {#each roleOptions as role}
              <button
                type="button"
                onclick={() => userFormRole = role}
                class="flex-1 px-3 py-2 text-sm font-medium rounded border transition-colors {userFormRole === role
                  ? 'bg-emerald-900/50 text-emerald-400 border-emerald-700'
                  : 'bg-slate-700 text-slate-400 border-slate-600 hover:text-slate-200'}"
              >
                {ROLE_LABELS[role]}
              </button>
            {/each}
          </div>
        </div>

        <!-- Active toggle (only for edit mode) -->
        {#if userModalMode === 'edit'}
          <div class="flex items-center gap-3">
            <label class="flex items-center gap-2 cursor-pointer">
              <input
                type="checkbox"
                bind:checked={userFormIsActive}
                class="w-4 h-4 text-emerald-600 bg-slate-900 border-slate-600 rounded focus:ring-emerald-500 focus:ring-offset-slate-800"
              />
              <span class="text-sm text-slate-300">Account is active</span>
            </label>
          </div>
        {/if}

        <!-- Actions -->
        <div class="flex items-center justify-end gap-3 pt-4 border-t border-slate-700">
          <button
            type="button"
            onclick={closeUserModal}
            class="px-4 py-2 text-sm font-medium text-slate-300 hover:text-white bg-slate-700 hover:bg-slate-600 rounded transition-colors"
          >
            Cancel
          </button>
          <button
            type="submit"
            disabled={userFormLoading}
            class="px-4 py-2 bg-emerald-600 hover:bg-emerald-500 disabled:bg-emerald-800 text-white text-sm font-medium rounded transition-colors disabled:cursor-not-allowed"
          >
            {#if userFormLoading}
              {userModalMode === 'add' ? 'Adding...' : 'Saving...'}
            {:else}
              {userModalMode === 'add' ? 'Add User' : 'Save Changes'}
            {/if}
          </button>
        </div>
      </form>
    </div>
  </div>
{/if}

<!-- Organization Modal -->
{#if showOrgModal}
  <div class="fixed inset-0 z-50 flex items-center justify-center p-4">
    <!-- Backdrop -->
    <div
      class="absolute inset-0 bg-black/60"
      onclick={closeOrgModal}
      onkeypress={(e) => e.key === 'Escape' && closeOrgModal()}
      role="button"
      tabindex="0"
      aria-label="Close modal"
    ></div>

    <!-- Modal -->
    <div class="relative bg-slate-800 border border-slate-700 rounded-lg w-full max-w-md">
      <!-- Header -->
      <div class="flex items-center justify-between p-4 border-b border-slate-700">
        <h2 class="text-lg font-medium text-slate-100">Edit Organization</h2>
        <button
          onclick={closeOrgModal}
          class="p-1 text-slate-400 hover:text-slate-200 transition-colors"
        >
          <IconX size={20} />
        </button>
      </div>

      <!-- Form -->
      <form onsubmit={(e) => { e.preventDefault(); handleOrgSubmit(); }} class="p-4 space-y-4">
        {#if orgFormError}
          <div class="p-3 bg-red-900/30 border border-red-800 rounded">
            <p class="text-sm text-red-400">{orgFormError}</p>
          </div>
        {/if}

        <!-- Name -->
        <div>
          <label for="org-name" class="block text-xs font-medium text-slate-400 uppercase tracking-wider mb-2">
            Name <span class="text-red-500">*</span>
          </label>
          <input
            id="org-name"
            type="text"
            bind:value={orgFormName}
            placeholder="Acme Corporation"
            class="w-full px-3 py-2 bg-slate-900 border border-slate-600 rounded text-sm text-slate-100 placeholder-slate-500 focus:outline-none focus:ring-1 focus:ring-emerald-500 focus:border-emerald-500"
          />
        </div>

        <!-- Slug -->
        <div>
          <label for="org-slug" class="block text-xs font-medium text-slate-400 uppercase tracking-wider mb-2">
            Slug <span class="text-red-500">*</span>
          </label>
          <input
            id="org-slug"
            type="text"
            bind:value={orgFormSlug}
            placeholder="acme-corp"
            class="w-full px-3 py-2 bg-slate-900 border border-slate-600 rounded text-sm text-slate-100 placeholder-slate-500 focus:outline-none focus:ring-1 focus:ring-emerald-500 focus:border-emerald-500 font-mono"
          />
          <p class="mt-1.5 text-xs text-slate-500">
            Lowercase letters, numbers, and hyphens only
          </p>
        </div>

        <!-- Actions -->
        <div class="flex items-center justify-end gap-3 pt-4 border-t border-slate-700">
          <button
            type="button"
            onclick={closeOrgModal}
            class="px-4 py-2 text-sm font-medium text-slate-300 hover:text-white bg-slate-700 hover:bg-slate-600 rounded transition-colors"
          >
            Cancel
          </button>
          <button
            type="submit"
            disabled={orgFormLoading}
            class="px-4 py-2 bg-emerald-600 hover:bg-emerald-500 disabled:bg-emerald-800 text-white text-sm font-medium rounded transition-colors disabled:cursor-not-allowed"
          >
            {#if orgFormLoading}
              Saving...
            {:else}
              Save Changes
            {/if}
          </button>
        </div>
      </form>
    </div>
  </div>
{/if}

<!-- Delete Cloud Account Confirmation Modal -->
{#if showDeleteModal && deleteConfirmAccount}
  <div class="fixed inset-0 z-50 flex items-center justify-center p-4">
    <!-- Backdrop -->
    <div
      class="absolute inset-0 bg-black/60"
      onclick={closeDeleteModal}
      onkeypress={(e) => e.key === 'Escape' && closeDeleteModal()}
      role="button"
      tabindex="0"
      aria-label="Close modal"
    ></div>

    <!-- Modal -->
    <div class="relative bg-slate-800 border border-slate-700 rounded-lg w-full max-w-md">
      <!-- Header -->
      <div class="flex items-center justify-between p-4 border-b border-slate-700">
        <h2 class="text-lg font-medium text-red-400">Delete Cloud Account</h2>
        <button
          onclick={closeDeleteModal}
          class="p-1 text-slate-400 hover:text-slate-200 transition-colors"
        >
          <IconX size={20} />
        </button>
      </div>

      <!-- Content -->
      <div class="p-4 space-y-4">
        <div class="flex items-start gap-3 p-3 bg-red-900/30 border border-red-800 rounded">
          <IconAlertTriangle size={20} class="text-red-500 flex-shrink-0 mt-0.5" />
          <div class="text-sm text-red-200">
            <p class="font-medium mb-1">This action is permanent and cannot be undone.</p>
            <p class="text-red-300">Deleting this account will also permanently remove:</p>
            <ul class="list-disc list-inside mt-1 text-red-300 space-y-0.5">
              <li>All discovered resources</li>
              <li>All execution history for those resources</li>
              <li>All active overrides on those resources</li>
              <li>All state change events</li>
            </ul>
            <p class="mt-2 text-red-300">Policies will not be deleted, but will no longer match any resources from this account.</p>
          </div>
        </div>

        <div>
          <p class="text-sm text-slate-400 mb-2">
            To confirm, type <strong class="text-slate-200">{deleteConfirmAccount.name}</strong> below:
          </p>
          <input
            type="text"
            bind:value={deleteConfirmText}
            placeholder={deleteConfirmAccount.name}
            class="w-full px-3 py-2 bg-slate-900 border border-slate-600 rounded text-sm text-slate-100 placeholder-slate-500 focus:outline-none focus:ring-1 focus:ring-red-500 focus:border-red-500"
          />
        </div>

        <div class="flex items-center justify-end gap-3 pt-2">
          <button
            type="button"
            onclick={closeDeleteModal}
            class="px-4 py-2 text-sm font-medium text-slate-300 hover:text-white bg-slate-700 hover:bg-slate-600 rounded transition-colors"
          >
            Cancel
          </button>
          <button
            onclick={confirmDelete}
            disabled={deleteConfirmText !== deleteConfirmAccount.name}
            class="px-4 py-2 bg-red-600 hover:bg-red-500 disabled:bg-red-900 disabled:text-red-400 text-white text-sm font-medium rounded transition-colors disabled:cursor-not-allowed"
          >
            Delete Account
          </button>
        </div>
      </div>
    </div>
  </div>
{/if}
