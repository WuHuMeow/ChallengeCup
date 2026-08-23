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
