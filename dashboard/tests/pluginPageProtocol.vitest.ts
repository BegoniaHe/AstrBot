import { afterEach, describe, expect, it, vi } from 'vitest';
import { readFileSync } from 'node:fs';
import { resolve } from 'node:path';
import { JSDOM } from 'jsdom';

import {
  PLUGIN_PAGE_MAX_PENDING,
  PluginPageHostChannel,
  PluginPageProtocolError,
  createPluginPageConnectMessage,
  parsePluginPageReadyMessage,
  parsePluginPageToHostMessage,
  validatePluginPageContext,
} from '@/views/extension/pluginPageProtocol';

class FakeMessagePort {
  readonly sent: Array<{ message: unknown; transfer?: Transferable[] }> = [];
  private listener: ((event: MessageEvent<unknown>) => void) | null = null;
  closed = false;

  addEventListener(_type: 'message', listener: EventListener) {
    this.listener = listener as (event: MessageEvent<unknown>) => void;
  }

  removeEventListener() {
    this.listener = null;
  }

  start() {}

  close() {
    this.closed = true;
  }

  postMessage(message: unknown, transfer?: Transferable[]) {
    this.sent.push({ message, transfer });
  }

  dispatch(message: unknown) {
    this.listener?.(new MessageEvent('message', { data: message }));
  }
}

class SdkMessagePort extends FakeMessagePort {
  onmessage: ((event: MessageEvent<unknown>) => void) | null = null;
}

const instanceId = 'instance-1';
const generation = 'generation-1';
const requestId = '1d42f034-2fa1-4e49-9df3-5e15d1bf5d45';

function common() {
  return {
    protocol_version: 1 as const,
    instance_id: instanceId,
    plugin_generation: generation,
  };
}

function jsonRequest(id = requestId) {
  return {
    ...common(),
    kind: 'request',
    request_id: id,
    action_id: 'config.read',
    action_kind: 'json',
    payload: {},
  };
}

afterEach(() => {
  vi.useRealTimers();
});

describe('Plugin Page protocol v1', () => {
  it('accepts only the exact ready and connect handshake schema', () => {
    const ready = {
      protocol: 'astrbot.dashboard-extension',
      version: 1,
      kind: 'ready',
      instance_id: instanceId,
      nonce: 'nonce-1',
    };
    expect(parsePluginPageReadyMessage(ready, instanceId, 'nonce-1')).toEqual(
      ready,
    );
    expect(
      parsePluginPageReadyMessage(
        { ...ready, unexpected: true },
        instanceId,
        'nonce-1',
      ),
    ).toBeNull();
    expect(
      parsePluginPageReadyMessage(ready, instanceId, 'wrong-nonce'),
    ).toBeNull();
    expect(createPluginPageConnectMessage(instanceId, 'nonce-1')).toEqual({
      protocol: 'astrbot.dashboard-extension',
      version: 1,
      kind: 'connect',
      instance_id: instanceId,
      nonce: 'nonce-1',
    });
  });

  it('strictly validates context and every Page-to-Host union member', () => {
    const context = {
      protocol_version: 1 as const,
      extension_id: 'io.github.example.palette',
      plugin_name: 'astrbot_plugin_palette',
      page_id: 'settings',
      instance_id: instanceId,
      plugin_generation: generation,
      expires_at: '2026-07-17T12:00:00Z',
      locale: 'en-US',
      theme: {
        mode: 'dark' as const,
        is_dark: true,
        primary: '#6750a4',
        secondary: '#625b71',
      },
      capabilities: {
        actions: ['config.read'],
        upload: false,
        file: false,
      },
    };
    expect(validatePluginPageContext(context, instanceId, generation)).toBe(
      true,
    );
    expect(
      validatePluginPageContext(
        { ...context, unexpected: true },
        instanceId,
        generation,
      ),
    ).toBe(false);

    expect(
      parsePluginPageToHostMessage(jsonRequest(), instanceId, generation),
    ).toMatchObject({ kind: 'request', action_kind: 'json' });
    expect(() =>
      parsePluginPageToHostMessage(
        { ...jsonRequest(), unexpected: true },
        instanceId,
        generation,
      ),
    ).toThrow(PluginPageProtocolError);
    expect(() =>
      parsePluginPageToHostMessage(
        { ...jsonRequest(), action_kind: 'proxy', url: 'https://example.com' },
        instanceId,
        generation,
      ),
    ).toThrow(PluginPageProtocolError);
    expect(() =>
      parsePluginPageToHostMessage(
        { ...jsonRequest(), payload: 'x'.repeat(256 * 1024) },
        instanceId,
        generation,
      ),
    ).toThrow(PluginPageProtocolError);
  });

  it('handles a request once and ignores a late terminal result after cancel', async () => {
    vi.useFakeTimers();
    const port = new FakeMessagePort();
    let resolveRequest: ((value: { data: unknown }) => void) | undefined;
    const handler = vi.fn(
      () =>
        new Promise<{ data: unknown }>((resolve) => {
          resolveRequest = resolve;
        }),
    );
    const channel = new PluginPageHostChannel(
      port as unknown as MessagePort,
      instanceId,
      generation,
      handler,
      vi.fn(),
      vi.fn(),
    );

    port.dispatch(jsonRequest());
    expect(channel.pendingCount).toBe(1);
    port.dispatch({ ...common(), kind: 'cancel', request_id: requestId });
    expect(channel.pendingCount).toBe(0);
    expect(port.sent.at(-1)?.message).toMatchObject({
      kind: 'cancelled',
      request_id: requestId,
    });
    resolveRequest?.({ data: { late: true } });
    await Promise.resolve();
    expect(
      port.sent.filter(
        ({ message }) => (message as { kind?: string }).kind === 'response',
      ),
    ).toHaveLength(0);
    channel.dispose('host_navigation');
  });

  it('rejects duplicate IDs and requests beyond the fixed pending limit', () => {
    vi.useFakeTimers();
    const port = new FakeMessagePort();
    const protocolError = vi.fn();
    const channel = new PluginPageHostChannel(
      port as unknown as MessagePort,
      instanceId,
      generation,
      () => new Promise(() => undefined),
      vi.fn(),
      protocolError,
    );
    port.dispatch(jsonRequest());
    port.dispatch(jsonRequest());
    expect(protocolError).toHaveBeenCalledTimes(1);

    for (let index = 1; index < PLUGIN_PAGE_MAX_PENDING; index += 1) {
      const id = `00000000-0000-4000-8000-${String(index).padStart(12, '0')}`;
      port.dispatch(jsonRequest(id));
    }
    expect(channel.pendingCount).toBe(PLUGIN_PAGE_MAX_PENDING);
    port.dispatch(jsonRequest('ffffffff-ffff-4fff-8fff-ffffffffffff'));
    expect(protocolError).toHaveBeenCalledTimes(2);
    channel.dispose('protocol_error');
  });

  it('fails closed on malformed messages and aborts all work on dispose', () => {
    vi.useFakeTimers();
    const port = new FakeMessagePort();
    const protocolError = vi.fn();
    const onPageDispose = vi.fn();
    const channel = new PluginPageHostChannel(
      port as unknown as MessagePort,
      instanceId,
      generation,
      () => new Promise(() => undefined),
      onPageDispose,
      protocolError,
    );
    port.dispatch({ ...common(), kind: 'unknown' });
    expect(protocolError).toHaveBeenCalledOnce();

    port.dispatch({ ...common(), kind: 'dispose', reason: 'page_requested' });
    expect(onPageDispose).toHaveBeenCalledOnce();
    expect(port.sent.at(-1)?.message).toMatchObject({ kind: 'disposed' });
    channel.dispose('host_navigation', false);
    expect(port.closed).toBe(true);
  });

  it('cancels a Host request at the fixed timeout and ignores its late result', async () => {
    vi.useFakeTimers();
    const port = new FakeMessagePort();
    const channel = new PluginPageHostChannel(
      port as unknown as MessagePort,
      instanceId,
      generation,
      () => new Promise(() => undefined),
      vi.fn(),
      vi.fn(),
    );
    port.dispatch(jsonRequest());
    await vi.advanceTimersByTimeAsync(30_000);
    expect(channel.pendingCount).toBe(0);
    expect(port.sent.at(-1)?.message).toMatchObject({
      kind: 'cancelled',
      request_id: requestId,
    });
    channel.dispose('host_navigation', false);
  });

  it('keeps SDK internals private and revokes SDK-managed object URLs', async () => {
    const source = readFileSync(
      resolve(process.cwd(), '../astrbot/dashboard/plugin_page_sdk.js'),
      'utf8',
    );
    const dom = new JSDOM('<!doctype html><body></body>', {
      runScripts: 'outside-only',
      url: 'https://dashboard.test/page#instance=instance-1&channel=nonce-1',
    });
    const sdkWindow = dom.window;
    const parentPostMessage = vi.fn();
    Object.defineProperty(sdkWindow, 'postMessage', {
      configurable: true,
      value: parentPostMessage,
    });
    const createObjectURL = vi.fn(() => 'blob:plugin-preview');
    const revokeObjectURL = vi.fn();
    Object.defineProperties(sdkWindow.URL, {
      createObjectURL: { configurable: true, value: createObjectURL },
      revokeObjectURL: { configurable: true, value: revokeObjectURL },
    });

    sdkWindow.eval(source);
    expect(parentPostMessage).toHaveBeenCalledWith(
      expect.objectContaining({ kind: 'ready', nonce: 'nonce-1' }),
      '*',
    );
    const sdk = (
      sdkWindow as unknown as {
        AstrBotPluginPage: {
          ready(): Promise<unknown>;
          readFile(
            actionId: string,
            payload: unknown,
          ): Promise<{
            bytes: ArrayBuffer;
            disposition: 'inline';
          }>;
          createObjectURL(file: {
            bytes: ArrayBuffer;
            disposition: 'inline';
          }): string;
          dispose(): void;
        };
      }
    ).AstrBotPluginPage;
    expect(Object.isFrozen(sdk)).toBe(true);
    expect(Object.keys(sdk)).not.toEqual(
      expect.arrayContaining(['port', 'nonce', 'session']),
    );

    const port = new SdkMessagePort();
    sdkWindow.dispatchEvent(
      new sdkWindow.MessageEvent('message', {
        source: sdkWindow,
        ports: [port as unknown as MessagePort],
        data: {
          protocol: 'astrbot.dashboard-extension',
          version: 1,
          kind: 'connect',
          instance_id: instanceId,
          nonce: 'nonce-1',
        },
      }),
    );
    const context = {
      protocol_version: 1,
      extension_id: 'io.github.example.palette',
      plugin_name: 'astrbot_plugin_palette',
      page_id: 'settings',
      instance_id: instanceId,
      plugin_generation: generation,
      expires_at: '2099-07-17T12:00:00Z',
      locale: 'en-US',
      theme: {
        mode: 'light',
        is_dark: false,
        primary: '#fff',
        secondary: '#000',
      },
      capabilities: {
        actions: ['background.thumbnail'],
        upload: false,
        file: true,
      },
    };
    port.dispatch({
      ...common(),
      kind: 'context',
      context,
    });
    await expect(sdk.ready()).resolves.toEqual(context);

    const filePromise = sdk.readFile('background.thumbnail', {});
    const request = port.sent.at(-1)?.message as { request_id: string };
    const bytes = new sdkWindow.ArrayBuffer(4);
    port.dispatch({
      ...common(),
      kind: 'response',
      request_id: request.request_id,
      ok: true,
      data: {
        bytes,
        filename: 'palette.png',
        contentType: 'image/png',
        size: 4,
        disposition: 'inline',
      },
    });
    const file = await filePromise;
    expect(sdk.createObjectURL(file)).toBe('blob:plugin-preview');
    sdk.dispose();
    expect(revokeObjectURL).toHaveBeenCalledWith('blob:plugin-preview');
    expect(port.closed).toBe(true);
    dom.window.close();
  });
});
