# FinAccess Insights frontend

A React/Vite research demonstration for the existing FastAPI prediction service.
Predictions are estimates, not definitive assessments or a basis for decisions
about individuals. Do not enter real personal data for a public demonstration.

## Requirements and local setup

Use Node.js 20.19+ on the 20.x line, or 22.12 or newer, npm, the project's
Python environment and the trusted local SVM artifact. From the repository root,
start the API as described in the main README:

```powershell
.\.venv\Scripts\python.exe -m uvicorn src.financial_exclusion.api.main:app --host 127.0.0.1 --port 8000
```

In another terminal:

```powershell
Set-Location frontend
npm ci
Copy-Item .env.example .env
npm run dev
```

Open the local URL printed by Vite. Verify the API is ready at
`http://127.0.0.1:8000/health` if predictions are unavailable.

## API configuration

`VITE_API_BASE_URL` is the client-visible base path; it defaults to `/api`.
`API_PROXY_TARGET` configures the Vite development server's `/api` proxy and
defaults to `http://127.0.0.1:8000`. The proxy removes `/api` before forwarding
`POST /api/predict` to the backend's `POST /predict`. Restart Vite after
changing the environment file.

The backend does not enable CORS. For a production build, arrange a same-origin
reverse proxy to forward `/api/*` to the FastAPI service without the `/api`
prefix. `npm run preview` is a static preview and does not provide that proxy.
If another deployment path is needed, configure `VITE_API_BASE_URL` at build time
and configure the reverse proxy accordingly. Vite variables are embedded in
the browser bundle; never place secrets in them.

The root Docker Compose configuration builds this frontend with `/api` and
serves it through Nginx, which proxies the API and Swagger paths. See the root
README for container startup, the read-only local model mount and port settings.

## Validation and build

```powershell
npm test
npm run build
```

All 17 API fields require a response. Select “Unavailable” to send `null` for
missing fields other than age; the fitted model imputes these. Monthly income
may also be marked unavailable. The form sends the workbook's exact categorical
values, including encoding artifacts and the unresolved education code 95.
Binary income-source fields deliberately display their workbook indicator codes,
because their export-to-questionnaire crosswalk is not verified. These options
reflect the locally saved model's fitted input categories; they are not a
general-purpose survey codebook. An updated model may require a reviewed option
mapping. Codes 98/99 for income are treated as missing by the saved pipeline.

The model provides no calibrated probabilities. Survey-design limitations and
the unverified provider classification are explained in the interface and the
main project documentation. No training records or support vectors are sent to
the frontend.

The local API has no authentication, TLS or rate limiting. These controls,
privacy risk assessment and appropriate data governance are necessary before
external deployment.
