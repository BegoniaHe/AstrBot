import { mount, type MountingOptions } from '@vue/test-utils';
import { createPinia } from 'pinia';
import type { Component } from 'vue';
import vuetify from '@/plugins/vuetify';

export function mountWithVuetify(
  component: Component,
  options: MountingOptions<unknown> = {},
) {
  const globalOptions = options.global ?? {};
  const pinia = createPinia();

  return mount(component as never, {
    attachTo: document.body,
    ...options,
    global: {
      ...globalOptions,
      plugins: [pinia, vuetify, ...(globalOptions.plugins ?? [])],
      renderStubDefaultSlot: true,
    },
  });
}
