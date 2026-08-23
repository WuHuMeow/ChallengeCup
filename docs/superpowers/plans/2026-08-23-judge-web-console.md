# Judge Web Console Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Build a judge-facing React console that runs a representative SUMO demo, exposes verified evidence clearly, and is served by the existing FastAPI application.

**Architecture:** A React 18/Vite SPA uses one typed client for REST and run-scoped WebSocket events. A small external-store implementation owns run state and rejects stale frame sequences; views remain presentation-focused. Vite emits `api/static/dist`, which FastAPI serves in production.

**Tech Stack:** React 18, TypeScript 5, Vite, Recharts, Lucide React, Playwright, npm.

**Spec:** `docs/superpowers/specs/2026-08-23-judge-web-console-design.md`

## Global Constraints

- The production build must be emitted to `api/static/dist` and contain no external CDN dependency.
- The REST client must use the canonical `/api/*` routes and must not expose `run_dir`.
- Frame updates must accept only a strictly newer `X-Frame-Sequence` for the active `run_id`.
- `/api/results` and `/api/runs/{run_id}/safety` are the only sources for formal evidence and safety badges.
- Quick demo output must be labeled separately from formal evidence.
- Do not modify `赛题资料.7z`, `data/intersection_data`, SUMO source files, or algorithm core code.
- Every user-facing icon-only control needs an accessible name; layout dimensions must remain stable while data loads.

---

### Task 1: Scaffold the frontend and write the browser RED test

**Files:**
- Create: `web/package.json`
- Create: `web/package-lock.json`
- Create: `web/tsconfig.json`
- Create: `web/vite.config.ts`
- Create: `web/index.html`
- Create: `web/tests/judge-flow.spec.ts`

**Interfaces:**
- Produces npm scripts `dev`, `build`, `typecheck`, and `test:e2e`.
- Produces a Playwright test that expects the four navigation views, a demo form, a nonblank frame, and an explicit formal-evidence label.

- [ ] **Step 1: Write the failing browser test**

```ts
import { expect, test } from "@playwright/test";

test("judge can navigate the demo and see a real frame placeholder", async ({ page }) => {
  await page.goto("/");
  await expect(page.getByRole("navigation")).toContainText("Simulation");
  await page.getByRole("button", { name: "Start quick demo" }).click();
  await expect(page.getByRole("img", { name: "SUMO simulation frame" })).toHaveAttribute(
    "src",
    /data:image|\/api\/runs\//,
  );
  await expect(page.getByText("Quick demo output")).toBeVisible();
  await expect(page.getByText("Formal evidence")).toBeVisible();
});
```

- [ ] **Step 2: Add the Vite and Playwright configuration**

Configure the Vite root as `web`, output directory as `../api/static/dist`, `strictPort: true`, and `/api` proxy target `http://127.0.0.1:8000`. Configure Playwright to use `web` as the web server command and retain traces only on failure.

- [ ] **Step 3: Run the RED test**

Run: `npm ci; npm run test:e2e -- --project=chromium web/tests/judge-flow.spec.ts`

Expected: FAIL because the application entry point and the named controls do not exist.

- [ ] **Step 4: Commit the scaffold and RED test**

```bash
git add web/package.json web/package-lock.json web/tsconfig.json web/vite.config.ts web/index.html web/tests/judge-flow.spec.ts
git commit -m "test: define judge console browser flow"
```

### Task 2: Implement the typed API client and run store

**Files:**
- Create: `web/src/api/client.ts`
- Create: `web/src/state/runStore.ts`
- Create: `web/src/main.tsx`
- Create: `web/src/App.tsx`

**Interfaces:**
- `createApiClient(baseUrl?: string): JudgeApiClient` exposes `listScenes`, `listAlgorithms`, `startRun`, `getRun`, `stopRun`, `getMetrics`, `getFrame`, `listResults`, `getResult`, `getSafety`, `openNativeGui`, and `subscribeEvents`.
- `runStore` exposes `selectedScene`, `selectedAlgorithm`, `selectedLoad`, `selectedDisturbance`, `activeRun`, `metrics`, `events`, `frameSequence`, `frameUrl`, `formalEvidence`, and `error`.
- `acceptFrame({ runId, sequence, simulationTime, blobUrl })` returns `boolean` and rejects a stale run or sequence.

- [ ] **Step 1: Add client-focused RED assertions to the browser fixture**

Route `/api/scenes`, `/api/algorithms`, `/api/runs`, `/api/runs/run-quick/frame`, and `/api/runs/run-quick/safety` in Playwright. Assert that the POST body uses `intersection_id`, canonical algorithm keys, `flow_multiplier`, `seed`, and `duration_seconds`; assert that a response with sequence `1` cannot replace an accepted sequence `2`.

- [ ] **Step 2: Implement the exact public types and fetch helpers**

Use `response.ok` checks that include the server `detail` in `ApiError`. Decode PNG responses as `Blob`, read `X-Run-Id`, `X-Frame-Sequence`, and `X-Simulation-Time`, and create object URLs only after a successful response.

- [ ] **Step 3: Implement the external store and cleanup**

Use a `Set` of listeners and a single immutable snapshot. Revoke the previous object URL when a newer accepted frame arrives or when `resetRun()` is called. WebSocket close events set `error.kind = "disconnected"` without changing a terminal run to completed.

- [ ] **Step 4: Run typecheck and the focused browser test**

Run: `npm run typecheck; npm run test:e2e -- --project=chromium web/tests/judge-flow.spec.ts`

Expected: typecheck passes; the test remains RED only for missing view components, not for client or state errors.

- [ ] **Step 5: Commit the client and store**

```bash
git add web/src/api/client.ts web/src/state/runStore.ts web/src/main.tsx web/src/App.tsx web/tests/judge-flow.spec.ts
git commit -m "feat: add typed judge API client and run store"
```

### Task 3: Build the real-time Simulation view

**Files:**
- Create: `web/src/components/SimulationView.tsx`
- Create: `web/src/components/SumoFrame.tsx`
- Create: `web/src/components/MetricPanel.tsx`
- Create: `web/src/components/ErrorBanner.tsx`

**Interfaces:**
- `SimulationView` accepts a `JudgeApiClient` and store snapshot, and emits `onStart`, `onStop`, `onSceneChange`, and `onAlgorithmChange` callbacks.
- `SumoFrame` accepts `src: string | null`, `sequence: number | null`, and `simulationTime: number | null`; its image always has the accessible name `SUMO simulation frame`.
- `MetricPanel` renders `Record<string, unknown>` without converting `null` to zero.

- [ ] **Step 1: Extend the RED test with the real controls**

Assert that scene and algorithm selectors are labeled, the quick-demo button starts a run, stop calls `POST /api/runs/{run_id}/stop`, the frame shows sequence/time, and the native GUI control reports a 409 error without hiding the run state.

- [ ] **Step 2: Implement stable frame and error components**

Use a fixed `aspect-ratio` frame region with an explicit empty/loading state. Render sequence and simulation time outside the image, and render errors through a single alert region with retry/stop actions where meaningful.

- [ ] **Step 3: Implement the simulation lifecycle**

On start, submit a short representative run using the selected scene and algorithm, attach WebSocket events, and start a bounded frame poller. Stop polling and close the socket on terminal status, stop, unmount, or run replacement. Do not display a formal-evidence badge for the active demo.

- [ ] **Step 4: Make the test GREEN**

Run: `npm run typecheck; npm run test:e2e -- --project=chromium web/tests/judge-flow.spec.ts`

Expected: the quick demo starts, the fixture frame is nonblank, stale sequence responses are ignored, and the test passes.

- [ ] **Step 5: Commit the simulation view**

```bash
git add web/src/components/SimulationView.tsx web/src/components/SumoFrame.tsx web/src/components/MetricPanel.tsx web/src/components/ErrorBanner.tsx web/tests/judge-flow.spec.ts
git commit -m "feat: add real-time judge simulation view"
```

### Task 4: Build Comparison, History, and Scene views

**Files:**
- Create: `web/src/components/ComparisonView.tsx`
- Create: `web/src/components/HistoryView.tsx`
- Create: `web/src/components/SceneView.tsx`

**Interfaces:**
- `ComparisonView` consumes validated `ResultListItem[]` and renders Recharts series from numeric metrics only.
- `HistoryView` consumes `/api/results` and never renders `run_dir`.
- `SceneView` consumes `SceneManifest[]` and renders provenance fields, validation status, and warnings.

- [ ] **Step 1: Add view and evidence-label RED assertions**

Mock one sealed result, one unsealed result, one scene warning, and a metric with `null`. Assert that only the sealed result appears as formal evidence, `null` is shown as unavailable, and scene provenance is visible.

- [ ] **Step 2: Implement comparison with explicit baseline labels**

Display fixed-time/actuated/classic MaxPressure/capacity-aware MaxPressure names from the API key, and keep chart units beside each axis. Never infer a performance improvement when a metric is absent.

- [ ] **Step 3: Implement history and scene provenance**

Use loading/empty/error states. Render SHA-256 and source file summaries as inspectable text, but do not expose filesystem paths.

- [ ] **Step 4: Run the focused view tests**

Run: `npm run typecheck; npm run test:e2e -- --project=chromium web/tests/judge-flow.spec.ts`

Expected: all four views are reachable and evidence labels remain correct.

- [ ] **Step 5: Commit the supporting views**

```bash
git add web/src/components/ComparisonView.tsx web/src/components/HistoryView.tsx web/src/components/SceneView.tsx web/tests/judge-flow.spec.ts
git commit -m "feat: add evidence comparison history and scene views"
```

### Task 5: Integrate responsive layout, accessibility, and build output

**Files:**
- Modify: `web/src/App.tsx`
- Create: `web/src/styles.css`
- Modify: `web/src/main.tsx`

**Interfaces:**
- `App` exposes navigation for `simulation`, `comparison`, `history`, and `scene` with a single active view.
- Every icon-only action has an `aria-label` and a visible tooltip/title where the icon is unfamiliar.

- [ ] **Step 1: Add layout and keyboard RED assertions**

Run Playwright at desktop and 390px mobile widths. Assert no horizontal overflow, that the active navigation control is keyboard focusable, and that the frame region retains its dimensions while loading.

- [ ] **Step 2: Implement the visual system**

Use restrained operational colors, compact panels, stable grids, and responsive columns. Keep evidence labels visually distinct from quick-demo labels. Do not add decorative gradients, orbs, or marketing hero sections.

- [ ] **Step 3: Wire the FastAPI static entry**

Render the SPA through `api/static.py`'s existing `index.html` route; do not add a second server-side fallback or weaken path containment.

- [ ] **Step 4: Run the complete frontend gate**

Run: `npm ci; npm run typecheck; npm run build; npm run test:e2e -- --project=chromium`

Expected: build succeeds, `api/static/dist/index.html` exists, desktop/mobile browser tests pass, and the image is nonblank.

- [ ] **Step 5: Commit the integrated console**

```bash
git add web api/static.py web/src
git commit -m "feat: publish judge-facing Web console"
```

### Task 6: Run repository regression and independent review

**Files:**
- Test: `tests/test_judge_api.py`
- Test: `tests/test_api_contract.py`
- Test: `web/tests/judge-flow.spec.ts`

- [ ] **Step 1: Run the Python API contract tests**

Run: `python -m pytest tests/test_judge_api.py tests/test_api_contract.py -q`

Expected: PASS with no changes to checked-in OpenAPI/Postman bytes.

- [ ] **Step 2: Run the full repository suite and static gates**

Run: `python -m pytest -q; python -m compileall -q api core engine algorithms scenes visualization; git diff --check`

Expected: the existing green baseline remains green; any pre-existing `.pytest_cache` permission warning is recorded without changing protected files.

- [ ] **Step 3: Verify protected invariants**

Record the SHA-256 of `赛题资料.7z`, tracked/disk counts for `data/intersection_data`, and the final `git status`. The values must match the Task 16 baseline.

- [ ] **Step 4: Perform an independent review**

Review the diff for stale-frame races, path exposure, evidence overclaiming, accessibility regressions, and stale browser object URLs before declaring Task 17 complete.

- [ ] **Step 5: Commit the verified task record**

```bash
git add docs/superpowers/specs/2026-08-23-judge-web-console-design.md docs/superpowers/plans/2026-08-23-judge-web-console.md web api tests
git commit -m "test: verify judge web console release flow"
```
