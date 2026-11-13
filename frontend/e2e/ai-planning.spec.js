const { test, expect } = require("@playwright/test");

async function createWorkspace(page) {
  const email = `ai-e2e-${Date.now()}-${Math.random().toString(36).slice(2)}@example.com`;
  const password = "TaskBoard-E2E-2026";
  await page.goto("/register/");
  await page.locator("#id_email").fill(email);
  await page.locator("#id_password").fill(password);
  await page.locator(".auth-submit").click();
  await expect(page).toHaveURL(/\/login\/$/);
  await page.locator("#id_email").fill(email);
  await page.locator("#id_password").fill(password);
  await page.locator(".auth-submit").click();
  await expect(page).toHaveURL("/");
  await page.goto("/boards/new/");
  await page.locator("#id_name").fill("AI test workspace");
  await page
    .getByRole("button", { name: "Utwórz tablicę", exact: true })
    .click();
  await page.locator(".board-card").click();
  const boardPath = new URL(page.url()).pathname;
  await page.locator(".ai-launchpad").click();
  await expect(page.locator("[data-ai-generate]")).toBeVisible();
  return { boardPath, email, password };
}

async function generatePlan(page) {
  await page
    .locator("#id_goal")
    .fill("Przygotować stronę portfolio z projektami w Pythonie.");
  await page.locator("#id_min_elements").fill("3");
  await page.locator("#id_max_elements").fill("5");
  await page.locator(".ai-generate-button").click();
  await expect(page.locator("[data-ai-suggestion]")).toHaveCount(5);
}

test("generated tasks require review, retain edits and save only selected titles", async ({
  page,
  request,
}) => {
  const { boardPath, email, password } = await createWorkspace(page);
  await page.getByRole("button", { name: "Portfolio", exact: true }).click();
  await expect(page.locator("#id_goal")).toHaveValue(/portfolio/);
  await generatePlan(page);
  await expect(page.locator(".ai-demo-note")).toContainText(
    "bez użycia modelu AI",
  );
  const login = await request.post("http://127.0.0.1:18180/users/login", {
    data: { email, password },
  });
  const token = (await login.json()).access_token;
  const apiURL = `http://127.0.0.1:18180${boardPath}tasks`;
  const before = await request.get(apiURL, {
    headers: { Authorization: `Bearer ${token}` },
  });
  expect(await before.json()).toEqual([]);
  await page
    .locator("#id_form-0-title")
    .fill("Moje dopracowane zadanie z planu AI");
  await page.locator("#id_form-1-DELETE").check();
  await expect(page.locator("[data-ai-selected-count]")).toHaveText("4");
  await expect(page.locator("[data-ai-suggestion]").nth(1)).toHaveClass(
    /is-skipped/,
  );
  await page.locator("[data-ai-save]").click();
  await expect(page).toHaveURL(boardPath);
  await expect(page.locator("article.task-row")).toHaveCount(4);
  await expect(page.locator(".task-title").first()).toHaveText(
    "Moje dopracowane zadanie z planu AI",
  );
  const after = await request.get(apiURL, {
    headers: { Authorization: `Bearer ${token}` },
  });
  expect((await after.json()).length).toBe(4);
});

test("generation exposes its waiting state and blocks duplicate submissions", async ({
  page,
}) => {
  await createWorkspace(page);
  let releaseResponse;
  const responseGate = new Promise((resolve) => (releaseResponse = resolve));
  await page.route("**/boards/*/plan/", async (route) => {
    if (route.request().method() === "POST") {
      await responseGate;
    }
    await route.continue();
  });
  await page
    .locator("#id_goal")
    .fill("Zaplanować nową aplikację Django do portfolio.");
  try {
    const state = await page
      .locator(".ai-generate-button")
      .evaluate(async (button) => {
        button.form.requestSubmit(button);
        await new Promise((resolve) => setTimeout(resolve, 25));
        return {
          waiting: !document.querySelector("[data-ai-loading]").hidden,
          disabled: button.disabled,
          readOnly: document.getElementById("id_goal").readOnly,
        };
      });
    expect(state).toEqual({ waiting: true, disabled: true, readOnly: true });
  } finally {
    releaseResponse();
  }
  await expect(page.locator("[data-ai-suggestion]")).toHaveCount(5);
});

test("an empty selection shows feedback without adding tasks", async ({
  page,
}) => {
  await createWorkspace(page);
  await generatePlan(page);
  for (const checkbox of await page
    .locator('[data-ai-review] input[type="checkbox"]')
    .all()) {
    await checkbox.check();
  }
  await expect(page.locator("[data-ai-selected-count]")).toHaveText("0");
  await page.locator("[data-ai-save]").click();
  await expect(page.locator(".non-field-errors")).toContainText(
    "Pozostaw co najmniej jedno zadanie",
  );
  await expect(page.locator("[data-ai-suggestion]")).toHaveCount(5);
});

test("AI views fit mobile, tablet and desktop and respect reduced motion", async ({
  page,
}) => {
  await createWorkspace(page);
  const planPath = new URL(page.url()).pathname;
  await page.emulateMedia({ reducedMotion: "reduce" });
  for (const width of [320, 390, 768, 1024, 1440]) {
    await page.setViewportSize({ width, height: 900 });
    await page.goto(planPath);
    expect(
      await page.evaluate(
        () => document.documentElement.scrollWidth <= innerWidth,
      ),
    ).toBeTruthy();
    await expect(page.locator("h1")).toHaveCount(1);
    expect(
      await page
        .locator(".entrance")
        .evaluate((element) => getComputedStyle(element).animationName),
    ).toBe("none");
  }
  await generatePlan(page);
  for (const width of [320, 390, 768, 1024, 1440]) {
    await page.setViewportSize({ width, height: 900 });
    expect(
      await page.evaluate(
        () => document.documentElement.scrollWidth <= innerWidth,
      ),
    ).toBeTruthy();
    await expect(page.locator("[data-ai-save]")).toBeEnabled();
  }
});

test.describe("Without JavaScript", () => {
  test.use({ javaScriptEnabled: false });

  test("planning, editing, selection and saving remain usable", async ({
    page,
  }) => {
    const { boardPath } = await createWorkspace(page);
    await generatePlan(page);
    await page
      .locator("#id_form-0-title")
      .fill("Zadanie zapisane bez JavaScriptu");
    await page.locator("#id_form-1-DELETE").check();
    await page.locator("[data-ai-save]").click();
    await expect(page).toHaveURL(boardPath);
    await expect(page.locator("article.task-row")).toHaveCount(4);
    await expect(page.locator(".task-title").first()).toHaveText(
      "Zadanie zapisane bez JavaScriptu",
    );
  });
});
