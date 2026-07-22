import { flushPromises } from '@vue/test-utils';
import { beforeEach, describe, expect, it, vi } from 'vitest';
import KBList from '@/views/knowledge-base/KBList.vue';
import { mountWithVuetify } from './utils/mountWithVuetify';

const api = vi.hoisted(() => ({
  list: vi.fn(),
  create: vi.fn(),
  update: vi.fn(),
  delete: vi.fn(),
  providers: vi.fn(),
}));

vi.mock('@/api/v1', () => ({
  knowledgeApi: {
    list: api.list,
    create: api.create,
    update: api.update,
    delete: api.delete,
  },
  providerApi: {
    listByProviderType: api.providers,
  },
}));

vi.mock('vue-router', () => ({
  useRouter: () => ({ push: vi.fn() }),
}));

vi.mock('@/components/shared/OutlinedActionListItem.vue', () => ({
  default: {
    props: ['title'],
    template:
      '<article class="knowledge-base-card"><strong>{{ title }}</strong><slot /><slot name="actions" /></article>',
  },
}));

function response(data: unknown) {
  return { data: { status: 'ok', data } };
}

describe('KBList', () => {
  beforeEach(() => {
    vi.clearAllMocks();
    api.list.mockResolvedValue(response({ items: [] }));
    api.providers.mockResolvedValue(response([]));
  });

  it('keeps a rejected list request generic in both the visible snackbar and console diagnostics', async () => {
    const errorSpy = vi.spyOn(console, 'error').mockImplementation(() => {});
    api.list.mockRejectedValue(
      new Error(
        'api_key=knowledge-secret at http://internal.example/knowledge',
      ),
    );
    const wrapper = mountWithVuetify(KBList);
    await flushPromises();

    expect(document.body.textContent).toContain(
      'Failed to load knowledge base list',
    );
    expect(document.body.textContent).not.toContain('knowledge-secret');
    expect(errorSpy.mock.calls.flat().join(' ')).not.toContain(
      'knowledge-secret',
    );
    expect(errorSpy.mock.calls.flat().join(' ')).not.toContain(
      'internal.example',
    );

    wrapper.unmount();
  });
});
