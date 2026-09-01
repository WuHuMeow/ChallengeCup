import { expect, test, type Page } from "@playwright/test";

const PNG = Buffer.from(
  "iVBORw0KGgoAAAANSUhEUgAAAAEAAAABCAQAAAC1HAwCAAAAC0lEQVR42mP8/x8AAusB9Wl2n0kAAAAASUVORK5CYII=",
  "base64",
);

const scene = {
  scene_id: "1",
  intersection_id: "1",
  name: "Test intersection",
  description: "fixture",
  source_files: { net: "data/intersection_data/scene.net.xml" },
  sha256: { net: "a".repeat(64) },
  step_length: 1,
  tls_ids: ["tls-1"],
  lane_ids: ["lane-1"],
  movement_count: 1,
  validation_status: "pass",
  warnings: ["fixture warning"],
};

async function mockJudgeApi(page: Page) {
  const startPayloads: Record<string, unknown>[] = [];
  await page.route("**/api/scenes", (route) => route.fulfill({ json: [scene] }));
  await page.route("**/api/algorithms", (route) =>
    route.fulfill({
      json: {
        formal: [
          {
            key: "fixed_time",
            display_name: "Fixed Time",
            formal: true,
            available: true,
            unavailable_reason: null,
          },
          {
            key: "capacity_aware_maxpressure",
            display_name: "Capacity-Aware MaxPressure",
            formal: true,
            available: true,
            unavailable_reason: null,
          },
        ],
        optional: [],
      },
    }),
  );
  await page.route("**/api/runs", async (route) => {
    expect(route.request().method()).toBe("POST");
    const body = route.request().postDataJSON();
    startPayloads.push(body);
    await route.fulfill({
      status: 202,
      json: {
        run_id: "run-quick",
        status: "queued",
        reason: "",
        run_dir: "hidden",
        summary: null,
        algorithm: "fixed_time",
      },
    });
  });
  await page.route("**/api/runs/run-quick/frame**", async (route) => {
    const requested = new URL(route.request().url()).searchParams.get("sequence");
    const sequence = requested === "2" ? 1 : 2;
    await route.fulfill({
      status: 200,
      contentType: "image/png",
      headers: {
        "X-Run-Id": "run-quick",
        "X-Frame-Sequence": String(sequence),
        "X-Simulation-Time": String(sequence),
      },
      body: PNG,
    });
  });
  await page.route("**/api/runs/run-quick/safety", (route) =>
    route.fulfill({
      json: {
        collision: 0,
        red_light: 0,
        illegal_transition: 0,
        harsh_braking: 0,
        teleport: 0,
        potential_conflict: 0,
      },
    }),
  );
  const formalResult = {
    run_id: "formal-1",
    status: "completed",
    reason: "",
    algorithm: "fixed_time",
    scene_id: "1",
    run_dir: "hidden",
    summary: {
      metrics: {
        avg_queue_length: 3.5,
        throughput: null,
        fuel_ml: 12,
        co2_g: 3,
        collision_count: 1,
        red_light_count: 2,
        illegal_transition_count: 3,
        harsh_braking_count: 4,
        teleport_count: 5,
        potential_conflict_count: 6,
      },
      units: {
        collision_count: "count",
        red_light_count: "count",
        illegal_transition_count: "count",
        harsh_braking_count: "count",
        teleport_count: "count",
        potential_conflict_count: "count",
      },
    },
  };
  const otherSceneResult = {
    ...formalResult,
    run_id: "formal-2",
    algorithm: "capacity_aware_maxpressure",
    scene_id: "2",
    summary: {
      metrics: { ...formalResult.summary.metrics, avg_queue_length: 99 },
      units: formalResult.summary.units,
    },
  };
  await page.route("**/api/results", (route) => route.fulfill({ status: 200, json: { items: [formalResult, otherSceneResult], count: 2 } }));
  await page.route("**/api/results/formal-1", (route) => route.fulfill({ status: 200, json: formalResult }));
  return { startPayloads };
}

test("judge can navigate the demo and see a real frame placeholder", async ({ page }) => {
  const { startPayloads } = await mockJudgeApi(page);
  await page.goto("/");
  await expect(page.getByRole("navigation")).toContainText("Simulation");
  await page.getByRole("button", { name: "Start quick demo" }).click();
  await expect(page.getByRole("img", { name: "SUMO simulation frame" })).toHaveAttribute(
    "src",
    /data:image|\/api\/runs\/|blob:/,
  );
  await expect.poll(() => page.getByRole("img", { name: "SUMO simulation frame" }).evaluate((image: HTMLImageElement) => image.naturalWidth)).toBeGreaterThan(0);
  await expect(page.getByText("Quick demo output")).toBeVisible();
  await expect(page.getByText("Sealed individual-run evidence is shown only for verified results from the evidence API; formal matrix conclusions await Task 22.")).toBeVisible();
  await expect(page.getByRole("region", { name: "Safety counters" })).toContainText(/Collision\s*0/);
  expect(startPayloads[0]).toMatchObject({
    intersection_id: "1",
    algorithm: "fixed_time",
    flow_multiplier: 1,
    seed: 42,
    duration_seconds: 30,
    warmup_seconds: 0,
    disturbance: null,
  });
});

test("typed run responses never retain server filesystem paths", async ({ page }) => {
  await mockJudgeApi(page);
  await page.goto("/");
  const retainsRunDir = await page.evaluate(async () => {
    const { createApiClient } = await import("/src/api/client.ts");
    const result = await createApiClient().startRun({
      intersection_id: "1",
      algorithm: "fixed_time",
      flow_multiplier: 1,
      seed: 42,
      duration_seconds: 30,
      warmup_seconds: 0,
      disturbance: null,
    });
    return Object.prototype.hasOwnProperty.call(result, "run_dir");
  });
  expect(retainsRunDir).toBe(false);
});

test("selected run parameters are sent to the judge API", async ({ page }) => {
  const { startPayloads } = await mockJudgeApi(page);
  await page.goto("/");
  await page.getByLabel("Flow multiplier").fill("1.5");
  await page.getByLabel("Duration (s)").fill("60");
  await page.getByLabel("Warmup (s)").fill("15");
  await page.getByLabel("Seed").fill("77");
  await page.getByLabel("Disturbance").selectOption("construction");
  await page.getByRole("button", { name: "Start quick demo" }).click();
  await expect.poll(() => startPayloads.length).toBe(1);
  expect(startPayloads[0]).toMatchObject({
    flow_multiplier: 1.5,
    seed: 77,
    duration_seconds: 60,
    warmup_seconds: 15,
    disturbance: {
      kind: "construction",
      begin_seconds: 15,
      end_seconds: 60,
      target: "lane-1",
      intensity: 0.5,
    },
  });
});

test("one-click judge sequence runs fixed time then capacity-aware control", async ({ page }) => {
  const { startPayloads } = await mockJudgeApi(page);
  await page.unroute("**/api/runs");
  await page.route("**/api/runs", async (route) => {
    const body = route.request().postDataJSON();
    startPayloads.push(body);
    const runId = body.algorithm === "fixed_time" ? "run-fixed" : "run-capacity";
    await route.fulfill({
      status: 202,
      json: { run_id: runId, status: "queued", reason: "", run_dir: "hidden", summary: null, algorithm: body.algorithm },
    });
  });
  await page.route("**/api/runs/run-*/frame**", (route) => route.fulfill({ status: 404, json: { detail: "frame unavailable" } }));
  await page.addInitScript(() => {
    class MockSocket extends EventTarget {
      readyState = 1;
      readonly runId: string;

      constructor(url: string) {
        super();
        this.runId = url.includes("run-capacity") ? "run-capacity" : "run-fixed";
        window.setTimeout(() => this.dispatchEvent(new Event("open")), 0);
        window.setTimeout(() => this.dispatchEvent(new MessageEvent("message", {
          data: JSON.stringify({ run_id: this.runId, type: "status", status: "completed" }),
        })), 40);
      }

      close() {
        this.readyState = 3;
        window.setTimeout(() => this.dispatchEvent(new CloseEvent("close")), 0);
      }
    }
    Object.defineProperty(window, "WebSocket", { configurable: true, value: MockSocket });
  });

  await page.goto("/");
  await page.getByRole("button", { name: "Run judge sequence" }).click();
  await expect.poll(() => startPayloads.map((payload) => payload.algorithm)).toEqual([
    "fixed_time",
    "capacity_aware_maxpressure",
  ]);
  await expect(page.getByRole("heading", { name: "Comparison" })).toBeVisible();
});

test("stale frame responses never replace the accepted sequence", async ({ page }) => {
  await mockJudgeApi(page);
  await page.goto("/");
  await page.getByRole("button", { name: "Start quick demo" }).click();
  await expect(page.getByTestId("frame-sequence")).toContainText("2");
  await expect(page.getByTestId("frame-sequence")).not.toContainText("1");
});

test("frame polling recovers when the first frame is not ready", async ({ page }) => {
  await mockJudgeApi(page);
  await page.unroute("**/api/runs/run-quick/frame**");
  let requests = 0;
  await page.route("**/api/runs/run-quick/frame**", (route) => {
    requests += 1;
    if (requests === 1) return route.fulfill({ status: 404, json: { detail: "frame unavailable" } });
    return route.fulfill({
      status: 200,
      contentType: "image/png",
      headers: {
        "X-Run-Id": "run-quick",
        "X-Frame-Sequence": "2",
        "X-Simulation-Time": "2",
      },
      body: PNG,
    });
  });

  await page.goto("/");
  await page.getByRole("button", { name: "Start quick demo" }).click();
  await expect(page.getByTestId("frame-sequence")).toContainText("Sequence 2");
  expect(requests).toBeGreaterThan(1);
});

test("terminal websocket cleanup remains idle", async ({ page }) => {
  await mockJudgeApi(page);
  let resultRequests = 0;
  await page.unroute("**/api/results");
  await page.route("**/api/results", (route) => {
    resultRequests += 1;
    return route.fulfill({ status: 200, json: { items: [], count: 0 } });
  });
  await page.addInitScript(() => {
    class MockSocket extends EventTarget {
      readyState = 1;

      constructor() {
        super();
        window.setTimeout(() => this.dispatchEvent(new Event("open")), 0);
        window.setTimeout(() => this.dispatchEvent(new MessageEvent("message", {
          data: JSON.stringify({ run_id: "run-quick", type: "status", status: "completed" }),
        })), 40);
      }

      close() {
        this.readyState = 3;
        window.setTimeout(() => this.dispatchEvent(new CloseEvent("close")), 0);
      }
    }
    Object.defineProperty(window, "WebSocket", { configurable: true, value: MockSocket });
  });

  await page.goto("/");
  await expect.poll(() => resultRequests).toBeGreaterThan(0);
  const initialResultRequests = resultRequests;
  await page.getByRole("button", { name: "Start quick demo" }).click();
  await expect(page.getByText("Status: completed")).toBeVisible();
  await expect(page.getByText("Connection: idle")).toBeVisible();
  await expect.poll(() => resultRequests).toBeGreaterThan(initialResultRequests);
});

test("unexpected websocket closure exposes a reconnect action", async ({ page }) => {
  await mockJudgeApi(page);
  await page.addInitScript(() => {
    let socketCount = 0;
    class MockSocket extends EventTarget {
      readyState = 1;
      readonly isRunSocket: boolean;

      constructor(url: string) {
        super();
        this.isRunSocket = url.includes("/api/runs/");
        if (this.isRunSocket) socketCount += 1;
        window.setTimeout(() => this.dispatchEvent(new Event("open")), 0);
        if (this.isRunSocket && socketCount === 1) window.setTimeout(() => this.dispatchEvent(new CloseEvent("close")), 40);
      }

      close() {
        this.readyState = 3;
        window.setTimeout(() => this.dispatchEvent(new CloseEvent("close")), 0);
      }
    }
    Object.defineProperty(window, "WebSocket", { configurable: true, value: MockSocket });
    Object.defineProperty(window, "__socketCount", { configurable: true, get: () => socketCount });
  });

  await page.goto("/");
  await page.getByRole("button", { name: "Start quick demo" }).click();
  await expect(page.getByRole("alert")).toContainText("Realtime connection closed");
  await page.getByRole("button", { name: "Reconnect events" }).click();
  await expect(page.getByText("Connection: connected")).toBeVisible();
  await expect.poll(() => page.evaluate(() => (window as unknown as { __socketCount: number }).__socketCount)).toBe(2);
});

test("stale websocket callbacks cannot disconnect a successful reconnect", async ({ page }) => {
  await mockJudgeApi(page);
  await page.addInitScript(() => {
    let socketCount = 0;
    class MockSocket extends EventTarget {
      readyState = 1;
      readonly socketNumber: number;
      readonly isRunSocket: boolean;

      constructor(url: string) {
        super();
        this.isRunSocket = url.includes("/api/runs/");
        if (this.isRunSocket) socketCount += 1;
        this.socketNumber = this.isRunSocket ? socketCount : 0;
        window.setTimeout(() => this.dispatchEvent(new Event("open")), 0);
        if (this.socketNumber === 1) {
          window.setTimeout(() => this.dispatchEvent(new CloseEvent("close")), 40);
          window.setTimeout(() => this.dispatchEvent(new Event("error")), 180);
        }
      }

      close() {
        this.readyState = 3;
      }
    }
    Object.defineProperty(window, "WebSocket", { configurable: true, value: MockSocket });
  });

  await page.goto("/");
  await page.getByRole("button", { name: "Start quick demo" }).click();
  await expect(page.getByRole("alert")).toContainText("Realtime connection closed");
  await page.getByRole("button", { name: "Reconnect events" }).click();
  await expect(page.getByText("Connection: connected")).toBeVisible();
  await page.waitForTimeout(250);
  await expect(page.getByText("Connection: connected")).toBeVisible();
  await expect(page.getByRole("alert")).toHaveCount(0);
});

test("runtime metrics expose the actual current signal phase", async ({ page }) => {
  await mockJudgeApi(page);
  await page.addInitScript(() => {
    class MockSocket extends EventTarget {
      readyState = 1;

      constructor() {
        super();
        window.setTimeout(() => this.dispatchEvent(new Event("open")), 0);
        window.setTimeout(() => this.dispatchEvent(new MessageEvent("message", {
          data: JSON.stringify({
            run_id: "run-quick",
            type: "metrics",
            metrics: { current_phase: 2, current_phase_name: "east-west green", elapsed_phase_time: 8 },
          }),
        })), 30);
      }

      close() {
        this.readyState = 3;
      }
    }
    Object.defineProperty(window, "WebSocket", { configurable: true, value: MockSocket });
  });

  await page.goto("/");
  await page.getByRole("button", { name: "Start quick demo" }).click();
  await expect(page.getByText("Phase: east-west green · 8 s")).toBeVisible();
});

test("late websocket events cannot mutate a replacement run", async ({ page }) => {
  await mockJudgeApi(page);
  let startCount = 0;
  await page.unroute("**/api/runs");
  await page.route("**/api/runs", (route) => {
    startCount += 1;
    return route.fulfill({
      status: 202,
      json: {
        run_id: `run-${startCount}`,
        status: "queued",
        reason: "",
        run_dir: "hidden",
        summary: null,
        algorithm: "fixed_time",
      },
    });
  });
  await page.route("**/api/runs/run-1/stop", (route) => route.fulfill({
    status: 200,
    json: { run_id: "run-1", status: "stopped", reason: "judge requested stop", run_dir: "hidden", summary: null, algorithm: "fixed_time" },
  }));
  await page.route("**/api/runs/run-*/frame**", (route) => route.fulfill({ status: 404, json: { detail: "frame unavailable" } }));
  await page.addInitScript(() => {
    let sockets = 0;
    class MockSocket extends EventTarget {
      readyState = 1;
      readonly socketNumber: number;
      readonly isRunSocket: boolean;

      constructor(url: string) {
        super();
        this.isRunSocket = url.includes("/api/runs/");
        if (this.isRunSocket) sockets += 1;
        this.socketNumber = this.isRunSocket ? sockets : 0;
        window.setTimeout(() => this.dispatchEvent(new Event("open")), 0);
        if (this.isRunSocket && this.socketNumber === 1) {
          window.setTimeout(() => this.dispatchEvent(new MessageEvent("message", {
            data: JSON.stringify({ run_id: "run-1", type: "status", status: "failed" }),
          })), 250);
        }
      }

      close() {
        this.readyState = 3;
        window.setTimeout(() => this.dispatchEvent(new CloseEvent("close")), 0);
      }
    }
    Object.defineProperty(window, "WebSocket", { configurable: true, value: MockSocket });
  });

  await page.goto("/");
  await page.getByRole("button", { name: "Start quick demo" }).click();
  await expect(page.getByText("Status: queued")).toBeVisible();
  await page.getByRole("button", { name: "Stop run" }).click();
  await expect(page.getByText("Status: stopped")).toBeVisible();
  await page.getByRole("button", { name: "Start quick demo" }).click();
  await expect(page.getByText("Status: queued")).toBeVisible();
  await page.waitForTimeout(350);
  await expect(page.getByText("Status: queued")).toBeVisible();
  expect(startCount).toBe(2);
});

test("simulation exposes stop, frame metadata, and native GUI errors", async ({ page }) => {
  await mockJudgeApi(page);
  let stopCalled = false;
  await page.route("**/api/runs/run-quick/stop", async (route) => {
    stopCalled = true;
    await route.fulfill({
      status: 200,
      json: {
        run_id: "run-quick",
        status: "interrupted",
        reason: "judge requested stop",
        run_dir: "hidden",
        summary: null,
        algorithm: "fixed_time",
      },
    });
  });
  await page.route("**/api/runs/run-quick/native-gui", (route) =>
    route.fulfill({ status: 409, json: { detail: "display unavailable" } }),
  );

  await page.goto("/");
  await page.getByRole("button", { name: "Start quick demo" }).click();
  await expect(page.getByTestId("frame-sequence")).toContainText("Sequence 2");
  await expect(page.getByTestId("simulation-time")).toContainText("Simulation time 2 s");
  await page.getByRole("button", { name: "Show native SUMO GUI" }).click();
  await expect(page.getByRole("alert")).toContainText("display unavailable");
  await page.getByRole("button", { name: "Stop run" }).click();
  await expect.poll(() => stopCalled).toBe(true);
  await expect(page.getByText("interrupted")).toBeVisible();
});

test("judge can inspect sealed run comparison, history, and scene provenance", async ({ page }) => {
  await mockJudgeApi(page);
  await page.goto("/");
  await page.getByRole("button", { name: "Comparison" }).click();
  await expect(page.getByRole("heading", { name: "Comparison" })).toBeVisible();
  await expect(page.getByLabel("Comparison scene")).toHaveValue("1");
  await expect(page.getByTestId("comparison-chart")).toBeVisible();
  await expect(page.getByRole("region", { name: "Sealed run result comparison" })).toBeVisible();
  await expect(page.locator(".recharts-wrapper").first()).toBeVisible();
  await expect(page.getByText("Unavailable")).toBeVisible();
  await expect(page.getByText("formal-1")).toBeVisible();
  await expect(page.getByText("formal-2")).not.toBeVisible();
  await expect(page.getByRole("heading", { name: "Fuel ml" })).toBeVisible();
  await expect(page.getByRole("heading", { name: "CO2 g" })).toBeVisible();
  await expect(page.getByText("Hard safety gates: collisions, red-light violations, and illegal transitions.")).toBeVisible();
  await expect(page.getByText("Observational safety: harsh braking, teleports, and potential conflicts.")).toBeVisible();
  const formalRow = page.getByRole("row").filter({ hasText: "source: formal-1" });
  const safetyCells = formalRow.getByRole("cell");
  await expect(safetyCells.nth(6)).toHaveText("1");
  await expect(safetyCells.nth(7)).toHaveText("2");
  await expect(safetyCells.nth(8)).toHaveText("3");
  await expect(safetyCells.nth(9)).toHaveText("4");
  await expect(safetyCells.nth(10)).toHaveText("5");
  await expect(safetyCells.nth(11)).toHaveText("6");
  await expect(page.getByText("Formal 95% CI has not yet been generated; it awaits Task 22's complete sealed 540-run matrix.")).toBeVisible();
  await page.getByLabel("Comparison scene").selectOption("2");
  await expect(page.getByText("formal-2")).toBeVisible();
  await expect(page.getByText("formal-1")).not.toBeVisible();

  await page.getByRole("button", { name: "History" }).click();
  await expect(page.getByText("formal-1")).toBeVisible();
  await expect(page.getByText("Sealed run evidence")).toBeVisible();
  await expect(page.getByText("Scene 1").first()).toBeVisible();
  await expect(page.getByText("hidden")).not.toBeVisible();
  await page.getByRole("button", { name: "Open sealed summary" }).first().click();
  await expect(page.getByLabel("Sealed result detail")).toContainText('"scene_id": "1"');

  await page.getByRole("button", { name: "Scene" }).click();
  await expect(page.getByText("Test intersection")).toBeVisible();
  await expect(page.getByText("pass", { exact: true })).toBeVisible();
  await expect(page.getByText("scene.net.xml")).toBeVisible();
  await expect(page.getByText("data/intersection_data", { exact: true })).not.toBeVisible();
  await expect(page.getByText("fixture warning")).toBeVisible();
});

test("failed scene manifests are never labeled as verified", async ({ page }) => {
  await mockJudgeApi(page);
  await page.unroute("**/api/scenes");
  await page.route("**/api/scenes", (route) => route.fulfill({ json: [{ ...scene, validation_status: "fail" }] }));
  await page.goto("/");
  await page.getByRole("button", { name: "Scene" }).click();
  await expect(page.getByText("Review manifest status")).toBeVisible();
  await expect(page.getByText("All manifests pass")).not.toBeVisible();
});

test("judge console remains usable on a narrow viewport", async ({ page }) => {
  await mockJudgeApi(page);
  await page.setViewportSize({ width: 390, height: 844 });
  await page.goto("/");
  await page.keyboard.press("Tab");
  await expect(page.getByRole("button", { name: "Simulation" })).toBeFocused();
  await expect(page.getByRole("button", { name: "Start quick demo" })).toBeVisible();
  const before = await page.locator(".sumo-frame__stage").boundingBox();
  await page.getByRole("button", { name: "Start quick demo" }).click();
  const after = await page.locator(".sumo-frame__stage").boundingBox();
  expect(before).not.toBeNull();
  expect(after).not.toBeNull();
  expect(after?.width).toBe(before?.width);
  expect(await page.evaluate(() => document.documentElement.scrollWidth <= document.documentElement.clientWidth)).toBe(true);
  for (const view of ["Comparison", "History", "Scene"]) {
    await page.getByRole("button", { name: view }).click();
    expect(await page.evaluate(() => document.documentElement.scrollWidth <= document.documentElement.clientWidth)).toBe(true);
  }
});
