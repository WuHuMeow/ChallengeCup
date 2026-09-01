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
  const guiDelayPayloads: Record<string, unknown>[] = [];
  const frameRequests = { count: 0 };
  const nativeGuiRequests: string[] = [];
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
    frameRequests.count += 1;
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
  await page.route("**/api/runs/run-quick/gui-delay", async (route) => {
    expect(route.request().method()).toBe("PUT");
    const body = route.request().postDataJSON();
    guiDelayPayloads.push(body);
    await new Promise((resolve) => setTimeout(resolve, 80));
    await route.fulfill({ status: 200, json: body });
  });
  await page.route("**/api/runs/run-quick/native-gui", async (route) => {
    expect(route.request().method()).toBe("POST");
    nativeGuiRequests.push("run-quick");
    await route.fulfill({ status: 200, json: { status: "shown" } });
  });
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
  return { startPayloads, guiDelayPayloads, frameRequests, nativeGuiRequests };
}

test("judge can configure a quick demo without the legacy browser viewers", async ({ page }) => {
  const { startPayloads, frameRequests } = await mockJudgeApi(page);
  await page.goto("/");
  await expect(page.locator("html")).toHaveAttribute("lang", "zh-CN");
  await expect(page).toHaveTitle("交通信号控制仿真评审台");
  await expect(page.getByRole("navigation", { name: "主导航" })).toContainText("实时仿真");
  await expect(page.getByRole("img", { name: "SUMO 仿真画面" })).toHaveCount(0);
  await expect(page.getByRole("button", { name: "运行评审序列" })).toHaveCount(0);
  await expect(page.getByRole("group", { name: "仿真步长（秒）" })).toBeVisible();
  await page.getByRole("button", { name: "自定义步长" }).click();
  await page.getByLabel("自定义仿真步长（秒）").fill("0.25");

  await page.getByRole("button", { name: "开始快速演示" }).click();

  await expect.poll(() => startPayloads.length).toBe(1);
  await page.waitForTimeout(200);
  expect(frameRequests.count).toBe(0);
  await expect(page.getByText("快速演示输出")).toBeVisible();
  await expect(page.getByText("仅展示由证据接口验证的单次运行封存结果；正式矩阵结论需等待任务 22 完成。")).toBeVisible();
  await expect(page.getByRole("region", { name: "安全计数" })).toContainText(/碰撞\s*0/);
  await expect(page.getByLabel("仿真时长（秒）")).toHaveValue("300");
  await expect(page.getByTestId("simulation-progress")).toContainText("仿真进度：0/1200 步（0/300 秒）");
  expect(startPayloads[0]).toMatchObject({
    intersection_id: "1",
    algorithm: "fixed_time",
    flow_multiplier: 1,
    seed: 42,
    duration_seconds: 300,
    warmup_seconds: 0,
    gui_delay_ms: 100,
    step_length_override: 0.25,
    disturbance: null,
  });
});

test("quick demo retries until the native SUMO window is ready", async ({ page }) => {
  await mockJudgeApi(page);
  await page.unroute("**/api/runs/run-quick/native-gui");
  let attempts = 0;
  await page.route("**/api/runs/run-quick/native-gui", async (route) => {
    attempts += 1;
    if (attempts === 1) {
      await route.fulfill({ status: 409, json: { detail: "SUMO process is not ready" } });
      return;
    }
    await route.fulfill({ status: 200, json: { status: "shown" } });
  });
  await page.addInitScript(() => {
    class MockSocket extends EventTarget {
      readyState = 1;

      constructor() {
        super();
        window.setTimeout(() => this.dispatchEvent(new Event("open")), 0);
        window.setTimeout(() => this.dispatchEvent(new MessageEvent("message", {
          data: JSON.stringify({ run_id: "run-quick", type: "status", status: "running" }),
        })), 20);
      }

      close() {
        this.readyState = 3;
      }
    }
    Object.defineProperty(window, "WebSocket", { configurable: true, value: MockSocket });
  });

  await page.goto("/");
  await page.getByRole("button", { name: "开始快速演示" }).click();
  await expect.poll(() => attempts).toBe(2);
  await expect(page.getByRole("alert")).toHaveCount(0);
});

test("judge can change the SUMO GUI delay while a run is active", async ({ page }) => {
  const { guiDelayPayloads } = await mockJudgeApi(page);
  await page.addInitScript(() => {
    class MockSocket extends EventTarget {
      readyState = 1;

      constructor() {
        super();
        window.setTimeout(() => this.dispatchEvent(new Event("open")), 0);
        window.setTimeout(() => this.dispatchEvent(new MessageEvent("message", {
          data: JSON.stringify({ run_id: "run-quick", type: "status", status: "running" }),
        })), 20);
      }

      close() {
        this.readyState = 3;
      }
    }
    Object.defineProperty(window, "WebSocket", { configurable: true, value: MockSocket });
  });

  await page.goto("/");
  const delayInput = page.getByLabel("GUI 步进延迟（毫秒）");
  await expect(delayInput).toHaveValue("100");
  await page.getByRole("button", { name: "开始快速演示" }).click();
  await expect(page.getByText("状态：运行中")).toBeVisible();

  await page.getByRole("button", { name: "延迟增加 50 毫秒" }).click();
  await expect(delayInput).toHaveValue("100");
  await expect.poll(() => guiDelayPayloads).toEqual([{ delay_ms: 150 }]);
  await expect(delayInput).toHaveValue("150");

  await page.getByRole("button", { name: "最快 0 毫秒" }).click();
  await expect.poll(() => guiDelayPayloads).toEqual([
    { delay_ms: 150 },
    { delay_ms: 0 },
  ]);
  await expect(delayInput).toHaveValue("0");
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
      gui_delay_ms: 100,
      disturbance: null,
    });
    return Object.prototype.hasOwnProperty.call(result, "run_dir");
  });
  expect(retainsRunDir).toBe(false);
});

test("selected run parameters are sent to the judge API", async ({ page }) => {
  const { startPayloads } = await mockJudgeApi(page);
  await page.goto("/");
  await page.getByLabel("流量倍率").fill("1.5");
  await page.getByLabel("仿真时长（秒）").fill("60");
  await page.getByLabel("预热时长（秒）").fill("15");
  await page.getByLabel("随机种子").fill("77");
  await page.getByLabel("扰动设置").selectOption("construction");
  await page.getByRole("button", { name: "开始快速演示" }).click();
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

test("run progress uses the selected simulation step length", async ({ page }) => {
  await mockJudgeApi(page);
  await page.addInitScript(() => {
    class MockSocket extends EventTarget {
      readyState = 1;

      constructor() {
        super();
        window.setTimeout(() => this.dispatchEvent(new Event("open")), 0);
        window.setTimeout(() => this.dispatchEvent(new MessageEvent("message", {
          data: JSON.stringify({ run_id: "run-quick", type: "metrics", simulation_time: 30, metrics: {} }),
        })), 30);
        window.setTimeout(() => this.dispatchEvent(new MessageEvent("message", {
          data: JSON.stringify({ run_id: "run-quick", type: "status", status: "completed", simulation_time: 30 }),
        })), 60);
      }

      close() {
        this.readyState = 3;
        window.setTimeout(() => this.dispatchEvent(new CloseEvent("close")), 0);
      }
    }
    Object.defineProperty(window, "WebSocket", { configurable: true, value: MockSocket });
  });

  await page.goto("/");
  await page.getByLabel("仿真时长（秒）").fill("30");
  await page.getByRole("button", { name: "0.5 秒步长" }).click();
  await page.getByRole("button", { name: "开始快速演示" }).click();

  await expect(page.getByTestId("simulation-progress")).toContainText("仿真进度：60/60 步（30/30 秒）");
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
  await page.getByRole("button", { name: "开始快速演示" }).click();
  await expect(page.getByText("状态：已完成")).toBeVisible();
  await expect(page.getByText("连接：空闲")).toBeVisible();
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
  await page.getByRole("button", { name: "开始快速演示" }).click();
  await expect(page.getByRole("alert")).toContainText("实时连接已关闭");
  await page.getByRole("button", { name: "重新连接事件流" }).click();
  await expect(page.getByText("连接：已连接")).toBeVisible();
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
  await page.getByRole("button", { name: "开始快速演示" }).click();
  await expect(page.getByRole("alert")).toContainText("实时连接已关闭");
  await page.getByRole("button", { name: "重新连接事件流" }).click();
  await expect(page.getByText("连接：已连接")).toBeVisible();
  await page.waitForTimeout(250);
  await expect(page.getByText("连接：已连接")).toBeVisible();
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
  await page.getByRole("button", { name: "开始快速演示" }).click();
  await expect(page.getByText("信号阶段：east-west green · 8 秒")).toBeVisible();
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
  await page.getByRole("button", { name: "开始快速演示" }).click();
  await expect(page.getByText("状态：排队中")).toBeVisible();
  await page.getByRole("button", { name: "停止运行" }).click();
  await expect(page.getByText("状态：已停止")).toBeVisible();
  await page.getByRole("button", { name: "开始快速演示" }).click();
  await expect(page.getByText("状态：排队中")).toBeVisible();
  await page.waitForTimeout(350);
  await expect(page.getByText("状态：排队中")).toBeVisible();
  expect(startCount).toBe(2);
});

test("simulation exposes stop and native GUI errors", async ({ page }) => {
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
  await page.getByRole("button", { name: "开始快速演示" }).click();
  await page.getByRole("button", { name: "显示原生 SUMO 界面" }).click();
  await expect(page.getByRole("alert")).toContainText("显示环境不可用");
  await page.getByRole("button", { name: "停止运行" }).click();
  await expect.poll(() => stopCalled).toBe(true);
  await expect(page.getByText("状态：已中断")).toBeVisible();
});

test("judge can inspect sealed run comparison, history, and scene provenance", async ({ page }) => {
  await mockJudgeApi(page);
  await page.goto("/");
  await page.getByRole("button", { name: "算法对比" }).click();
  await expect(page.getByRole("heading", { name: "算法对比" })).toBeVisible();
  await expect(page.getByLabel("对比场景")).toHaveValue("1");
  await expect(page.getByTestId("comparison-chart")).toBeVisible();
  await expect(page.getByRole("region", { name: "封存运行结果对比" })).toBeVisible();
  await expect(page.locator(".recharts-wrapper").first()).toBeVisible();
  await expect(page.getByText("不可用")).toBeVisible();
  await expect(page.getByText("formal-1")).toBeVisible();
  await expect(page.getByText("formal-2")).not.toBeVisible();
  await expect(page.getByRole("heading", { name: "燃油消耗 毫升" })).toBeVisible();
  await expect(page.getByRole("heading", { name: "二氧化碳排放 克" })).toBeVisible();
  await expect(page.getByText("硬性安全门槛：碰撞、闯红灯和非法相位切换。")).toBeVisible();
  await expect(page.getByText("观测性安全指标：急刹车、车辆传送和潜在冲突。")).toBeVisible();
  const formalRow = page.getByRole("row").filter({ hasText: "来源：formal-1" });
  const safetyCells = formalRow.getByRole("cell");
  await expect(safetyCells.nth(6)).toHaveText("1");
  await expect(safetyCells.nth(7)).toHaveText("2");
  await expect(safetyCells.nth(8)).toHaveText("3");
  await expect(safetyCells.nth(9)).toHaveText("4");
  await expect(safetyCells.nth(10)).toHaveText("5");
  await expect(safetyCells.nth(11)).toHaveText("6");
  await expect(page.getByText("正式的 95% 置信区间尚未生成，需等待任务 22 完成并封存 540 次运行矩阵。")).toBeVisible();
  await page.getByLabel("对比场景").selectOption("2");
  await expect(page.getByText("formal-2")).toBeVisible();
  await expect(page.getByText("formal-1")).not.toBeVisible();

  await page.getByRole("button", { name: "运行历史" }).click();
  await expect(page.getByText("formal-1")).toBeVisible();
  await expect(page.getByText("封存运行证据")).toBeVisible();
  await expect(page.getByText("场景 1").first()).toBeVisible();
  await expect(page.getByText("hidden")).not.toBeVisible();
  await page.getByRole("button", { name: "打开封存摘要" }).first().click();
  await expect(page.getByLabel("封存结果详情")).toContainText('"scene_id": "1"');

  await page.getByRole("button", { name: "场景清单" }).click();
  await expect(page.getByText("Test intersection")).toBeVisible();
  await expect(page.getByText("通过", { exact: true })).toBeVisible();
  await expect(page.getByText("scene.net.xml")).toBeVisible();
  await expect(page.getByText("data/intersection_data", { exact: true })).not.toBeVisible();
  await expect(page.getByText("fixture warning")).toBeVisible();
});

test("failed scene manifests are never labeled as verified", async ({ page }) => {
  await mockJudgeApi(page);
  await page.unroute("**/api/scenes");
  await page.route("**/api/scenes", (route) => route.fulfill({ json: [{ ...scene, validation_status: "fail" }] }));
  await page.goto("/");
  await page.getByRole("button", { name: "场景清单" }).click();
  await expect(page.getByText("请检查清单状态")).toBeVisible();
  await expect(page.getByText("所有清单均已通过")).not.toBeVisible();
});

test("judge console remains usable on a narrow viewport", async ({ page }) => {
  await mockJudgeApi(page);
  await page.setViewportSize({ width: 390, height: 844 });
  await page.goto("/");
  await page.keyboard.press("Tab");
  await expect(page.getByRole("button", { name: "实时仿真" })).toBeFocused();
  await expect(page.getByRole("button", { name: "开始快速演示" })).toBeVisible();
  const before = await page.locator(".simulation-grid").boundingBox();
  await page.getByRole("button", { name: "开始快速演示" }).click();
  const after = await page.locator(".simulation-grid").boundingBox();
  expect(before).not.toBeNull();
  expect(after).not.toBeNull();
  expect(after?.width).toBe(before?.width);
  expect(await page.evaluate(() => document.documentElement.scrollWidth <= document.documentElement.clientWidth)).toBe(true);
  for (const view of ["算法对比", "运行历史", "场景清单"]) {
    await page.getByRole("button", { name: view }).click();
    expect(await page.evaluate(() => document.documentElement.scrollWidth <= document.documentElement.clientWidth)).toBe(true);
  }
});
