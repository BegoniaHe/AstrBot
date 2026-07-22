import { flushPromises } from '@vue/test-utils';
import { beforeEach, describe, expect, it, vi } from 'vitest';
import SessionManagementPage from '@/views/SessionManagementPage.vue';
import { mountWithVuetify } from './utils/mountWithVuetify';

const api = vi.hoisted(() => ({
  listRules: vi.fn(),
  activeUmos: vi.fn(),
  upsertRule: vi.fn(),
  deleteRules: vi.fn(),
  batchUpdateProvider: vi.fn(),
  batchUpdateService: vi.fn(),
  listGroups: vi.fn(),
  createGroup: vi.fn(),
  updateGroup: vi.fn(),
  deleteGroup: vi.fn(),
}));

vi.mock('@/api/v1', () => ({
  sessionApi: api,
}));

vi.mock('@/components/shared/UmoDisplay.vue', () => ({
  default: {
    template: '<span class="umo-display-stub"></span>',
  },
}));

vi.mock('@/utils/confirmDialog', () => ({
  askForConfirmation: vi.fn(),
  useConfirmDialog: () => undefined,
}));

vi.mock('@/utils/platformUtils', () => ({
  getPlatformColor: () => 'primary',
}));

const dataTableStub = {
  template: '<div class="session-table-stub"><slot name="no-data" /></div>',
};

function response(data: unknown) {
  return { data: { status: 'ok', data } };
}

describe('SessionManagementPage', () => {
  beforeEach(() => {
    vi.clearAllMocks();
    api.listGroups.mockResolvedValue(response({ groups: [] }));
    api.activeUmos.mockResolvedValue(response({ umos: [], umo_infos: [] }));
  });

  it('does not expose a sensitive transport failure while loading session rules', async () => {
    api.listRules.mockRejectedValue(
      new Error('Bearer session-secret at http://internal.example/sessions'),
    );
    const wrapper = mountWithVuetify(SessionManagementPage, {
      global: {
        stubs: { VDataTableServer: dataTableStub },
      },
    });
    await flushPromises();

    expect(document.body.textContent).toContain('Failed to load data');
    expect(document.body.textContent).not.toContain('session-secret');
    expect(document.body.textContent).not.toContain('internal.example');

    wrapper.unmount();
  });

  it('keeps an explicit business validation message from the session API', async () => {
    api.listRules.mockResolvedValue({
      data: {
        status: 'error',
        message: 'A custom group must contain at least one session',
      },
    });
    const wrapper = mountWithVuetify(SessionManagementPage, {
      global: {
        stubs: { VDataTableServer: dataTableStub },
      },
    });
    await flushPromises();

    expect(document.body.textContent).toContain(
      'A custom group must contain at least one session',
    );

    wrapper.unmount();
  });
});
