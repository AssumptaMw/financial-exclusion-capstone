const baseUrl = (import.meta.env.VITE_API_BASE_URL || '/api').replace(/\/+$/, '');

export async function predict(payload) {
  let response;
  try {
    response = await fetch(`${baseUrl}/predict`, {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify(payload),
    });
  } catch {
    throw new Error('Unable to connect to the prediction service. Check that the API is running and try again.');
  }

  if (!response.ok) {
    if (response.status === 422) {
      throw new Error('The service could not validate the request. Review the responses and try again.');
    }
    if (response.status === 503) {
      throw new Error('The prediction model is unavailable. Check the API and local model, then try again.');
    }
    throw new Error('The prediction service could not complete the request. Please try again.');
  }

  let result;
  try {
    result = await response.json();
  } catch {
    throw new Error('The prediction service returned an invalid response.');
  }
  const valid = (result?.financial_exclusion_status === 0 && result?.label === 'Financially included')
    || (result?.financial_exclusion_status === 1 && result?.label === 'Financially excluded');
  if (!valid) {
    throw new Error('The prediction service returned an invalid response.');
  }
  return result;
}
