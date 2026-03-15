import { writable, derived } from 'svelte/store';
import { providersAPI, type ProviderMetadata } from '$lib/api/endpoints/providers';

const _metadata = writable<ProviderMetadata[]>([]);
let _loaded = false;

export const providerMetadata = { subscribe: _metadata.subscribe };

export const providerLabels = derived(_metadata, ($m) => {
  const labels: Record<string, string> = {};
  for (const p of $m) labels[p.provider_type] = p.display_name;
  return labels;
});

export const providerTypes = derived(_metadata, ($m) =>
  $m.map((p) => p.provider_type)
);

export async function loadProviderMetadata(): Promise<void> {
  if (_loaded) return;
  try {
    const data = await providersAPI.getMetadata();
    _metadata.set(data);
    _loaded = true;
  } catch (err) {
    console.error('Failed to load provider metadata', err);
  }
}

export function getProviderMeta(
  providers: ProviderMetadata[],
  type: string
): ProviderMetadata | undefined {
  return providers.find((p) => p.provider_type === type);
}
