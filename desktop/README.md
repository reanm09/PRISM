PRISM Sentinel Desktop v0.7.4 — build-fixed

# PRISM Sentinel Desktop v0.7.4

PRISM Sentinel is the native Windows client for the PRISM artifact-analysis platform.
It combines the investigation surfaces of the PRISM web application with native endpoint capabilities.

## What is in this build

### Full PRISM client surface

- Sentinel overview, interception, artifacts, fractures, review queue, scanning, watch locations, quarantine, and history.
- Interpretation Graph.
- PRISM Lab.
- Experiments / investigation state.
- Evidence.
- Comparisons.
- Artifact Passports.
- Capability Graph.
- Immune Memory.
- Local Files and Policies.

### Native Windows capabilities

- Read real local files through the Rust/Tauri layer.
- Scan an individual file.
- Recursively scan a directory.
- Monitor selected directories recursively.
- Re-scan created/modified files from watched directories.
- Persist local scan history.
- View authenticated, encrypted Sentinel quarantine records from the local PRISM backend and restore by quarantine ID.
- Recover legacy desktop quarantine records created by older builds; new local scans do not create these unencrypted records.
- Reveal files in Windows Explorer.
- Hand off a locally inspected artifact to the PRISM FastAPI backend.

There is no generated dashboard telemetry or hard-coded artifact data. Empty, unavailable, and disconnected states are shown honestly.

## Development

Requirements on Windows:

- Node.js
- Rust toolchain
- Tauri Windows prerequisites (Microsoft C++ Build Tools and WebView2)

Install frontend dependencies:

```powershell
npm install
```

Run the desktop app in development mode:

```powershell
npm run tauri:dev
```

Build the Windows installer:

```powershell
npm run tauri:build
```

The generated installers are placed under:

```text
src-tauri\target\release\bundle\
```

The NSIS setup executable is the usual file to distribute to Windows users.

## Backend connection

Default endpoint:

```text
http://127.0.0.1:8000
```

Change it in **Settings → PRISM API endpoint**.

Local scanning, history, and review-only watching work without the backend. Encrypted quarantine and deterministic investigation require the local backend. Backend watch roots are configured separately with `prism watch add`. The desktop accepts only a loopback HTTP backend endpoint.

## Safety model

PRISM analyzes untrusted artifacts. The native layer does not execute the selected artifact. It reads bytes, computes SHA-256, inspects inexpensive local evidence, and applies bounded local heuristics. Deeper parser execution, experiments, and Lab reasoning remain backend responsibilities.


### v0.7.3 UI fix
- Uses the exact PRISM Sentinel logo asset supplied for the app and Windows bundle.
- Locks the application shell to the native window; only the main content pane scrolls.
- Prevents browser-style page panning/dragging from moving the entire interface.


### Monorepo note
This desktop project is designed to live under `desktop/` inside the main PRISM repository. A local PostCSS config prevents the desktop Vite build from inheriting the parent repository's CSS configuration.
