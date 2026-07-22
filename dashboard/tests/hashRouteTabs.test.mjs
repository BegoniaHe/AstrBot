import { describe, expect, it, vi } from 'vitest';

import { EXTENSION_ROUTE_NAME } from '../src/router/routeConstants';
import {
  createTabRouteLocation,
  getValidHashTab,
  replaceTabRoute,
} from '../src/utils/hashRouteTabs';

describe('hash route tabs', () => {
  const validTabs = ['installed', 'market', 'mcp'];

  it('returns the tab name for a valid route hash', () => {
    expect(getValidHashTab('#market', validTabs)).toBe('market');
  });

  it('rejects empty and unknown hashes', () => {
    expect(getValidHashTab('', validTabs)).toBeNull();
    expect(getValidHashTab('#unknown', validTabs)).toBeNull();
  });

  it('uses the last hash segment when multiple hashes are present', () => {
    expect(getValidHashTab('#/extension#foo#installed', validTabs)).toBe(
      'installed',
    );
  });

  it('preserves the current path and query', () => {
    const query = { open_config: 'sample-plugin', page: '2' };
    const location = createTabRouteLocation(
      {
        path: '/extension',
        query,
      },
      'market',
    );

    expect(location).toEqual({
      path: '/extension',
      query: { open_config: 'sample-plugin', page: '2' },
      hash: '#market',
    });
    expect(location.query).not.toBe(query);
  });

  it('falls back to the extension route name', () => {
    expect(createTabRouteLocation({}, 'installed')).toEqual({
      name: EXTENSION_ROUTE_NAME,
      query: {},
      hash: '#installed',
    });
  });

  it('prefers the route name and preserves params', () => {
    const params = { pluginId: 'demo-plugin' };
    const location = createTabRouteLocation(
      {
        name: 'ExtensionDetails',
        path: '/extension/demo-plugin',
        params,
        query: { tab: 'details' },
      },
      'market',
    );

    expect(location).toEqual({
      name: 'ExtensionDetails',
      params: { pluginId: 'demo-plugin' },
      query: { tab: 'details' },
      hash: '#market',
    });
    expect(location.params).not.toBe(params);
  });

  it('omits params for path-based routes', () => {
    const location = createTabRouteLocation(
      {
        path: '/extension/demo-plugin',
        params: { pluginId: 'demo-plugin' },
      },
      'installed',
    );

    expect(location).toEqual({
      path: '/extension/demo-plugin',
      query: {},
      hash: '#installed',
    });
    expect(location.params).toBeUndefined();
  });

  it('catches rejected router updates', async () => {
    const error = new Error('blocked');
    const logger = { warn: vi.fn() };
    const router = { replace: vi.fn().mockRejectedValue(error) };

    await expect(
      replaceTabRoute(
        router,
        { name: EXTENSION_ROUTE_NAME, query: { page: '1' } },
        'installed',
        logger,
      ),
    ).resolves.toBe(false);
    expect(logger.warn).toHaveBeenCalledWith(
      'Failed to update extension tab route:',
      error,
    );
  });
});
