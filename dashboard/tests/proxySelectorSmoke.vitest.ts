import { beforeEach, describe, expect, it, vi } from 'vitest';
import { flushPromises } from '@vue/test-utils';
import ProxySelector from '@/components/shared/ProxySelector.vue';
import { mountWithVuetify } from './utils/mountWithVuetify';

const testState = vi.hoisted(() => ({
  testGhproxyMock: vi.fn(),
  readGitHubProxyStateMock: vi.fn(),
  writeGitHubProxyControlMock: vi.fn(),
  writeGitHubProxyRadioValueMock: vi.fn(),
  writeSelectedGitHubProxyMock: vi.fn(),
}));

vi.mock('@/api/v1', () => ({
  statsApi: {
    testGhproxy: testState.testGhproxyMock,
  },
}));

vi.mock('@/utils/githubProxyStorage', () => ({
  readGitHubProxyState: testState.readGitHubProxyStateMock,
  writeGitHubProxyControl: testState.writeGitHubProxyControlMock,
  writeGitHubProxyRadioValue: testState.writeGitHubProxyRadioValueMock,
  writeSelectedGitHubProxy: testState.writeSelectedGitHubProxyMock,
}));

function expectNoRuntimeWarnings(calls: unknown[][]) {
  const warningTexts = calls.flatMap((args) => args.map((arg) => String(arg)));
  expect(
    warningTexts.some(
      (text) =>
        text.includes('Translation key not found') ||
        text.includes('Extraneous non-props attributes') ||
        text.includes(
          'Component inside <Transition> renders non-element root node',
        ),
    ),
  ).toBe(false);
}

describe('ProxySelector smoke', () => {
  beforeEach(() => {
    vi.clearAllMocks();

    testState.readGitHubProxyStateMock.mockReturnValue({
      radioValue: '0',
      control: '0',
      selectedProxy: '',
    });
    testState.testGhproxyMock.mockImplementation(
      async ({ proxy_url }: { proxy_url: string }) => {
        if (proxy_url.includes('edgeone')) {
          return {
            status: 200,
            data: { data: { latency: 123 } },
          };
        }
        if (proxy_url.includes('gh.dpik.top')) {
          return {
            status: 200,
            data: { data: { latency: '87.6' } },
          };
        }
        if (proxy_url.includes('hk.gh-proxy.com')) {
          throw new Error('network unreachable');
        }
        return {
          status: 503,
          data: { data: { latency: 0 } },
        };
      },
    );
  });

  it('renders proxy test results without runtime warnings after enabling proxy mode', async () => {
    const warnSpy = vi.spyOn(console, 'warn').mockImplementation(() => {});

    const wrapper = mountWithVuetify(ProxySelector, {
      attrs: {
        class: 'proxy-selector-test',
      },
    });

    await flushPromises();

    expect(wrapper.classes()).toContain('proxy-selector-test');
    expect(wrapper.find('.proxy-selector__list').exists()).toBe(false);

    const [modeGroup] = wrapper.findAllComponents({ name: 'VRadioGroup' });
    modeGroup.vm.$emit('update:modelValue', '1');
    await flushPromises();

    expect(testState.writeGitHubProxyRadioValueMock).toHaveBeenCalledWith('1');
    expect(wrapper.find('.proxy-selector__list').exists()).toBe(true);

    await wrapper.find('.proxy-selector__mode .v-btn').trigger('click');
    await flushPromises();

    expect(testState.testGhproxyMock).toHaveBeenCalledTimes(4);
    expect(wrapper.text()).toContain("Don't use GitHub Proxy");
    expect(wrapper.text()).toContain('Use GitHub Proxy');
    expect(wrapper.text()).toContain('Available');
    expect(wrapper.text()).toContain('Unavailable');
    expect(wrapper.text()).toContain('123ms');
    expect(wrapper.text()).toContain('88ms');
    expectNoRuntimeWarnings(warnSpy.mock.calls);
  });

  it('renders the custom proxy input and persists updates without attr or transition warnings', async () => {
    const warnSpy = vi.spyOn(console, 'warn').mockImplementation(() => {});

    const wrapper = mountWithVuetify(ProxySelector);

    await flushPromises();

    const [modeGroup] = wrapper.findAllComponents({ name: 'VRadioGroup' });
    modeGroup.vm.$emit('update:modelValue', '1');
    await flushPromises();

    const groups = wrapper.findAllComponents({ name: 'VRadioGroup' });
    groups[1].vm.$emit('update:modelValue', '-1');
    await flushPromises();

    expect(testState.writeGitHubProxyControlMock).toHaveBeenCalledWith('-1');
    expect(wrapper.find('.proxy-selector__custom-input').exists()).toBe(true);

    const customInput = wrapper.find('.proxy-selector__custom-input input');
    expect(customInput.exists()).toBe(true);

    await customInput.setValue('https://mirror.example.com');
    await flushPromises();

    expect(testState.writeSelectedGitHubProxyMock).toHaveBeenCalledWith(
      'https://mirror.example.com',
    );
    expectNoRuntimeWarnings(warnSpy.mock.calls);
  });
});
