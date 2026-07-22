import { describe, expect, it } from 'vitest';

import {
  PINNED_EXTENSIONS_STORAGE_KEY,
  readPinnedExtensions,
  writePinnedExtensions,
} from '../src/views/extension/extensionPreferenceStorage';

describe('extension preference storage', () => {
  it('uses the pinned extension storage key', () => {
    expect(PINNED_EXTENSIONS_STORAGE_KEY).toBe('astrbot.pinnedExtensions');
  });

  it('parses stored pinned extension names', () => {
    const storage = {
      getItem(key) {
        return key === PINNED_EXTENSIONS_STORAGE_KEY
          ? JSON.stringify(['alpha', 'beta', 'alpha', '', 1])
          : null;
      },
    };

    expect(readPinnedExtensions(storage)).toEqual(['alpha', 'beta']);
  });

  it('returns an empty array when storage access fails', () => {
    const storage = {
      getItem() {
        throw new Error('SecurityError');
      },
    };

    expect(readPinnedExtensions(storage)).toEqual([]);
  });

  it('stores normalized pinned extension names', () => {
    const writes = [];
    const storage = {
      setItem(key, value) {
        writes.push([key, value]);
      },
    };

    writePinnedExtensions(['alpha', 'beta', 'alpha', '', null], storage);

    expect(writes).toEqual([
      [PINNED_EXTENSIONS_STORAGE_KEY, JSON.stringify(['alpha', 'beta'])],
    ]);
  });

  it('ignores unavailable storage', () => {
    expect(() => writePinnedExtensions(['alpha'], null)).not.toThrow();
    expect(() => writePinnedExtensions(['alpha'], {})).not.toThrow();
  });
});
