import { describe, expect, it } from 'vitest';
import { nextTick } from 'vue';
import ProviderSourcesPanel from '@/components/provider/ProviderSourcesPanel.vue';
import { mountWithVuetify } from './utils/mountWithVuetify';

const displayedProviderSources = [
  {
    id: 'openai-main',
    provider: 'openai',
    api_base: 'https://api.openai.com/v1',
  },
  {
    templateKey: 'anthropic',
    isPlaceholder: true,
    api_base: '',
  },
];

describe('ProviderSourcesPanel', () => {
  it('renders provider source entries and emits list actions', async () => {
    const wrapper = mountWithVuetify(ProviderSourcesPanel, {
      props: {
        displayedProviderSources,
        selectedProviderSource: displayedProviderSources[0],
        availableSourceTypes: [{ value: 'openai', label: 'OpenAI' }],
        tm: (key: string) => key,
        resolveSourceIcon: () => '/icons/openai.svg',
        getSourceDisplayName: (source: { id?: string; templateKey?: string }) =>
          source.id || `template:${source.templateKey}`,
      },
    });

    expect(wrapper.findAll('button.provider-source-item')).toHaveLength(2);
    expect(wrapper.text()).toContain('openai-main');
    expect(wrapper.text()).toContain('template:anthropic');

    await wrapper.find('button.provider-source-item').trigger('click');
    expect(wrapper.emitted('select-provider-source')?.[0]).toEqual([
      displayedProviderSources[0],
    ]);

    await wrapper.find('.provider-sources-mobile-delete').trigger('click');
    expect(wrapper.emitted('delete-provider-source')?.[0]).toEqual([
      displayedProviderSources[0],
    ]);
  });

  it('maps the mobile selector value back to the source record', async () => {
    const wrapper = mountWithVuetify(ProviderSourcesPanel, {
      props: {
        displayedProviderSources,
        selectedProviderSource: displayedProviderSources[0],
        availableSourceTypes: [{ value: 'openai', label: 'OpenAI' }],
        tm: (key: string) => key,
        resolveSourceIcon: () => '/icons/openai.svg',
        getSourceDisplayName: (source: { id?: string; templateKey?: string }) =>
          source.id || `template:${source.templateKey}`,
      },
    });

    const select = wrapper.findComponent({ name: 'VSelect' });
    select.vm.$emit('update:modelValue', 'source:openai-main');
    await nextTick();

    expect(wrapper.emitted('select-provider-source')?.[0]).toEqual([
      displayedProviderSources[0],
    ]);
  });
});
