import { describe, expect, it } from 'vitest';

import { isComposingEnter } from '../src/utils/imeInput';

describe('IME Enter handling', () => {
  it('detects Enter while an IME composition is active', () => {
    expect(isComposingEnter({ key: 'Enter', isComposing: true }, false)).toBe(
      true,
    );
    expect(isComposingEnter({ key: 'Enter', isComposing: false }, true)).toBe(
      true,
    );
  });

  it('does not treat normal Enter as IME composition', () => {
    expect(isComposingEnter({ key: 'Enter', isComposing: false }, false)).toBe(
      false,
    );
    expect(isComposingEnter({ key: 'a', isComposing: true }, true)).toBe(false);
  });

  it('detects Enter fired immediately after composition ended', () => {
    expect(
      isComposingEnter(
        { key: 'Enter', isComposing: false, timeStamp: 105 },
        false,
        100,
      ),
    ).toBe(true);
  });

  it('does not treat delayed Enter after composition ended as IME composition', () => {
    expect(
      isComposingEnter(
        { key: 'Enter', isComposing: false, timeStamp: 250 },
        false,
        100,
      ),
    ).toBe(false);
  });
});
