import { afterEach, expect, it, vi } from 'vitest';
import { predict } from './api.js';

afterEach(() => vi.unstubAllGlobals());

it.each([
  [422, 'could not validate'],
  [503, 'model is unavailable'],
  [500, 'could not complete'],
])('handles HTTP %i without exposing server details', async (status, message) => {
  vi.stubGlobal('fetch', vi.fn().mockResolvedValue({ ok: false, status }));
  await expect(predict({})).rejects.toThrow(message);
});

it('rejects inconsistent or malformed prediction responses', async () => {
  vi.stubGlobal('fetch', vi.fn().mockResolvedValue({
    ok: true, json: async () => ({ financial_exclusion_status: 0, label: 'Financially excluded' }),
  }));
  await expect(predict({})).rejects.toThrow('invalid response');
  vi.stubGlobal('fetch', vi.fn().mockResolvedValue({ ok: true, json: async () => { throw new Error('bad json'); } }));
  await expect(predict({})).rejects.toThrow('invalid response');
});
