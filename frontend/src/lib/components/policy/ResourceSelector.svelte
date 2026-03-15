<script lang="ts">
  import { createEventDispatcher, onMount } from 'svelte';
  import { resourcesAPI } from '$lib/api/endpoints/resources';
  import type { ResourceSelector } from '$lib/types/policy';
  import type { Resource } from '$lib/types/resource';

  export let value: ResourceSelector = { tags: {} };
  export let disabled = false;

  const dispatch = createEventDispatcher<{ change: ResourceSelector }>();

  let mode: 'tags' | 'resource_ids' = 'tags' in value ? 'tags' : 'resource_ids';

  // Tag mode state
  let tags: Array<{ key: string; value: string }> = [];

  // Resource IDs mode state
  let selectedResourceIds: string[] = [];
  let resources: Resource[] = [];
  let loadingResources = false;

  // Initialize from value
  $: initializeFromValue(value);

  function initializeFromValue(v: ResourceSelector) {
    if ('tags' in v) {
      mode = 'tags';
      tags = Object.entries(v.tags).map(([key, val]) => ({ key, value: val }));
      if (tags.length === 0) {
        tags = [{ key: '', value: '' }];
      }
    } else if ('resource_ids' in v) {
      mode = 'resource_ids';
      selectedResourceIds = v.resource_ids;
    }
  }

  onMount(async () => {
    await loadResources();
  });

  async function loadResources() {
    loadingResources = true;
    try {
      const result = await resourcesAPI.list({ page_size: 100 });
      resources = result.items;
    } catch (err) {
      console.error('Failed to load resources:', err);
    } finally {
      loadingResources = false;
    }
  }

  function handleModeChange() {
    if (mode === 'tags') {
      tags = [{ key: '', value: '' }];
      emitChange();
    } else {
      selectedResourceIds = [];
      emitChange();
    }
  }

  function addTag() {
    tags = [...tags, { key: '', value: '' }];
  }

  function removeTag(index: number) {
    tags = tags.filter((_, i) => i !== index);
    if (tags.length === 0) {
      tags = [{ key: '', value: '' }];
    }
    emitChange();
  }

  function handleTagChange() {
    emitChange();
  }

  function toggleResource(resourceId: string) {
    if (selectedResourceIds.includes(resourceId)) {
      selectedResourceIds = selectedResourceIds.filter(id => id !== resourceId);
    } else {
      selectedResourceIds = [...selectedResourceIds, resourceId];
    }
    emitChange();
  }

  function emitChange() {
    let newValue: ResourceSelector;

    if (mode === 'tags') {
      const tagMap: Record<string, string> = {};
      for (const tag of tags) {
        if (tag.key.trim()) {
          tagMap[tag.key.trim()] = tag.value.trim();
        }
      }
      newValue = { tags: tagMap };
    } else {
      newValue = { resource_ids: selectedResourceIds };
    }

    dispatch('change', newValue);
  }
</script>

<div class="resource-selector">
  <!-- Mode Toggle -->
  <div class="flex items-center gap-4 mb-4">
    <label class="flex items-center gap-2 cursor-pointer">
      <input
        type="radio"
        bind:group={mode}
        value="tags"
        on:change={handleModeChange}
        {disabled}
        class="w-4 h-4 text-emerald-600 bg-slate-900 border-slate-600 focus:ring-emerald-500 focus:ring-offset-slate-800"
      />
      <span class="text-sm text-slate-300">Select by Tags</span>
    </label>
    <label class="flex items-center gap-2 cursor-pointer">
      <input
        type="radio"
        bind:group={mode}
        value="resource_ids"
        on:change={handleModeChange}
        {disabled}
        class="w-4 h-4 text-emerald-600 bg-slate-900 border-slate-600 focus:ring-emerald-500 focus:ring-offset-slate-800"
      />
      <span class="text-sm text-slate-300">Select Specific Resources</span>
    </label>
  </div>

  <!-- Tags Mode -->
  {#if mode === 'tags'}
    <div class="space-y-2">
      <p class="text-xs text-slate-500">Resources matching ALL tags will be included</p>

      {#each tags as tag, index}
        <div class="flex items-center gap-2">
          <input
            type="text"
            bind:value={tag.key}
            on:input={handleTagChange}
            placeholder="Tag key"
            {disabled}
            class="flex-1 px-3 py-2 bg-slate-900 border border-slate-600 rounded text-sm text-slate-100 placeholder-slate-500 focus:outline-none focus:ring-1 focus:ring-emerald-500 focus:border-emerald-500 disabled:opacity-50"
          />
          <span class="text-slate-500">=</span>
          <input
            type="text"
            bind:value={tag.value}
            on:input={handleTagChange}
            placeholder="Tag value"
            {disabled}
            class="flex-1 px-3 py-2 bg-slate-900 border border-slate-600 rounded text-sm text-slate-100 placeholder-slate-500 focus:outline-none focus:ring-1 focus:ring-emerald-500 focus:border-emerald-500 disabled:opacity-50"
          />
          <button
            type="button"
            on:click={() => removeTag(index)}
            {disabled}
            class="p-2 text-slate-500 hover:text-red-400 disabled:opacity-50 disabled:cursor-not-allowed"
            aria-label="Remove tag"
          >
            <svg class="w-4 h-4" fill="none" viewBox="0 0 24 24" stroke="currentColor">
              <path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M6 18L18 6M6 6l12 12" />
            </svg>
          </button>
        </div>
      {/each}

      {#if !disabled}
        <button
          type="button"
          on:click={addTag}
          class="flex items-center gap-1 text-sm text-emerald-500 hover:text-emerald-400"
        >
          <svg class="w-4 h-4" fill="none" viewBox="0 0 24 24" stroke="currentColor">
            <path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M12 4v16m8-8H4" />
          </svg>
          Add Tag
        </button>
      {/if}
    </div>
  {/if}

  <!-- Resource IDs Mode -->
  {#if mode === 'resource_ids'}
    <div>
      <p class="text-xs text-slate-500 mb-2">Select specific resources to include</p>

      {#if loadingResources}
        <div class="flex items-center justify-center py-4">
          <div class="animate-spin rounded-full h-5 w-5 border-2 border-slate-700 border-t-emerald-500"></div>
        </div>
      {:else if resources.length === 0}
        <div class="text-center py-4 text-slate-500 text-sm">
          No resources available
        </div>
      {:else}
        <div class="max-h-48 overflow-y-auto border border-slate-700 rounded bg-slate-900/50">
          {#each resources as resource}
            <label
              class="flex items-center gap-3 px-3 py-2 hover:bg-slate-800 cursor-pointer border-b border-slate-800 last:border-b-0"
            >
              <input
                type="checkbox"
                checked={selectedResourceIds.includes(resource.id)}
                on:change={() => toggleResource(resource.id)}
                {disabled}
                class="w-4 h-4 text-emerald-600 bg-slate-900 border-slate-600 rounded focus:ring-emerald-500 focus:ring-offset-slate-800"
              />
              <div class="flex-1 min-w-0">
                <div class="text-sm text-slate-200 truncate">{resource.name}</div>
                <div class="text-xs text-slate-500">
                  {resource.provider} · {resource.region}
                  {#if resource.state}
                    · <span class={resource.state === 'RUNNING' ? 'text-emerald-500' : 'text-slate-400'}>{resource.state}</span>
                  {/if}
                </div>
              </div>
            </label>
          {/each}
        </div>

        <div class="text-xs text-slate-500 mt-2">
          {selectedResourceIds.length} resource{selectedResourceIds.length !== 1 ? 's' : ''} selected
        </div>
      {/if}
    </div>
  {/if}
</div>
