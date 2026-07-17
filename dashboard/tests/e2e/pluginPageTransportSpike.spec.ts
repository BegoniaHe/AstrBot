import { expect, test } from '@playwright/test';

test('plugin page transport spike', async ({ page }) => {
  const consoleErrors: string[] = [];
  page.on('console', (message) => {
    if (message.type() === 'error') {
      consoleErrors.push(message.text());
    }
  });

  await page.goto('https://127.0.0.1:6190/spike');
  await expect(page.getByTestId('spike-status')).toHaveText('complete');

  const messages = await page.evaluate(
    () => (window as Window & { spikeMessages?: string[] }).spikeMessages ?? [],
  );
  expect(messages).toEqual(
    expect.arrayContaining([
      'sdk-loaded',
      'module-loaded',
      'static-import-loaded',
      'dynamic-import-loaded',
      'css-loaded',
      'image-loaded',
      'font-loaded',
    ]),
  );

  const resultResponse = await page.request.get(
    'https://127.0.0.1:6190/spike/results',
  );
  expect(resultResponse.ok()).toBeTruthy();
  const results = (await resultResponse.json()) as {
    requests: Array<{
      path: string;
      origin: string | null;
      hasSessionCookie: boolean;
    }>;
  };
  const bundleAssets = results.requests.filter((request) =>
    request.path.includes('/bundles/spike-bundle/'),
  );
  expect(bundleAssets.length).toBeGreaterThanOrEqual(6);
  for (const request of bundleAssets) {
    expect(request.hasSessionCookie).toBe(false);
    expect([null, 'null', 'https://127.0.0.1:6190']).toContain(request.origin);
  }

  expect(
    consoleErrors.filter((message) => !message.includes('navigate-to')),
  ).toEqual([]);
});
