import { afterEach, describe, expect, it, vi } from 'vitest';
import { cleanup, render, screen, waitFor } from '@testing-library/react';
import userEvent from '@testing-library/user-event';
import App from './App.jsx';
import { fields, prepareRequest } from './fields.js';

afterEach(() => {
  cleanup();
  vi.unstubAllGlobals();
});

describe('prediction form', () => {
  it('requires all 17 fields and rejects ineligible ages', async () => {
    const user = userEvent.setup();
    const fetch = vi.fn();
    vi.stubGlobal('fetch', fetch);
    render(<App />);
    expect(fields).toHaveLength(17);
    expect(screen.getAllByRole('combobox')).toHaveLength(15);
    await user.click(screen.getByRole('button', { name: /generate prediction/i }));
    expect(screen.getByRole('alert')).toHaveTextContent('review the highlighted fields');
    expect(fetch).not.toHaveBeenCalled();
    const age = screen.getByRole('spinbutton', { name: /^age/i });
    await user.type(age, '98');
    await user.click(screen.getByRole('button', { name: /generate prediction/i }));
    expect(age).toHaveAttribute('aria-invalid', 'true');
    expect(fetch).not.toHaveBeenCalled();
  });

  it('sends exact API fields, preserves workbook labels and renders the result', async () => {
    const user = userEvent.setup();
    const fetch = vi.fn().mockResolvedValue({
      ok: true, json: async () => ({ financial_exclusion_status: 1, label: 'Financially excluded' }),
    });
    vi.stubGlobal('fetch', fetch);
    render(<App />);
    await user.type(screen.getByRole('spinbutton', { name: /^age/i }), '35');
    await user.type(screen.getByRole('spinbutton', { name: /^total income/i }), '10000');
    for (const select of screen.getAllByRole('combobox')) {
      await user.selectOptions(select, '__missing__');
    }
    await user.selectOptions(screen.getByRole('combobox', { name: /^highest education/i }), '"Secondary completed "');
    await user.selectOptions(screen.getByRole('combobox', { name: /^employed income/i }), '1');
    await user.selectOptions(screen.getByRole('combobox', { name: /^internet use frequency/i }), 'Daily/"Kila siku"');
    await user.selectOptions(screen.getByRole('combobox', { name: /^phone ownership/i }), 'I don\u00e2\u20ac\u2122t own or use a mobile phone/Sina wala situmii simu ya mkononi');
    await user.click(screen.getByRole('button', { name: /generate prediction/i }));

    expect(await screen.findByText('Financially Excluded')).toBeInTheDocument();
    expect(screen.getByRole('region', { name: 'Prediction result' })).toHaveFocus();
    const [url, options] = fetch.mock.calls[0];
    expect(url).toBe('/api/predict/with-explanation');
    expect(options.method).toBe('POST');
    const payload = JSON.parse(options.body);
    expect(Object.keys(payload)).toEqual(fields.map((field) => field.name));
    expect(payload).toMatchObject({
      A18: 35, A20: '"Secondary completed "', B3A__2: 1,
      B3Ii: 10000, S3: 'Daily/"Kila siku"', Sex: null,
      S1: 'I don\u00e2\u20ac\u2122t own or use a mobile phone/Sina wala situmii simu ya mkononi',
    });
    expect(payload).not.toHaveProperty('probability');
    await user.selectOptions(screen.getByRole('combobox', { name: /^sex/i }), 'Female');
    expect(screen.queryByText('Financially Excluded')).not.toBeInTheDocument();
  });

  it('offers explicit missing income and shows connectivity errors', async () => {
    const user = userEvent.setup();
    vi.stubGlobal('fetch', vi.fn().mockRejectedValue(new TypeError('network failure')));
    render(<App />);
    await user.type(screen.getByRole('spinbutton', { name: /^age/i }), '36');
    await user.click(screen.getByRole('checkbox', { name: /income unavailable/i }));
    expect(screen.getByRole('spinbutton', { name: /^total income/i })).toBeDisabled();
    for (const select of screen.getAllByRole('combobox')) {
      await user.selectOptions(select, '__missing__');
    }
    await user.click(screen.getByRole('button', { name: /generate prediction/i }));
    expect(await screen.findByRole('alert')).toHaveTextContent('Unable to connect');
    expect(JSON.parse(fetch.mock.calls[0][1].body).B3Ii).toBeNull();
  });

  it('disables submission while the service is responding', async () => {
    const user = userEvent.setup();
    let resolve;
    vi.stubGlobal('fetch', vi.fn(() => new Promise((done) => { resolve = done; })));
    render(<App />);
    await user.type(screen.getByRole('spinbutton', { name: /^age/i }), '30');
    await user.click(screen.getByRole('checkbox', { name: /income unavailable/i }));
    for (const select of screen.getAllByRole('combobox')) {
      await user.selectOptions(select, '__missing__');
    }
    await user.click(screen.getByRole('button', { name: /generate prediction/i }));
    expect(screen.getByRole('button', { name: /generating prediction/i })).toBeDisabled();
    resolve({ ok: true, json: async () => ({ financial_exclusion_status: 0, label: 'Financially included' }) });
    await waitFor(() => expect(screen.getByText('Financially Included')).toBeInTheDocument());
  });
});

it('validates numeric edge cases without altering approved category values', () => {
  const values = Object.fromEntries(fields.map((field) => [field.name, field.options?.[0].value ?? '']));
  expect(prepareRequest({ ...values, A18: '17', B3Ii: '-1' }, false).errors).toHaveProperty('A18');
  expect(prepareRequest({ ...values, A18: '99', B3Ii: '-1' }, false).errors).toHaveProperty('B3Ii');
  expect(prepareRequest({ ...values, A18: '18', B3Ii: '0' }, false).payload.B3Ii).toBe(0);
});
