export const PLUGIN_PAGE_PROTOCOL = 'astrbot.dashboard-extension' as const;
export const PLUGIN_PAGE_PROTOCOL_VERSION = 1 as const;
export const PLUGIN_PAGE_MAX_PENDING = 64;
export const PLUGIN_PAGE_MAX_JSON_BYTES = 256 * 1024;
export const PLUGIN_PAGE_REQUEST_TIMEOUT_MS = 30_000;

const encoder = new TextEncoder();
const actionIdPattern = /^[a-z][a-z0-9]*(?:[._-][a-z0-9]+)*$/;
const uuidPattern =
  /^[0-9a-f]{8}-[0-9a-f]{4}-[1-8][0-9a-f]{3}-[89ab][0-9a-f]{3}-[0-9a-f]{12}$/i;

export type PluginPageDisposeReason =
  | 'host_navigation'
  | 'plugin_changed'
  | 'logout'
  | 'expired'
  | 'protocol_error';

export interface PluginPageContext {
  protocol_version: 1;
  extension_id: string;
  plugin_name: string;
  page_id: string;
  instance_id: string;
  plugin_generation: string;
  expires_at: string;
  locale: string;
  theme: {
    mode: 'light' | 'dark';
    is_dark: boolean;
    primary: string;
    secondary: string;
  };
  capabilities: {
    actions: string[];
    upload: boolean;
    file: boolean;
  };
}

export interface PluginPageReadyMessage {
  protocol: typeof PLUGIN_PAGE_PROTOCOL;
  version: 1;
  kind: 'ready';
  instance_id: string;
  nonce: string;
}

export interface PluginPageConnectMessage {
  protocol: typeof PLUGIN_PAGE_PROTOCOL;
  version: 1;
  kind: 'connect';
  instance_id: string;
  nonce: string;
}

export interface PluginPagePublicError {
  code: string;
  message: string;
  request_id?: string;
  retryable: boolean;
}

interface PluginPageCommon {
  protocol_version: 1;
  instance_id: string;
  plugin_generation: string;
}

export type PluginPageRequest = PluginPageCommon &
  (
    | {
        kind: 'request';
        request_id: string;
        action_id: string;
        action_kind: 'json';
        payload: unknown;
      }
    | {
        kind: 'request';
        request_id: string;
        action_id: string;
        action_kind: 'upload';
        file: File;
        fields: unknown;
      }
    | {
        kind: 'request';
        request_id: string;
        action_id: string;
        action_kind: 'file';
        file_operation: 'read' | 'download';
        payload: unknown;
      }
  );

export type PluginPageToHostMessage =
  | PluginPageRequest
  | (PluginPageCommon & { kind: 'cancel'; request_id: string })
  | (PluginPageCommon & { kind: 'dispose'; reason: 'page_requested' })
  | (PluginPageCommon & { kind: 'disposed' });

export interface PluginPageRequestResult {
  data: unknown;
  transfer?: Transferable[];
}

export interface PluginPageRequestHandler {
  (
    request: PluginPageRequest,
    signal: AbortSignal,
  ): Promise<PluginPageRequestResult>;
}

export class PluginPageProtocolError extends Error {
  constructor(message = 'Plugin Page protocol error') {
    super(message);
    this.name = 'PluginPageProtocolError';
  }
}

function isRecord(value: unknown): value is Record<string, unknown> {
  return Boolean(value) && typeof value === 'object' && !Array.isArray(value);
}

function hasExactKeys(
  value: Record<string, unknown>,
  expectedKeys: readonly string[],
): boolean {
  const actual = Object.keys(value).sort();
  const expected = [...expectedKeys].sort();
  return (
    actual.length === expected.length &&
    actual.every((key, index) => key === expected[index])
  );
}

function jsonPartSize(value: unknown): number {
  try {
    const serialized = JSON.stringify(value, (_key, item) => {
      if (typeof File !== 'undefined' && item instanceof File) {
        return {
          name: item.name,
          size: item.size,
          type: item.type,
          lastModified: item.lastModified,
        };
      }
      if (item instanceof ArrayBuffer) {
        return { byteLength: item.byteLength };
      }
      return item;
    });
    return encoder.encode(serialized).length;
  } catch {
    return Number.POSITIVE_INFINITY;
  }
}

function requireString(value: unknown): value is string {
  return typeof value === 'string' && value.length > 0 && value.length <= 512;
}

export function parsePluginPageReadyMessage(
  value: unknown,
  expectedInstanceId: string,
  expectedNonce: string,
): PluginPageReadyMessage | null {
  if (
    !isRecord(value) ||
    !hasExactKeys(value, [
      'protocol',
      'version',
      'kind',
      'instance_id',
      'nonce',
    ]) ||
    value.protocol !== PLUGIN_PAGE_PROTOCOL ||
    value.version !== PLUGIN_PAGE_PROTOCOL_VERSION ||
    value.kind !== 'ready' ||
    value.instance_id !== expectedInstanceId ||
    value.nonce !== expectedNonce
  ) {
    return null;
  }
  return value as unknown as PluginPageReadyMessage;
}

export function createPluginPageConnectMessage(
  instanceId: string,
  nonce: string,
): PluginPageConnectMessage {
  return {
    protocol: PLUGIN_PAGE_PROTOCOL,
    version: PLUGIN_PAGE_PROTOCOL_VERSION,
    kind: 'connect',
    instance_id: instanceId,
    nonce,
  };
}

export function validatePluginPageContext(
  value: unknown,
  expectedInstanceId: string,
  expectedGeneration: string,
): value is PluginPageContext {
  if (
    !isRecord(value) ||
    !hasExactKeys(value, [
      'protocol_version',
      'extension_id',
      'plugin_name',
      'page_id',
      'instance_id',
      'plugin_generation',
      'expires_at',
      'locale',
      'theme',
      'capabilities',
    ]) ||
    value.protocol_version !== PLUGIN_PAGE_PROTOCOL_VERSION ||
    value.instance_id !== expectedInstanceId ||
    value.plugin_generation !== expectedGeneration ||
    !requireString(value.extension_id) ||
    !requireString(value.plugin_name) ||
    !requireString(value.page_id) ||
    !requireString(value.expires_at) ||
    !requireString(value.locale) ||
    !isRecord(value.theme) ||
    !hasExactKeys(value.theme, ['mode', 'is_dark', 'primary', 'secondary']) ||
    !['light', 'dark'].includes(String(value.theme.mode)) ||
    typeof value.theme.is_dark !== 'boolean' ||
    !requireString(value.theme.primary) ||
    !requireString(value.theme.secondary) ||
    !isRecord(value.capabilities) ||
    !hasExactKeys(value.capabilities, ['actions', 'upload', 'file']) ||
    !Array.isArray(value.capabilities.actions) ||
    !value.capabilities.actions.every(
      (item) => typeof item === 'string' && actionIdPattern.test(item),
    ) ||
    typeof value.capabilities.upload !== 'boolean' ||
    typeof value.capabilities.file !== 'boolean'
  ) {
    return false;
  }
  return true;
}

export function parsePluginPageToHostMessage(
  value: unknown,
  expectedInstanceId: string,
  expectedGeneration: string,
): PluginPageToHostMessage {
  if (
    !isRecord(value) ||
    value.protocol_version !== PLUGIN_PAGE_PROTOCOL_VERSION ||
    value.instance_id !== expectedInstanceId ||
    value.plugin_generation !== expectedGeneration ||
    jsonPartSize(value) > PLUGIN_PAGE_MAX_JSON_BYTES
  ) {
    throw new PluginPageProtocolError();
  }

  const common = [
    'protocol_version',
    'instance_id',
    'plugin_generation',
    'kind',
  ];
  if (value.kind === 'request') {
    if (
      !requireString(value.request_id) ||
      !uuidPattern.test(value.request_id) ||
      !requireString(value.action_id) ||
      !actionIdPattern.test(value.action_id)
    ) {
      throw new PluginPageProtocolError();
    }
    if (
      value.action_kind === 'json' &&
      hasExactKeys(value, [
        ...common,
        'request_id',
        'action_id',
        'action_kind',
        'payload',
      ])
    ) {
      return value as unknown as PluginPageRequest;
    }
    if (
      value.action_kind === 'upload' &&
      hasExactKeys(value, [
        ...common,
        'request_id',
        'action_id',
        'action_kind',
        'file',
        'fields',
      ]) &&
      typeof File !== 'undefined' &&
      value.file instanceof File
    ) {
      return value as unknown as PluginPageRequest;
    }
    if (
      value.action_kind === 'file' &&
      hasExactKeys(value, [
        ...common,
        'request_id',
        'action_id',
        'action_kind',
        'file_operation',
        'payload',
      ]) &&
      ['read', 'download'].includes(String(value.file_operation))
    ) {
      return value as unknown as PluginPageRequest;
    }
    throw new PluginPageProtocolError();
  }
  if (
    value.kind === 'cancel' &&
    hasExactKeys(value, [...common, 'request_id']) &&
    requireString(value.request_id) &&
    uuidPattern.test(value.request_id)
  ) {
    return value as unknown as PluginPageToHostMessage;
  }
  if (
    value.kind === 'dispose' &&
    value.reason === 'page_requested' &&
    hasExactKeys(value, [...common, 'reason'])
  ) {
    return value as unknown as PluginPageToHostMessage;
  }
  if (value.kind === 'disposed' && hasExactKeys(value, common)) {
    return value as unknown as PluginPageToHostMessage;
  }
  throw new PluginPageProtocolError();
}

function normalizePublicError(
  error: unknown,
  requestId: string,
): PluginPagePublicError {
  if (isRecord(error) && typeof error.code === 'string') {
    return {
      code: error.code.slice(0, 128),
      message:
        typeof error.message === 'string'
          ? error.message.slice(0, 512)
          : 'Plugin request failed',
      request_id: requestId,
      retryable: error.retryable === true,
    };
  }
  return {
    code: 'request_failed',
    message: 'Plugin request failed',
    request_id: requestId,
    retryable: false,
  };
}

export class PluginPageHostChannel {
  private readonly activeRequests = new Map<string, AbortController>();
  private readonly completedRequestIds = new Set<string>();
  private disposed = false;

  constructor(
    private readonly port: MessagePort,
    private readonly instanceId: string,
    private readonly generation: string,
    private readonly requestHandler: PluginPageRequestHandler,
    private readonly onPageDispose: () => void,
    private readonly onProtocolError: () => void,
  ) {
    this.port.addEventListener('message', this.handleMessage);
    this.port.start();
  }

  sendContext(context: PluginPageContext): void {
    if (
      this.disposed ||
      !validatePluginPageContext(context, this.instanceId, this.generation)
    ) {
      throw new PluginPageProtocolError();
    }
    this.port.postMessage({
      protocol_version: PLUGIN_PAGE_PROTOCOL_VERSION,
      instance_id: this.instanceId,
      plugin_generation: this.generation,
      kind: 'context',
      context,
    });
  }

  dispose(reason: PluginPageDisposeReason, notifyPage = true): void {
    if (this.disposed) return;
    this.disposed = true;
    for (const controller of this.activeRequests.values()) controller.abort();
    this.activeRequests.clear();
    if (notifyPage) {
      this.port.postMessage({
        protocol_version: PLUGIN_PAGE_PROTOCOL_VERSION,
        instance_id: this.instanceId,
        plugin_generation: this.generation,
        kind: 'dispose',
        reason,
      });
    }
    this.port.removeEventListener('message', this.handleMessage);
    this.port.close();
  }

  get pendingCount(): number {
    return this.activeRequests.size;
  }

  private readonly handleMessage = (event: MessageEvent<unknown>): void => {
    if (this.disposed) return;
    let message: PluginPageToHostMessage;
    try {
      message = parsePluginPageToHostMessage(
        event.data,
        this.instanceId,
        this.generation,
      );
    } catch {
      this.onProtocolError();
      return;
    }

    if (message.kind === 'dispose') {
      this.port.postMessage({
        protocol_version: PLUGIN_PAGE_PROTOCOL_VERSION,
        instance_id: this.instanceId,
        plugin_generation: this.generation,
        kind: 'disposed',
      });
      this.onPageDispose();
      return;
    }
    if (message.kind === 'disposed') {
      this.dispose('host_navigation', false);
      return;
    }
    if (message.kind === 'cancel') {
      this.activeRequests.get(message.request_id)?.abort();
      this.activeRequests.delete(message.request_id);
      this.rememberCompleted(message.request_id);
      this.sendCancelled(message.request_id);
      return;
    }

    const requestId = message.request_id;
    if (
      this.activeRequests.has(requestId) ||
      this.completedRequestIds.has(requestId) ||
      this.activeRequests.size >= PLUGIN_PAGE_MAX_PENDING
    ) {
      this.onProtocolError();
      return;
    }
    const controller = new AbortController();
    this.activeRequests.set(requestId, controller);
    const timeout = window.setTimeout(() => {
      if (!this.activeRequests.delete(requestId)) return;
      this.rememberCompleted(requestId);
      controller.abort();
      this.sendCancelled(requestId);
    }, PLUGIN_PAGE_REQUEST_TIMEOUT_MS);
    void this.requestHandler(message, controller.signal)
      .then((result) => {
        const response = {
          protocol_version: PLUGIN_PAGE_PROTOCOL_VERSION,
          instance_id: this.instanceId,
          plugin_generation: this.generation,
          kind: 'response' as const,
          request_id: requestId,
          ok: true as const,
          data: result.data,
        };
        if (jsonPartSize(response) > PLUGIN_PAGE_MAX_JSON_BYTES) {
          throw new PluginPageProtocolError('Plugin response is too large');
        }
        if (!this.finishRequest(requestId) || controller.signal.aborted) return;
        this.port.postMessage(response, result.transfer ?? []);
      })
      .catch((error: unknown) => {
        if (!this.finishRequest(requestId)) return;
        if (controller.signal.aborted) {
          this.sendCancelled(requestId);
          return;
        }
        this.port.postMessage({
          protocol_version: PLUGIN_PAGE_PROTOCOL_VERSION,
          instance_id: this.instanceId,
          plugin_generation: this.generation,
          kind: 'response',
          request_id: requestId,
          ok: false,
          error: normalizePublicError(error, requestId),
        });
      })
      .finally(() => {
        window.clearTimeout(timeout);
      });
  };

  private finishRequest(requestId: string): boolean {
    if (!this.activeRequests.delete(requestId)) return false;
    this.rememberCompleted(requestId);
    return !this.disposed;
  }

  private rememberCompleted(requestId: string): void {
    this.completedRequestIds.add(requestId);
    if (this.completedRequestIds.size > PLUGIN_PAGE_MAX_PENDING * 4) {
      const oldest = this.completedRequestIds.values().next().value;
      if (oldest) this.completedRequestIds.delete(oldest);
    }
  }

  private sendCancelled(requestId: string): void {
    if (this.disposed) return;
    this.port.postMessage({
      protocol_version: PLUGIN_PAGE_PROTOCOL_VERSION,
      instance_id: this.instanceId,
      plugin_generation: this.generation,
      kind: 'cancelled',
      request_id: requestId,
    });
  }
}
