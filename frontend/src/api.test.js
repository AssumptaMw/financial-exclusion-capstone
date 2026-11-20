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

it('accepts prediction with explanation', async () => {
  const mockResponse = {
    financial_exclusion_status: 1,
    label: 'Financially excluded',
    explanation: {
      success: true,
      margin: 0.5,
      contributors: [
        { variable: 'S1', shap_value: 0.4, direction: 'towards excluded' },
        { variable: 'ID_card', shap_value: 0.1, direction: 'towards included' },
      ],
    },
  };
  vi.stubGlobal('fetch', vi.fn().mockResolvedValue({
    ok: true,
    json: async () => mockResponse,
  }));
  const result = await predict({});
  expect(result).toEqual(mockResponse);
  expect(result.explanation).toBeDefined();
  expect(Array.isArray(result.explanation.contributors)).toBe(true);
});

it('handles missing explanation gracefully', async () => {
  const mockResponse = {
    financial_exclusion_status: 0,
    label: 'Financially included',
    explanation: {
      success: false,
      error: 'Explanation unavailable',
    },
  };
  vi.stubGlobal('fetch', vi.fn().mockResolvedValue({
    ok: true,
    json: async () => mockResponse,
  }));
  const result = await predict({});
  expect(result).toEqual(mockResponse);
  expect(result.explanation.success).toBe(false);
});

