# PRISM Web Frontend

Evidence-first PRISM web client built around the project architecture: Sentinel, multi-interpreter analysis, Semantic Fractures, PRISM Lab, Artifact Passports, Capability Graphs, and Immune Memory.

## Design

Theme E: warm off-white surfaces, dark ink navigation, restrained cobalt primary accent, and semantic severity colors only where real data warrants them.

The UI deliberately avoids synthetic counts, example filenames, fake hashes, fake activity feeds, fake telemetry, status dots, "LIVE" labels, AI badges, and decorative cyberpunk elements. When data is unavailable, the UI renders an explicit empty/loading/error state.

## Stack

- Next.js App Router
- React
- TypeScript
- Tailwind CSS v4
- TanStack Query
- React Flow
- Lucide
- Supabase SSR + OAuth

## Run locally

```bash
npm install
cp .env.example .env.local
npm run dev
```

Set `NEXT_PUBLIC_PRISM_API_URL` to the FastAPI backend. For authentication, set `NEXT_PUBLIC_SUPABASE_URL` and either `NEXT_PUBLIC_SUPABASE_PUBLISHABLE_KEY` or `NEXT_PUBLIC_SUPABASE_ANON_KEY`.

## Backend contracts used by the client

The current web client is wired to the endpoints that actually exist in the supplied FastAPI repository:

- `GET /health`
- `POST /api/artifacts`
- `GET /api/artifacts/{id}`
- `POST /api/artifacts/{id}/fastscan`
- `GET /api/artifacts/{id}/fastscan`
- `POST /api/artifacts/{id}/interpret`
- `GET /api/artifacts/{id}/interpretation`
- `POST /api/artifacts/{id}/graph`
- `GET /api/artifacts/{id}/graph`

The artifact workspace runs the real backend flow in order: ingestion → FastScan → interpretation → graph.

## Notes

The first backend sketch does not define a global `GET /api/artifacts` or global fractures/experiments collections. Those pages therefore remain empty until the corresponding list APIs exist.

The artifact detail route consumes the real per-artifact artifact, FastScan, interpretation, and Interpretation Graph responses exposed by the supplied backend. Fracture, Passport, and other intelligence surfaces remain explicit contract placeholders until those APIs are added.

## PRISM brand motion

The cleaned PRISM mark is included at `public/prism-mark.svg` and is used in the application shell, login experience, favicon, and navigation transition. Sidebar navigation uses a restrained full-view transition: the PRISM mark settles into place with a very small breathing motion and a single cobalt beam. The transition is intentionally text-free and has a reduced-motion fallback.

## Authentication

The client includes `/login` with Google OAuth and email/password sign-in through Supabase. When Supabase credentials are present, the application routes are protected by middleware and Google OAuth returns through `/auth/callback`. Without those variables, the login screen uses a clearly temporary local workspace-access flow so the frontend can be exercised before the real provider is connected. The placeholder session is stored only in local browser storage and is replaced by Supabase auth when provider credentials are added.

## Running against the supplied FastAPI repository

Start the backend from its `backend` directory:

```bash
python -m uvicorn app.main:app --reload --port 8000
```

Then create `.env.local` from `.env.example` in this frontend and keep:

```bash
NEXT_PUBLIC_PRISM_API_URL=http://localhost:8000
```

Start the web client:

```bash
npm install
npm run dev
```

Open `http://localhost:3000`.

The upload flow is intentionally aligned to the actual backend contract. The client does not call the older `/analyze`, `/analysis`, `/interpretations`, `/fractures`, `/passport`, or `/immune-memory` routes that were present in the earlier UI scaffold.
