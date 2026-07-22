import { flushPromises } from '@vue/test-utils';
import { afterEach, beforeEach, describe, expect, it, vi } from 'vitest';
import StatsPage from '@/views/stats/StatsPage.vue';
import { mountWithVuetify } from './utils/mountWithVuetify';

const api = vi.hoisted(() => ({
  get: vi.fn(),
  providerTokens: vi.fn(),
  t2iRuntime: vi.fn(),
}));

vi.mock('@/api/v1', () => ({
  statsApi: api,
}));

vi.mock('vue3-apexcharts', () => ({
  default: {
    template: '<div class="chart-stub"></div>',
  },
}));

const baseStats = {
  message_count: 12,
  platform_count: 1,
  platform: [],
  message_time_series: [],
  memory: { process: 256, system: 1024 },
  cpu_percent: 1.5,
  running: { hours: 1, minutes: 2, seconds: 3 },
  thread_count: 4,
  start_time: 1_700_000_000,
};

const providerStats = {
  days: 1,
  trend: { series: [], total_series: [] },
  range_total_tokens: 3,
  range_total_calls: 2,
  range_avg_ttft_ms: 100,
  range_avg_duration_ms: 200,
  range_avg_tpm: 300,
  range_success_rate: 1,
  range_by_provider: [],
  range_by_umo: [],
  today_total_tokens: 3,
  today_total_calls: 2,
  today_by_provider: [],
};

const t2iRuntime = {
  render_in_progress: 0,
  active_pages: 0,
  peak_active_pages: 0,
  successful_renders: 0,
  failed_renders: 0,
  cancelled_renders: 0,
  total_render_duration_ms: 0,
  last_render_duration_ms: 0,
  average_render_duration_ms: 0,
  max_render_duration_ms: 0,
  output_bytes: 0,
  browser_starts: 0,
  browser_restarts: 0,
  browser_connected: false,
  context_count: 0,
};

describe('StatsPage', () => {
  beforeEach(() => {
    vi.clearAllMocks();
    api.get.mockResolvedValue({ data: { data: baseStats } });
    api.providerTokens.mockResolvedValue({ data: { data: providerStats } });
    api.t2iRuntime.mockResolvedValue({ data: { data: t2iRuntime } });
  });

  afterEach(() => {
    vi.restoreAllMocks();
  });

  it('keeps the loaded statistics visible and reports a generic error when a range refresh fails', async () => {
    const errorSpy = vi.spyOn(console, 'error').mockImplementation(() => {});
    api.providerTokens.mockResolvedValueOnce({
      data: { data: providerStats },
    });
    api.providerTokens.mockRejectedValueOnce(
      new Error('Bearer stats-token at http://internal.example/stats'),
    );
    const wrapper = mountWithVuetify(StatsPage);
    await flushPromises();

    expect(wrapper.text()).toContain('Platform Instances');
    await wrapper.findAll('button.range-chip')[1]!.trigger('click');
    await flushPromises();

    expect(api.get).toHaveBeenLastCalledWith(3 * 24 * 60 * 60);
    expect(api.providerTokens).toHaveBeenLastCalledWith(3);
    expect(wrapper.text()).toContain(
      'Failed to switch the statistics range. Please try again later.',
    );
    expect(wrapper.text()).not.toContain('stats-token');
    expect(wrapper.text()).toContain('Platform Instances');
    expect(errorSpy).toHaveBeenCalledWith('Failed to refresh stats range');
    expect(errorSpy.mock.calls.flat().join(' ')).not.toContain('stats-token');

    wrapper.unmount();
  });

  it('releases the periodic refresh interval on unmount', async () => {
    const clearIntervalSpy = vi.spyOn(window, 'clearInterval');
    const wrapper = mountWithVuetify(StatsPage);
    await flushPromises();

    wrapper.unmount();

    expect(clearIntervalSpy).toHaveBeenCalled();
  });
});
