import { describe, expect, it, vi } from 'vitest';

import { waitForRouterReadyInBackground } from '../src/utils/routerReadiness';

describe('router readiness', () => {
  it('returns immediately and logs failures', async () => {
    const error = new Error('router blocked');
    const logger = { warn: vi.fn() };
    const readyPromise = Promise.reject(error);
    const router = { isReady: () => readyPromise };

    expect(waitForRouterReadyInBackground(router, logger)).toBeUndefined();

    await Promise.resolve();

    expect(logger.warn).toHaveBeenCalledWith(
      'Router did not become ready after fallback mount:',
      error,
    );
  });
});
