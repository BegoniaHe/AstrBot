import { flushPromises } from '@vue/test-utils';
import { beforeEach, describe, expect, it, vi } from 'vitest';
import TracePage from '@/views/TracePage.vue';
import { mountWithVuetify } from './utils/mountWithVuetify';

const api = vi.hoisted(() => ({
  getSettings: vi.fn(),
  updateSettings: vi.fn(),
}));

vi.mock('@/api/v1', () => ({
  traceApi: api,
}));

vi.mock('@/components/shared/TraceDisplayer.vue', () => ({
  default: {
    template: '<div data-testid="trace-displayer"></div>',
  },
}));

function traceToggle(wrapper: ReturnType<typeof mountWithVuetify>) {
  return wrapper.get('input[type="checkbox"]');
}

describe('TracePage', () => {
  beforeEach(() => {
    vi.clearAllMocks();
    api.getSettings.mockResolvedValue({
      data: { status: 'ok', data: { enabled: true } },
    });
  });

  it('reflects the setting supplied during initialization', async () => {
    const wrapper = mountWithVuetify(TracePage);
    await flushPromises();

    expect(api.getSettings).toHaveBeenCalledOnce();
    expect(traceToggle(wrapper).element.checked).toBe(true);
    expect(wrapper.find('[data-testid="trace-displayer"]').exists()).toBe(true);
  });

  it('rolls a failed trace-setting update back to the last confirmed value', async () => {
    const errorSpy = vi.spyOn(console, 'error').mockImplementation(() => {});
    api.updateSettings.mockResolvedValue({
      data: {
        status: 'error',
        message: 'Bearer trace-secret at http://internal.example/trace',
      },
    });
    const wrapper = mountWithVuetify(TracePage);
    await flushPromises();

    await traceToggle(wrapper).setValue(false);
    await flushPromises();

    expect(api.updateSettings).toHaveBeenCalledWith({ enabled: false });
    expect(traceToggle(wrapper).element.checked).toBe(true);
    expect(wrapper.text()).toContain(
      'Unable to update trace settings. Please try again.',
    );
    expect(wrapper.text()).not.toContain('trace-secret');
    expect(wrapper.text()).not.toContain('internal.example');
    expect(errorSpy).toHaveBeenCalledWith('Failed to update trace settings');
    expect(errorSpy.mock.calls.flat().join(' ')).not.toContain('trace-secret');
  });
});
