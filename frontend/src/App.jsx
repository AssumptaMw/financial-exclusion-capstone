import { useEffect, useRef, useState } from 'react';
import { predict } from './api.js';
import { MISSING, prepareRequest, sections } from './fields.js';

function Mark() {
  return (
    <span className="brand-mark" aria-hidden="true">
      <svg viewBox="0 0 32 32" fill="none">
        <path d="M7 23V15M13 23V9M19 23V13M25 23V6" stroke="currentColor" strokeWidth="2.5" strokeLinecap="round" />
        <path d="M6 26H26" stroke="currentColor" strokeWidth="2" strokeLinecap="round" />
      </svg>
    </span>
  );
}

function Field({ field, value, error, onChange, incomeMissing, onIncomeMissing }) {
  const describedBy = [field.hint ? `${field.name}-hint` : '', error ? `${field.name}-error` : '']
    .filter(Boolean).join(' ') || undefined;
  return (
    <div className={`field ${field.type === 'income' ? 'income-field' : ''}`}>
      <label htmlFor={field.name}>{field.label} <span className="field-code">{field.name}</span></label>
      {field.options ? (
        <select id={field.name} name={field.name} value={value} onChange={(event) => onChange(field.name, event.target.value)}
          aria-invalid={Boolean(error)} aria-describedby={describedBy} required>
          <option value="">Select a response</option>
          {field.options.map((entry) => <option key={entry.value} value={entry.value}>{entry.label}</option>)}
          <option value={MISSING}>Unavailable (model imputes)</option>
        </select>
      ) : (
        <div className="input-wrap">
          {field.type === 'income' && <span className="input-prefix" aria-hidden="true">KSh</span>}
          <input id={field.name} name={field.name} type="number" value={value}
            min={field.type === 'age' ? 18 : 0} step={field.type === 'age' ? 1 : 'any'}
            inputMode={field.type === 'age' ? 'numeric' : 'decimal'}
            placeholder={field.type === 'age' ? 'e.g. 35' : 'e.g. 10000'}
            disabled={field.type === 'income' && incomeMissing}
            onChange={(event) => onChange(field.name, event.target.value)}
            aria-invalid={Boolean(error)} aria-describedby={describedBy} required={!incomeMissing || field.type === 'age'} />
        </div>
      )}
      {field.type === 'income' && (
        <label className="checkbox-label">
          <input type="checkbox" checked={incomeMissing} onChange={(event) => onIncomeMissing(event.target.checked)} />
          Income unavailable (model imputes)
        </label>
      )}
      {field.hint && <p className="field-hint" id={`${field.name}-hint`}>{field.hint}</p>}
      {error && <p className="field-error" id={`${field.name}-error`}>{error}</p>}
    </div>
  );
}

function Results({ result, loading, resultRef }) {
  const excluded = result?.financial_exclusion_status === 1;
  return (
    <section className={`result-card ${result ? (excluded ? 'result-excluded' : 'result-included') : ''}`}
      id="result" aria-labelledby="result-title" aria-live="polite" tabIndex={-1} ref={resultRef}>
      <div className="result-heading">
        <span className="eyebrow">MODEL OUTPUT</span>
        <span className="result-icon" aria-hidden="true">{result ? (excluded ? '!' : '✓') : '↗'}</span>
      </div>
      <h2 id="result-title">{result ? 'Prediction result' : 'Your result appears here'}</h2>
      {result ? (
        <>
          <div className="result-label">{excluded ? 'Financially Excluded' : 'Financially Included'}</div>
          <p>The model’s predicted classification for the responses provided.</p>
        </>
      ) : (
        <p>{loading ? 'The model is processing your responses.' : 'Complete the form to see the model’s predicted classification.'}</p>
      )}
      <div className="result-note">
        <strong>An estimate, not a verdict.</strong>
        <span>Predictions are not definitive assessments of individuals and should not be used as the sole basis for decisions.</span>
      </div>
    </section>
  );
}

export default function App() {
  const [values, setValues] = useState({});
  const [incomeMissing, setIncomeMissing] = useState(false);
  const [errors, setErrors] = useState({});
  const [result, setResult] = useState(null);
  const [error, setError] = useState('');
  const [loading, setLoading] = useState(false);
  const resultRef = useRef(null);

  useEffect(() => {
    if (result) resultRef.current?.focus();
  }, [result]);

  function update(name, value) {
    setValues((current) => ({ ...current, [name]: value }));
    setErrors((current) => ({ ...current, [name]: undefined }));
    setResult(null);
    setError('');
  }

  function updateIncomeMissing(checked) {
    setIncomeMissing(checked);
    setErrors((current) => ({ ...current, B3Ii: undefined }));
    setResult(null);
    setError('');
  }

  async function submit(event) {
    event.preventDefault();
    const prepared = prepareRequest(values, incomeMissing);
    setErrors(prepared.errors);
    setResult(null);
    setError('');
    if (Object.keys(prepared.errors).length) {
      setError('Please review the highlighted fields before continuing.');
      return;
    }
    setLoading(true);
    try {
      setResult(await predict(prepared.payload));
    } catch (reason) {
      setError(reason instanceof Error ? reason.message : 'The prediction request failed. Please try again.');
    } finally {
      setLoading(false);
    }
  }

  return (
    <>
      <a className="skip-link" href="#prediction">Skip to prediction form</a>
      <header className="site-header">
        <div className="header-inner">
          <a className="brand" href="#top" aria-label="FinAccess Insights home"><Mark /><span>FinAccess <strong>Insights</strong><small>RESEARCH PROJECT</small></span></a>
          <nav aria-label="Main navigation">
            <a href="#prediction">Prediction</a>
            <a href="#about">About the model</a>
          </nav>
          <span className="header-tag"><span /> MSc CAPSTONE</span>
        </div>
      </header>

      <main id="top">
        <section className="hero">
          <div className="hero-inner">
            <div className="hero-copy">
              <span className="hero-kicker"><span /> EXPLAINABLE MACHINE LEARNING</span>
              <h1>Understanding financial <em>exclusion</em> in Kenya.</h1>
              <p>Explore a research model built using the 2024 FinAccess Household Survey. Enter a set of responses to generate an estimated classification.</p>
              <a className="hero-link" href="#prediction">Explore the prediction tool <span aria-hidden="true">↗</span></a>
            </div>
            <div className="hero-aside" aria-label="Research context">
              <span className="hero-aside-title">THE RESEARCH CONTEXT</span>
              <div><strong>2024</strong><span>FinAccess household survey</span></div>
              <div><strong>17</strong><span>approved predictor fields</span></div>
              <p>Designed for exploration and academic demonstration, not individual decision-making.</p>
            </div>
          </div>
        </section>

        <div className="content-shell">
          <div className="section-intro" id="prediction">
            <div><span className="eyebrow">PREDICTION WORKSPACE</span><h2>Explore a prediction</h2>
              <p>Provide all 17 responses below. Choose “Unavailable” where a response is missing; the model will impute it.</p></div>
            <span className="privacy-badge"><span aria-hidden="true">◈</span> Research demonstration</span>
          </div>

          <div className="workspace">
            <form className="form-card" onSubmit={submit} noValidate>
              <div className="form-header"><div><h3>Respondent information</h3><p>All fields require a response.</p></div><span>17 FIELDS</span></div>
              <fieldset disabled={loading} className="form-fieldset">
                {sections.map((section) => (
                  <section className="form-section" key={section.number} aria-labelledby={`section-${section.number}`}>
                    <div className="section-heading">
                      <span className="section-number">{section.number}</span>
                      <div><h4 id={`section-${section.number}`}>{section.title}</h4><p>{section.description}</p></div>
                    </div>
                    <div className="field-grid">
                      {section.fields.map((field) => (
                        <Field key={field.name} field={field} value={values[field.name] ?? ''}
                          error={errors[field.name]} onChange={update} incomeMissing={incomeMissing}
                          onIncomeMissing={updateIncomeMissing} />
                      ))}
                    </div>
                  </section>
                ))}
              </fieldset>
              <div className="form-actions">
                {error && <p className="form-alert" role="alert">{error}</p>}
                <button className="submit-button" type="submit" disabled={loading}>
                  {loading ? 'Generating prediction…' : 'Generate prediction'}
                  {!loading && <span aria-hidden="true">→</span>}
                </button>
                <p>By submitting, the responses are sent to the configured prediction service.</p>
              </div>
            </form>

            <aside className="sidebar">
              <Results result={result} loading={loading} resultRef={resultRef} />
              <section className="about-card" id="about">
                <span className="eyebrow">UNDER THE HOOD</span>
                <h2>About this model</h2>
                <p>An RBF support vector machine uses the approved predictors and the existing fitted preprocessing pipeline to estimate a binary classification.</p>
                <div className="about-divider" />
                <h3>Important limitations</h3>
                <ul>
                  <li>The provider’s original classification derivation has not been independently verified.</li>
                  <li>Results are unweighted and are not nationally representative or causal.</li>
                  <li>The held-out test set was previously evaluated; it is not a pristine independent assessment.</li>
                  <li>Missing responses are imputed. No calibrated probabilities are available.</li>
                </ul>
                <p className="about-footnote">Explainability describes model associations, not causes.</p>
              </section>
            </aside>
          </div>
        </div>
      </main>
      <footer><span>FinAccess Insights</span><p>An MSc Data Science capstone · Academic research demonstration</p><a href="#top">Back to top ↑</a></footer>
    </>
  );
}
