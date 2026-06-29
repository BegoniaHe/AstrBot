import { describe, expect, it, vi } from 'vitest';
import { flushPromises } from '@vue/test-utils';
import { ref } from 'vue';
import InstalledPluginsTab from '@/views/extension/InstalledPluginsTab.vue';
import MarketPluginsTab from '@/views/extension/MarketPluginsTab.vue';
import ReadmeDialog from '@/components/shared/ReadmeDialog.vue';
import { mountWithVuetify } from './utils/mountWithVuetify';

vi.mock('@/components/shared/ExtensionCard.vue', () => ({
  default: {
    props: ['extension', 'isPinned'],
    template:
      '<div class="extension-card-stub">{{ extension.name }}|{{ String(isPinned) }}</div>',
  },
}));

vi.mock('@/components/extension/MarketPluginCard.vue', () => ({
  default: {
    props: ['plugin'],
    template: '<div class="market-plugin-card-stub">{{ plugin.name }}</div>',
  },
}));

vi.mock('@/components/extension/PluginSortControl.vue', () => ({
  default: {
    props: ['modelValue', 'items', 'label', 'order'],
    template: '<div class="plugin-sort-control-stub">{{ label }}</div>',
  },
}));

vi.mock('@/api/v1', () => ({
  pluginApi: {
    readme: vi.fn(async () => ({
      data: {
        status: 'ok',
        data: {
          content: Array.from({ length: 120 }, (_, index) => `Line ${index}`)
            .join('\n\n'),
        },
      },
    })),
    changelog: vi.fn(async () => ({
      data: { status: 'ok', data: { content: 'Changelog' } },
    })),
  },
  statsApi: {
    firstNotice: vi.fn(async () => ({
      data: { status: 'ok', data: { content: 'Notice' } },
    })),
  },
}));

function warningTexts(calls: unknown[][]) {
  return calls.flatMap((args) => args.map((arg) => String(arg)));
}

function expectNoExtensionWarnings(calls: unknown[][]) {
  const texts = warningTexts(calls);
  const blockedWarnings = [
    'Failed to resolve component: v-tab-item',
    "'dense' is deprecated",
    'theme.global.name.value',
    'Translation key not found',
    'Extraneous non-props attributes',
    'Unhandled error during execution',
  ];

  expect(
    texts.some((text) =>
      blockedWarnings.some((warning) => text.includes(warning)),
    ),
  ).toBe(false);
}

describe('extension runtime smokes', () => {
  it('renders InstalledPluginsTab without deprecated tab component warnings', async () => {
    const warnSpy = vi.spyOn(console, 'warn').mockImplementation(() => {});

    const wrapper = mountWithVuetify(InstalledPluginsTab, {
      props: {
        state: {
          tm: (key: string) => key,
          router: { push: vi.fn() },
          activeTab: ref('installed'),
          updatingAll: ref(false),
          pluginSearch: ref(''),
          filteredPlugins: ref([{ name: 'plugin-alpha', activated: true }]),
          failedPluginItems: ref([]),
          reloadFailedPlugin: vi.fn(),
          uninstallExtension: vi.fn(),
          requestUninstallFailedPlugin: vi.fn(),
          updateExtension: vi.fn(),
          showUpdateAllConfirm: vi.fn(),
          pluginOn: vi.fn(),
          pluginOff: vi.fn(),
          openExtensionConfig: vi.fn(),
          showPluginInfo: vi.fn(),
          reloadPlugin: vi.fn(),
          viewReadme: vi.fn(),
          viewChangelog: vi.fn(),
          openInstallDialog: vi.fn(),
        },
      },
    });

    await flushPromises();

    expect(wrapper.find('.extension-card-stub').exists()).toBe(true);
    expectNoExtensionWarnings(warnSpy.mock.calls);
  });

  it('renders MarketPluginsTab without deprecated dense or v-tab-item warnings', async () => {
    const warnSpy = vi.spyOn(console, 'warn').mockImplementation(() => {});

    const wrapper = mountWithVuetify(MarketPluginsTab, {
      props: {
        state: {
          tm: (key: string) => key,
          router: { push: vi.fn() },
          activeTab: ref('market'),
          pluginMarketData: ref([{ name: 'market-alpha', pinned: false }]),
          loading_: ref(false),
          currentPage: ref(1),
          customSources: ref([]),
          selectedSource: ref(null),
          showPluginFullName: ref(false),
          marketSearch: ref(''),
          refreshingMarket: ref(false),
          sortBy: ref('default'),
          sortOrder: ref('desc'),
          marketCategoryFilter: ref('all'),
          marketCategoryItems: ref([]),
          randomPlugins: ref([]),
          refreshRandomPlugins: vi.fn(),
          totalPages: ref(1),
          paginatedPlugins: ref([{ name: 'market-alpha', pinned: false }]),
          openInstallDialog: vi.fn(),
          handleInstallPlugin: vi.fn(),
          openSourceManagerDialog: vi.fn(),
          refreshPluginMarket: vi.fn(),
        },
      },
    });

    await flushPromises();

    expect(wrapper.find('.market-plugin-card-stub').exists()).toBe(true);
    expect(wrapper.find('.plugin-sort-control-stub').exists()).toBe(true);
    expectNoExtensionWarnings(warnSpy.mock.calls);
  });

  it('renders ReadmeDialog inside a bounded scroll container for long markdown', async () => {
    const warnSpy = vi.spyOn(console, 'warn').mockImplementation(() => {});
    const errorSpy = vi.spyOn(console, 'error').mockImplementation(() => {});

    mountWithVuetify(ReadmeDialog, {
      props: {
        show: true,
        pluginName: 'plugin-alpha',
        repoUrl: 'https://github.com/example/plugin-alpha',
      },
    });

    await flushPromises();
    await flushPromises();

    expect(document.body.querySelector('.readme-dialog-card')).not.toBeNull();
    expect(document.body.querySelector('.readme-dialog__body')).not.toBeNull();
    expect(document.body.querySelector('.markdown-body')).not.toBeNull();
    expectNoExtensionWarnings(warnSpy.mock.calls);
    expectNoExtensionWarnings(errorSpy.mock.calls);
  });
});
