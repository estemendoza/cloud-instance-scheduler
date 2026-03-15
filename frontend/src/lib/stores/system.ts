import { writable } from 'svelte/store';

interface SystemState {
  bootstrapped: boolean;
  version: string;
}

export const systemStore = writable<SystemState>({
  bootstrapped: false,
  version: ''
});
