import { expect, test, type Page } from "@playwright/test";

const scene = {
  scene_id: "1",
  intersection_id: "1",
  name: "Test intersection",
  description: "fixture",
  source_files: { net: "scene.net.xml" },
  sha256: { net: "a".repeat(64) },
  step_length: 1,
  tls_ids: ["tls-1"],
  lane_ids: ["lane-1"],
  movement_count: 1,
  validation_status: "pass",
  warnings: [],
};

async function mockJudgeApi(page: Page) {
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
        ],
        optional: [],
      },
    }),
  );
  await page.route("**/api/runs", async (route) => {
    expect(route.request().method()).toBe("POST");
    const body = route.request().postDataJSON();
    expect(body).toMatchObject({
      intersection_id: "1",
      algorithm: "fixed_time",
      flow_multiplier: 1,
      seed: 42,
      duration_seconds: 30,
    });
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
      body: Buffer.from("png"),
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
}

test("judge can navigate the demo and see a real frame placeholder", async ({ page }) => {
  await mockJudgeApi(page);
  await page.goto("/");
  await page.goto("/");
  await expect(page.getByRole("navigation")).toContainText("Simulation");
  await page.getByRole("button", { name: "Start quick demo" }).click();
  await expect(page.getByRole("img", { name: "SUMO simulation frame" })).toHaveAttribute(
    "src",
    /data:image|\/api\/runs\/|blob:/,
  );
  await expect(page.getByText("Quick demo output")).toBeVisible();
  await expect(page.getByText("Formal evidence")).toBeVisible();
});

test("stale frame responses never replace the accepted sequence", async ({ page }) => {
  await mockJudgeApi(page);
  await page.goto("/");
  await page.getByRole("button", { name: "Start quick demo" }).click();
  await expect(page.getByTestId("frame-sequence")).toContainText("2");
  await expect(page.getByTestId("frame-sequence")).not.toContainText("1");
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
