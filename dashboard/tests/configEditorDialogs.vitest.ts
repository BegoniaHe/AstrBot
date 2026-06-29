import { describe, expect, it } from 'vitest';
import { flushPromises } from '@vue/test-utils';
import ListConfigItem from '@/components/shared/ListConfigItem.vue';
import ObjectEditor from '@/components/shared/ObjectEditor.vue';
import { mountWithVuetify } from './utils/mountWithVuetify';

describe('config editor dialog layouts', () => {
  it('renders the list editor inside a constrained scrollable dialog', async () => {
    const wrapper = mountWithVuetify(ListConfigItem, {
      props: {
        modelValue: ['alpha', 'beta'],
        preferSingleItem: false,
      },
    });

    await wrapper.find('button').trigger('click');
    await flushPromises();

    expect(
      document.body.querySelector('.list-config-dialog__card'),
    ).not.toBeNull();
    expect(
      document.body.querySelector('.list-config-dialog__content'),
    ).not.toBeNull();

    wrapper.unmount();
  });

  it('renders the object editor inside a constrained scrollable dialog', async () => {
    const wrapper = mountWithVuetify(ObjectEditor, {
      props: {
        modelValue: {
          Authorization: 'Bearer token',
          'X-Custom-Header': 'astrbot',
        },
      },
    });

    await wrapper.find('button').trigger('click');
    await flushPromises();

    expect(
      document.body.querySelector('.object-editor-dialog__card'),
    ).not.toBeNull();
    expect(
      document.body.querySelector('.object-editor-dialog__content'),
    ).not.toBeNull();

    wrapper.unmount();
  });
});
