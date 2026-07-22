import { flushPromises } from '@vue/test-utils';
import { beforeEach, describe, expect, it, vi } from 'vitest';
import AuthLogin from '@/views/authentication/authForms/AuthLogin.vue';
import { mountWithVuetify } from './utils/mountWithVuetify';

const state = vi.hoisted(() => ({
  login: vi.fn(),
  authStore: {
    returnUrl: null as string | null,
    login: vi.fn(),
  },
}));

vi.mock('@/stores/auth', () => ({
  useAuthStore: () => state.authStore,
}));

vi.mock('@/views/authentication/authForms/stages/AuthStageAccount.vue', () => ({
  default: {
    emits: ['submit', 'update:username', 'update:password'],
    template: `
      <div data-testid="account-stage">
        <button data-testid="set-account" @click="$emit('update:username', 'astrbot'); $emit('update:password', 'not-a-real-password')">set account</button>
        <button data-testid="submit-account" @click="$emit('submit')">submit account</button>
      </div>
    `,
  },
}));

vi.mock('@/views/authentication/authForms/stages/AuthStageTotp.vue', () => ({
  default: {
    template: '<div data-testid="totp-stage"></div>',
  },
}));

vi.mock(
  '@/views/authentication/authForms/stages/AuthStageRecovery.vue',
  () => ({
    default: {
      template: '<div data-testid="recovery-stage"></div>',
    },
  }),
);

describe('AuthLogin', () => {
  beforeEach(() => {
    vi.clearAllMocks();
    state.authStore.returnUrl = null;
    state.authStore.login = state.login;
  });

  it('moves to the TOTP stage only after the account credentials are accepted', async () => {
    state.login.mockResolvedValue('totp_required');
    const wrapper = mountWithVuetify(AuthLogin);

    await wrapper.get('[data-testid="set-account"]').trigger('click');
    await wrapper.get('[data-testid="submit-account"]').trigger('click');
    await flushPromises();

    expect(state.login).toHaveBeenCalledWith('astrbot', 'not-a-real-password');
    expect(wrapper.find('[data-testid="totp-stage"]').exists()).toBe(true);
  });

  it('keeps unexpected login errors generic instead of exposing credentials or internal URLs', async () => {
    state.login.mockRejectedValue(
      new Error(
        'provider api_key=super-secret Bearer top-secret at http://internal.example/private',
      ),
    );
    const wrapper = mountWithVuetify(AuthLogin);

    await wrapper.get('[data-testid="set-account"]').trigger('click');
    await wrapper.get('[data-testid="submit-account"]').trigger('click');
    await flushPromises();

    expect(wrapper.find('.error-container').text()).toContain('Login failed');
    expect(wrapper.text()).not.toContain('super-secret');
    expect(wrapper.text()).not.toContain('internal.example');
  });
});
