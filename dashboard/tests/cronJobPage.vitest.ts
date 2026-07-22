import { flushPromises } from '@vue/test-utils';
import { beforeEach, describe, expect, it, vi } from 'vitest';
import CronJobPage from '@/views/CronJobPage.vue';
import { mountWithVuetify } from './utils/mountWithVuetify';

const api = vi.hoisted(() => ({
  list: vi.fn(),
  create: vi.fn(),
  update: vi.fn(),
  delete: vi.fn(),
  run: vi.fn(),
  stats: vi.fn(),
  activeUmos: vi.fn(),
}));

vi.mock('@/api/v1', () => ({
  cronApi: {
    list: api.list,
    create: api.create,
    update: api.update,
    delete: api.delete,
    run: api.run,
  },
  botApi: { stats: api.stats },
  sessionApi: { activeUmos: api.activeUmos },
}));

vi.mock('@/components/shared/OutlinedActionListItem.vue', () => ({
  default: {
    props: ['title'],
    emits: ['click'],
    template: `
      <article class="cron-job-card" @click="$emit('click')">
        <strong class="cron-job-title">{{ title }}</strong>
        <slot />
        <div class="cron-job-actions"><slot name="actions" /></div>
        <div class="cron-job-control"><slot name="control" /></div>
      </article>
    `,
  },
}));

vi.mock('@/components/shared/StyledMenu.vue', () => ({
  default: {
    template:
      '<div class="styled-menu-stub"><slot name="activator" :props="{}" /><slot /></div>',
  },
}));

vi.mock('@/components/shared/UmoDisplay.vue', () => ({
  default: {
    template: '<span class="umo-display-stub"></span>',
  },
}));

const listItemStub = {
  emits: ['click'],
  template:
    '<button class="cron-menu-item" type="button" @click="$emit(\'click\', $event)"><slot /></button>',
};

function response(data: unknown) {
  return { data: { status: 'ok', data } };
}

describe('CronJobPage', () => {
  beforeEach(() => {
    vi.clearAllMocks();
    api.list.mockResolvedValue(
      response([
        {
          job_id: 'job-1',
          name: 'Deliver update',
          note: 'Send the daily update',
          enabled: true,
          cron_expression: '0 9 * * *',
          session: 'telegram:GroupMessage:chat-1',
        },
      ]),
    );
    api.stats.mockResolvedValue(response({ platforms: [] }));
    api.activeUmos.mockResolvedValue(response({ umos: [], umo_infos: [] }));
  });

  it('suppresses duplicate Run now requests while the first request is still pending', async () => {
    let resolveRun: ((value: ReturnType<typeof response>) => void) | undefined;
    api.run.mockImplementation(
      () =>
        new Promise<ReturnType<typeof response>>((resolve) => {
          resolveRun = resolve;
        }),
    );
    const wrapper = mountWithVuetify(CronJobPage, {
      global: {
        stubs: {
          VListItem: listItemStub,
          VListItemTitle: { template: '<span><slot /></span>' },
        },
      },
    });
    await flushPromises();

    const runButton = wrapper
      .findAll('.cron-menu-item')
      .find((item) => item.text().includes('Run now'));
    expect(runButton).toBeDefined();

    await runButton!.trigger('click');
    await runButton!.trigger('click');
    await flushPromises();

    expect(api.run).toHaveBeenCalledTimes(1);
    expect(api.run).toHaveBeenCalledWith('job-1');

    resolveRun!(response({}));
    await flushPromises();

    expect(api.list).toHaveBeenCalledTimes(2);
    wrapper.unmount();
  });
});
