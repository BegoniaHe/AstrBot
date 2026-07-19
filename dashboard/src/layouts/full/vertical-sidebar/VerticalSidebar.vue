<script setup>
import {
  ref,
  shallowRef,
  computed,
  onMounted,
  onUnmounted,
  watch,
  defineAsyncComponent,
} from 'vue';
import { useTheme } from 'vuetify';
import { useCustomizerStore } from '../../../stores/customizer';
import { useI18n } from '@/i18n/composables';
import sidebarItems from './sidebarItem';
import NavItem from './NavItem.vue';
import { applySidebarCustomization } from '@/utils/sidebarCustomization';

const { t, locale } = useI18n();
const ChangelogDialog = defineAsyncComponent(
  () => import('@/components/shared/ChangelogDialog.vue'),
);

const customizer = useCustomizerStore();
const theme = useTheme();

function buildSidebarMenu() {
  return applySidebarCustomization(sidebarItems);
}

function collectGroupValues(items, values = new Set()) {
  items.forEach((item) => {
    if (item?.children && item.title) {
      values.add(item.title);
      collectGroupValues(item.children, values);
    }
  });
  return values;
}

function sanitizeOpenedItems(items, menuItems) {
  if (!Array.isArray(items)) {
    return [];
  }

  const groupValues = collectGroupValues(menuItems);
  return items.filter(
    (item) => typeof item === 'string' && groupValues.has(item),
  );
}

function getInitialOpenedItems(menuItems) {
  try {
    const stored = JSON.parse(
      localStorage.getItem('sidebar_openedItems') || '[]',
    );
    return sanitizeOpenedItems(stored, menuItems);
  } catch {
    return [];
  }
}

const sidebarMenu = shallowRef(buildSidebarMenu());

// 侧边栏分组展开状态持久化
const openedItems = ref(getInitialOpenedItems(sidebarMenu.value));
watch(
  openedItems,
  (val) => {
    localStorage.setItem(
      'sidebar_openedItems',
      JSON.stringify(sanitizeOpenedItems(val, sidebarMenu.value)),
    );
  },
  { deep: true },
);

function refreshSidebarMenu() {
  sidebarMenu.value = buildSidebarMenu();
  openedItems.value = sanitizeOpenedItems(openedItems.value, sidebarMenu.value);
}

// Apply customization on mount and listen for storage changes
const handleStorageChange = (e) => {
  if (e.key === 'astrbot_sidebar_customization') {
    refreshSidebarMenu();
  }
};

const handleCustomEvent = () => {
  refreshSidebarMenu();
};

onMounted(() => {
  window.addEventListener('storage', handleStorageChange);
  window.addEventListener('sidebar-customization-changed', handleCustomEvent);
});

onUnmounted(() => {
  window.removeEventListener('storage', handleStorageChange);
  window.removeEventListener(
    'sidebar-customization-changed',
    handleCustomEvent,
  );
});

const showIframe = ref(false);
const starCount = ref(null);
const STAR_COUNT_CACHE_KEY = 'astrbot_github_star_count_cache';
const STAR_COUNT_CACHE_TTL_MS = 30 * 60 * 1000;

// 更新日志对话框
const changelogDialog = ref(false);

const sidebarWidth = ref(235);
const minSidebarWidth = 200;
const maxSidebarWidth = 300;
const isResizing = ref(false);

const isDark = computed(() => customizer.uiTheme === 'PurpleThemeDark');
const themeColors = computed(() => theme.current.value.colors);
const iframeBackground = computed(() =>
  isDark.value ? themeColors.value.surface || 'white' : 'white',
);
const dragHeaderBackground = computed(() =>
  isDark.value
    ? themeColors.value.mcpCardBg || themeColors.value.surface || 'white'
    : '#f0f0f0',
);
const frameBorder = computed(
  () =>
    `1px solid ${isDark.value ? themeColors.value.borderLight || '#ccc' : '#ccc'}`,
);

const isMobile = window.innerWidth < 768;
const isRailSidebar = computed(() => !isMobile && customizer.mini_sidebar);
if (isMobile) {
  customizer.Sidebar_drawer = false;
} else {
  customizer.Sidebar_drawer = true;
}

const dragPos = ref({ left: '', top: '' });

const iframeStyle = computed(() => {
  const base = isMobile
    ? {
        position: 'fixed',
        top: '10%',
        left: '0%',
        width: '100%',
        height: '80%',
        zIndex: '1002',
      }
    : {
        position: 'fixed',
        bottom: '16px',
        right: '16px',
        width: '490px',
        height: '640px',
        zIndex: '10000000',
      };
  const pos = dragPos.value.left
    ? {
        left: dragPos.value.left,
        top: dragPos.value.top,
        bottom: 'auto',
        right: 'auto',
      }
    : {};
  return {
    ...base,
    ...pos,
    minWidth: '300px',
    minHeight: '200px',
    background: iframeBackground.value,
    resize: 'both',
    overflow: 'auto',
    borderRadius: '12px',
    boxShadow: isDark.value
      ? '0px 4px 16px rgba(0, 0, 0, 0.5)'
      : '0px 4px 12px rgba(0, 0, 0, 0.1)',
  };
});

const iframeInnerStyle = computed(() => ({
  width: '100%',
  height: 'calc(100% - 66px)',
  border: 'none',
  borderBottomLeftRadius: '12px',
  borderBottomRightRadius: '12px',
  filter: isDark.value ? 'invert(0.88) hue-rotate(180deg)' : 'none',
}));

const dragHeaderStyle = computed(() => ({
  width: '100%',
  padding: '8px',
  background: dragHeaderBackground.value,
  borderBottom: frameBorder.value,
  borderTopLeftRadius: '8px',
  borderTopRightRadius: '8px',
  display: 'flex',
  justifyContent: 'space-between',
  alignItems: 'center',
  cursor: 'move',
}));

function toggleIframe() {
  showIframe.value = !showIframe.value;
}

function openIframeLink(url) {
  if (typeof window !== 'undefined') {
    let url_ = url || 'https://docs.astrbot.app';
    window.open(url_, '_blank');
  }
}

function openFaqLink() {
  const faqUrl =
    locale.value === 'en-US'
      ? 'https://docs.astrbot.app/en/faq.html'
      : 'https://docs.astrbot.app/faq.html';
  openIframeLink(faqUrl);
}

let offsetX = 0;
let offsetY = 0;
let isDragging = false;

function clamp(value, min, max) {
  return Math.min(Math.max(value, min), max);
}

function startDrag(clientX, clientY) {
  isDragging = true;
  const dm = document.getElementById('draggable-iframe');
  const rect = dm.getBoundingClientRect();
  offsetX = clientX - rect.left;
  offsetY = clientY - rect.top;
  document.body.style.userSelect = 'none';
  document.addEventListener('mousemove', onMouseMove);
  document.addEventListener('mouseup', onMouseUp);
  document.addEventListener('touchmove', onTouchMove, { passive: false });
  document.addEventListener('touchend', onTouchEnd);
}

function onMouseDown(event) {
  startDrag(event.clientX, event.clientY);
}

function onMouseMove(event) {
  if (isDragging) {
    moveAt(event.clientX, event.clientY);
  }
}

function onMouseUp() {
  endDrag();
}

function onTouchStart(event) {
  if (event.touches.length === 1) {
    const touch = event.touches[0];
    startDrag(touch.clientX, touch.clientY);
  }
}

function onTouchMove(event) {
  if (isDragging && event.touches.length === 1) {
    event.preventDefault();
    const touch = event.touches[0];
    moveAt(touch.clientX, touch.clientY);
  }
}

function onTouchEnd() {
  endDrag();
}

function moveAt(clientX, clientY) {
  const dm = document.getElementById('draggable-iframe');
  const newLeft = clamp(
    clientX - offsetX,
    0,
    window.innerWidth - dm.offsetWidth,
  );
  const newTop = clamp(
    clientY - offsetY,
    0,
    window.innerHeight - dm.offsetHeight,
  );
  // Sync dragged position to reactive variable
  dragPos.value = { left: `${newLeft}px`, top: `${newTop}px` };
}

function endDrag() {
  isDragging = false;
  document.body.style.userSelect = '';
  document.removeEventListener('mousemove', onMouseMove);
  document.removeEventListener('mouseup', onMouseUp);
  document.removeEventListener('touchmove', onTouchMove);
  document.removeEventListener('touchend', onTouchEnd);
}

function startSidebarResize(event) {
  isResizing.value = true;
  document.body.style.userSelect = 'none';
  document.body.style.cursor = 'ew-resize';

  // 拖拽时禁用 iframe 的 pointer-events，防止 iframe 截获 mousemove 事件导致拖拽卡住
  const iframes = document.querySelectorAll('.plugin-page-frame');
  iframes.forEach((el) => {
    el.style.pointerEvents = 'none';
  });

  const startX = event.clientX;
  const startWidth = sidebarWidth.value;

  function onMouseMoveResize(event) {
    if (!isResizing.value) return;

    const deltaX = event.clientX - startX;
    const newWidth = Math.max(
      minSidebarWidth,
      Math.min(maxSidebarWidth, startWidth + deltaX),
    );
    sidebarWidth.value = newWidth;
  }

  function onMouseUpResize() {
    isResizing.value = false;
    document.body.style.userSelect = '';
    document.body.style.cursor = '';
    iframes.forEach((el) => {
      el.style.pointerEvents = '';
    });
    document.removeEventListener('mousemove', onMouseMoveResize);
    document.removeEventListener('mouseup', onMouseUpResize);
  }

  document.addEventListener('mousemove', onMouseMoveResize);
  document.addEventListener('mouseup', onMouseUpResize);
}

function formatNumber(num) {
  return num.toString().replace(/\B(?=(\d{3})+(?!\d))/g, ',');
}

function readCachedStarCount() {
  try {
    const raw = localStorage.getItem(STAR_COUNT_CACHE_KEY);
    if (!raw) {
      return null;
    }
    const parsed = JSON.parse(raw);
    const cachedAt = Number(parsed?.cachedAt);
    const value = Number(parsed?.value);
    if (
      !Number.isFinite(cachedAt) ||
      !Number.isFinite(value) ||
      Date.now() - cachedAt > STAR_COUNT_CACHE_TTL_MS
    ) {
      return null;
    }
    return value;
  } catch {
    return null;
  }
}

function writeCachedStarCount(value) {
  try {
    localStorage.setItem(
      STAR_COUNT_CACHE_KEY,
      JSON.stringify({
        cachedAt: Date.now(),
        value,
      }),
    );
  } catch {
    // Ignore storage failures and keep the UI non-blocking.
  }
}

async function fetchStarCount() {
  const cachedValue = readCachedStarCount();
  if (cachedValue !== null) {
    starCount.value = cachedValue;
  }

  try {
    const response = await fetch(
      'https://api.github.com/repos/Xero-Team/AstrBot',
      {
        headers: {
          Accept: 'application/vnd.github+json',
        },
      },
    );
    if (!response.ok) {
      return;
    }
    const data = await response.json();
    const nextStarCount = Number(data?.stargazers_count);
    if (Number.isFinite(nextStarCount) && nextStarCount > 0) {
      starCount.value = nextStarCount;
      writeCachedStarCount(nextStarCount);
    }
  } catch {
    // Ignore transient network failures. The GitHub button remains usable
    // without the optional star count badge.
  }
}

void fetchStarCount();

// 打开更新日志对话框
function openChangelogDialog() {
  changelogDialog.value = true;
}
</script>

<template>
  <v-navigation-drawer
    v-model="customizer.Sidebar_drawer"
    left
    elevation="0"
    rail-width="80"
    app
    class="leftSidebar"
    :width="sidebarWidth"
    :rail="isRailSidebar"
  >
    <div class="sidebar-container">
      <v-list
        v-model:opened="openedItems"
        :class="[
          'pa-4',
          'listitem',
          'flex-grow-1',
          { 'hidden-scrollbar': isRailSidebar },
        ]"
        :open-strategy="'multiple'"
      >
        <template
          v-for="(item, i) in sidebarMenu"
          :key="item.title || item.to || `sidebar-item-${i}`"
        >
          <NavItem :item="item" class="leftPadding" :rail="isRailSidebar" />
        </template>
      </v-list>
      <div v-if="!isRailSidebar" class="sidebar-footer">
        <v-btn
          class="sidebar-footer-btn"
          size="small"
          variant="tonal"
          color="primary"
          to="/settings"
          prepend-icon="mdi-cog"
        >
          {{ t('core.navigation.settings') }}
        </v-btn>
        <v-btn
          class="sidebar-footer-btn"
          size="small"
          variant="text"
          prepend-icon="mdi-note-text-outline"
          @click="openChangelogDialog"
        >
          {{ t('core.navigation.changelog') }}
        </v-btn>
        <v-btn
          class="sidebar-footer-btn"
          size="small"
          variant="text"
          prepend-icon="mdi-book-open-variant"
          @click="toggleIframe"
        >
          {{ t('core.navigation.documentation') }}
        </v-btn>
        <v-btn
          class="sidebar-footer-btn"
          size="small"
          variant="text"
          prepend-icon="mdi-frequently-asked-questions"
          @click="openFaqLink"
        >
          {{ t('core.navigation.faq') }}
        </v-btn>
        <v-btn
          class="sidebar-footer-btn"
          size="small"
          variant="text"
          prepend-icon="mdi-github"
          @click="openIframeLink('https://github.com/Xero-Team/AstrBot')"
        >
          {{ t('core.navigation.github') }}
          <v-chip
            v-if="starCount"
            size="x-small"
            variant="outlined"
            class="ml-2"
            style="font-weight: normal"
            >{{ formatNumber(starCount) }}</v-chip
          >
        </v-btn>
      </div>
      <div v-else class="sidebar-footer sidebar-footer-rail">
        <v-tooltip
          location="right"
          :text="t('core.navigation.settings')"
          open-delay="180"
        >
          <template #activator="{ props }">
            <v-btn
              v-bind="props"
              class="sidebar-footer-icon-btn"
              variant="text"
              to="/settings"
              :aria-label="t('core.navigation.settings')"
            >
              <v-icon icon="mdi-cog" />
            </v-btn>
          </template>
        </v-tooltip>
        <v-tooltip
          location="right"
          :text="t('core.navigation.changelog')"
          open-delay="180"
        >
          <template #activator="{ props }">
            <v-btn
              v-bind="props"
              class="sidebar-footer-icon-btn"
              variant="text"
              :aria-label="t('core.navigation.changelog')"
              @click="openChangelogDialog"
            >
              <v-icon icon="mdi-note-text-outline" />
            </v-btn>
          </template>
        </v-tooltip>
        <v-tooltip
          location="right"
          :text="t('core.navigation.documentation')"
          open-delay="180"
        >
          <template #activator="{ props }">
            <v-btn
              v-bind="props"
              class="sidebar-footer-icon-btn"
              variant="text"
              :aria-label="t('core.navigation.documentation')"
              @click="toggleIframe"
            >
              <v-icon icon="mdi-book-open-variant" />
            </v-btn>
          </template>
        </v-tooltip>
        <v-tooltip
          location="right"
          :text="t('core.navigation.faq')"
          open-delay="180"
        >
          <template #activator="{ props }">
            <v-btn
              v-bind="props"
              class="sidebar-footer-icon-btn"
              variant="text"
              :aria-label="t('core.navigation.faq')"
              @click="openFaqLink"
            >
              <v-icon icon="mdi-frequently-asked-questions" />
            </v-btn>
          </template>
        </v-tooltip>
        <v-tooltip location="right" text="GitHub" open-delay="180">
          <template #activator="{ props }">
            <v-btn
              v-bind="props"
              class="sidebar-footer-icon-btn"
              variant="text"
              aria-label="GitHub"
              @click="openIframeLink('https://github.com/Xero-Team/AstrBot')"
            >
              <v-icon icon="mdi-github" />
            </v-btn>
          </template>
        </v-tooltip>
      </div>
    </div>

    <div
      v-if="!isRailSidebar && !isMobile && customizer.Sidebar_drawer"
      class="sidebar-resize-handle"
      :class="{ resizing: isResizing }"
      @mousedown="startSidebarResize"
    ></div>
  </v-navigation-drawer>

  <div v-if="showIframe" id="draggable-iframe" :style="iframeStyle">
    <div
      :style="dragHeaderStyle"
      @mousedown="onMouseDown"
      @touchstart="onTouchStart"
    >
      <div style="display: flex; align-items: center">
        <v-icon icon="mdi-cursor-move" />
        <span style="margin-left: 8px">{{ t('core.navigation.drag') }}</span>
      </div>
      <div style="display: flex; gap: 8px">
        <v-btn
          icon
          :style="{ borderRadius: '8px', border: frameBorder }"
          @click.stop="openIframeLink('https://docs.astrbot.app')"
          @mousedown.stop
        >
          <v-icon icon="mdi-open-in-new" />
        </v-btn>
        <v-btn
          icon
          :style="{ borderRadius: '8px', border: frameBorder }"
          @click.stop="toggleIframe"
          @mousedown.stop
        >
          <v-icon icon="mdi-close" />
        </v-btn>
      </div>
    </div>
    <iframe src="https://docs.astrbot.app" :style="iframeInnerStyle"></iframe>
  </div>

  <!-- 更新日志对话框 -->
  <ChangelogDialog v-model="changelogDialog" />
</template>

<style scoped>
.sidebar-resize-handle {
  position: absolute;
  top: 0;
  right: 0;
  width: 4px;
  height: 100%;
  background: transparent;
  cursor: ew-resize;
  user-select: none;
  z-index: 1000;
  transition: background-color 0.2s ease;
}

.sidebar-resize-handle:hover,
.sidebar-resize-handle.resizing {
  background: rgba(var(--v-theme-primary), 0.3);
}

.sidebar-resize-handle::before {
  content: '';
  position: absolute;
  top: 50%;
  left: 50%;
  transform: translate(-50%, -50%);
  width: 2px;
  height: 30px;
  background: rgba(var(--v-theme-on-surface), 0.3);
  border-radius: 1px;
  opacity: 0;
  transition: opacity 0.2s ease;
}

.sidebar-resize-handle:hover::before,
.sidebar-resize-handle.resizing::before {
  opacity: 1;
}

/* 确保侧边栏容器支持相对定位 */
.leftSidebar .v-navigation-drawer__content {
  position: relative;
}
</style>
