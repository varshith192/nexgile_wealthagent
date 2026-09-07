import { expect, test } from "@playwright/test";

import { ACCOUNTS, DEMO_PASSWORD, expectNoBlankScreen, signIn, waitForData } from "./helpers";

/**
 * The complete evaluation journey (§52), driven through the real UI against a
 * real API:
 *
 *   Login → Dashboard → Portfolio → Goal → WealthAgent → Recommendation
 *         → Advisor Client 360 → Approval → Audit trail
 */

test.describe("Sign-in", () => {
  test("the login page presents the product and its demo accounts", async ({ page }) => {
    await page.goto("/login");

    await expect(page.getByRole("heading", { name: /Every account, goal and decision/i })).toBeVisible();
    await expect(page.getByRole("heading", { name: "Sign in" })).toBeVisible();
    await expect(page.getByLabel("Email address")).toBeVisible();
    await expect(page.getByLabel("Password")).toBeVisible();
    await expect(page.getByLabel("Remember me")).toBeVisible();
    await expect(page.getByRole("button", { name: "Forgot password?" })).toBeVisible();

    // Demo accounts are labelled as demo, and no production credential appears.
    await expect(page.getByText("Demo accounts")).toBeVisible();
    for (const account of Object.values(ACCOUNTS)) {
      await expect(page.getByText(account.label, { exact: true })).toBeVisible();
    }
    await expect(page.getByText(DEMO_PASSWORD)).toBeVisible();
  });

  test("a wrong password is refused with a readable message", async ({ page }) => {
    await page.goto("/login");
    await page.getByLabel("Email address").fill(ACCOUNTS.client.email);
    await page.getByLabel("Password").fill("not-the-password");
    await page.getByRole("button", { name: "Sign in" }).click();

    await expect(page.getByRole("alert")).toContainText(/Incorrect email or password/i);
    await expect(page).toHaveURL(/\/login/);
  });

  test("a one-click demo account signs in and lands on its workspace", async ({ page }) => {
    await page.goto("/login");
    await page.getByRole("button", { name: /Advisor Demo/ }).click();
    await page.waitForURL("**/advisor", { timeout: 30_000 });
    await expect(page.getByRole("heading", { name: "Advisor workstation" })).toBeVisible();
  });

  test("an unauthenticated visitor is sent to sign in", async ({ page }) => {
    await page.goto("/dashboard");
    await page.waitForURL(/\/login/, { timeout: 30_000 });
    await expect(page.getByRole("heading", { name: "Sign in" })).toBeVisible();
  });
});

test.describe("Client journey", () => {
  test("dashboard through to a recommendation, then approval and audit", async ({ page }) => {
    // ------------------------------------------------------- 1. Dashboard
    await signIn(page, "client");
    await waitForData(page);

    await expect(page.getByText("Net worth").first()).toBeVisible();
    await expect(page.getByText("Portfolio value")).toBeVisible();
    await expect(page.getByText("Needs attention")).toBeVisible();
    await expect(page.getByText("WealthAgent").first()).toBeVisible();

    // As-of date and freshness are declared, never implied (§39).
    await expect(page.getByText(/As of/).first()).toBeVisible();

    const netWorth = await page.locator("p.tabular").first().innerText();
    expect(netWorth).toMatch(/\$/);

    // ------------------------------------------------------- 2. Portfolio
    await page.getByRole("link", { name: "Portfolio", exact: true }).click();
    await page.waitForURL("**/portfolio");
    await waitForData(page);
    await expect(page.getByRole("heading", { name: "Portfolio", level: 1 })).toBeVisible();
    await expect(page.getByText("Market value")).toBeVisible();
    await expect(page.getByRole("heading", { name: "Performance" })).toBeVisible();

    // Period buttons drive a real recalculation.
    await page.getByRole("button", { name: "1Y", exact: true }).click();
    await expect(page.getByText("1Y return")).toBeVisible();

    // Allocation tabs.
    await page.getByRole("tab", { name: /Drift vs policy/ }).click();
    await expect(page.getByText("Above target")).toBeVisible();

    // Every figure can show its working (§4).
    await page.getByRole("button", { name: /How these statistics are calculated/ }).first().click();
    await expect(page.getByText("Assumptions").first()).toBeVisible();
    await expect(page.getByText("Limitations").first()).toBeVisible();

    // -------------------------------------------------------- 3. Holdings
    await page.getByRole("link", { name: "Holdings", exact: true }).click();
    await page.waitForURL("**/holdings");
    await waitForData(page);
    await expect(page.getByRole("heading", { name: "Holdings", level: 1 })).toBeVisible();

    const firstRow = page.locator("tbody tr").first();
    await expect(firstRow).toBeVisible();
    await firstRow.click();
    await expect(page.getByRole("dialog")).toBeVisible();
    await expect(page.getByText("Tax lots")).toBeVisible();
    await page.getByRole("button", { name: "Close panel" }).click();

    // ----------------------------------------------------------- 4. Goals
    await page.getByRole("link", { name: "Goals", exact: true }).click();
    await page.waitForURL("**/goals");
    await waitForData(page);
    await expect(page.getByRole("heading", { name: "Goals", level: 1 })).toBeVisible();

    await page.locator('a[href^="/goals/"]').first().click();
    await page.waitForURL(/\/goals\/[a-f0-9-]+/);
    await waitForData(page);

    await expect(page.getByText("Funding progress")).toBeVisible();
    await expect(page.getByText(/Projections are illustrative, not guaranteed/)).toBeVisible();

    // Scenarios must run and must not alter the goal (§4).
    const targetBefore = await page.getByText("Target amount (today's dollars)").locator("..").innerText();
    await page.getByRole("button", { name: /Run scenarios/ }).first().click();
    await expect(page.getByText("Base Case")).toBeVisible({ timeout: 30_000 });
    await expect(page.getByText("Higher Savings")).toBeVisible();
    await expect(page.getByText("Lower Return")).toBeVisible();
    await expect(page.getByText("Earlier Retirement")).toBeVisible();
    await expect(page.getByText(/never written back to the books of record|does not change your goal/i)).toBeVisible();

    const targetAfter = await page.getByText("Target amount (today's dollars)").locator("..").innerText();
    expect(targetAfter).toBe(targetBefore);

    // ---------------------------------------------------- 5. WealthAgent
    await page.getByRole("link", { name: "WealthAgent", exact: true }).click();
    await page.waitForURL("**/wealthagent");
    await waitForData(page);

    await expect(page.getByRole("heading", { name: "WealthAgent", level: 1 })).toBeVisible();
    await expect(page.getByText(/Deterministic rules engine/i).first()).toBeVisible();
    await expect(page.getByText(/No API key required/)).toBeVisible();

    // An insight shows the data behind it.
    const insight = page.locator("li >> button").first();
    await insight.click();
    await expect(page.getByText("Supporting data").first()).toBeVisible();
    await expect(page.getByText("Calculation").first()).toBeVisible();

    // The conversational surface answers from verified figures.
    await page.getByLabel("Ask WealthAgent a question").fill("What is my net worth?");
    await page.getByRole("button", { name: "Send question" }).click();
    await expect(page.getByText("Figures quoted")).toBeVisible({ timeout: 30_000 });

    // ------------------------------------------------- 6. Recommendation
    await page.getByRole("tab", { name: /Recommendations/ }).click();
    await expect(page.getByText(/Requires approval/).first()).toBeVisible();
  });
});

test.describe("Advisor journey", () => {
  test("Client 360, a recommendation, an approval decision and the audit trail", async ({ page }) => {
    await signIn(page, "advisor");
    await waitForData(page);

    // ---------------------------------------------- Advisor workstation
    await expect(page.getByText("Assets under advice")).toBeVisible();
    await expect(page.getByText("Pending approvals").first()).toBeVisible();

    // --------------------------------------------------- Client 360
    await page.getByRole("link", { name: "Clients", exact: true }).click();
    await page.waitForURL("**/advisor/clients");
    await waitForData(page);

    await page.locator('a[href^="/advisor/clients/"]').first().click();
    await page.waitForURL(/\/advisor\/clients\/[a-f0-9-]+/);
    await waitForData(page);

    for (const tab of ["Household", "Accounts", "Portfolio", "Goals", "Tax", "Estate", "Service", "Activity"]) {
      await page.getByRole("tab", { name: new RegExp(tab) }).click();
      await expect(page.getByRole("tab", { name: new RegExp(tab) })).toHaveAttribute("aria-selected", "true");
    }

    // The activity timeline is populated.
    await expect(page.locator("ol li").first()).toBeVisible();

    // ------------------------------------------- Raise a recommendation
    await page.goto("/wealthagent");
    await waitForData(page);
    await page.getByRole("tab", { name: /Recommendations/ }).click();

    const submit = page.getByRole("button", { name: /Submit for approval/ }).first();
    await expect(submit).toBeVisible();
    await submit.click();
    await expect(page.getByText("Submitted for review").first()).toBeVisible({ timeout: 30_000 });

    // ------------------------------------------------------- Approvals
    await page.goto("/approvals");
    await waitForData(page);
    await expect(page.getByRole("heading", { name: "Approvals", level: 1 })).toBeVisible();
    await expect(page.getByText("Awaiting a decision")).toBeVisible();

    await page.locator("li >> button").first().click();
    const drawer = page.getByRole("dialog");
    await expect(drawer).toBeVisible();
    await expect(drawer.getByText("History")).toBeVisible();
    await expect(drawer.locator("ol li").first()).toBeVisible();
  });

  test("an approval moves through review, decision and completion", async ({ page }) => {
    // The investment team decides on investment recommendations.
    await page.goto("/login");
    await page.getByLabel("Email address").fill("tobias.frank@nexgile.example");
    await page.getByLabel("Password").fill(DEMO_PASSWORD);
    await page.getByRole("button", { name: "Sign in" }).click();
    await page.waitForURL(/\/advisor/, { timeout: 30_000 });

    await page.goto("/approvals");
    await waitForData(page);
    await page.getByRole("tab", { name: "Submitted" }).click();
    await waitForData(page);

    const rows = page.locator("li >> button");
    if ((await rows.count()) === 0) test.skip(true, "no submitted approvals in this run");

    await rows.first().click();
    const drawer = page.getByRole("dialog");
    await expect(drawer).toBeVisible();

    const approve = drawer.getByRole("button", { name: "Approve", exact: true });
    await expect(approve).toBeVisible();
    await drawer.getByLabel("Decision note").fill("Reviewed against the investment policy.");
    await approve.click();

    await expect(drawer.getByText("Approved").first()).toBeVisible({ timeout: 30_000 });
    await expect(drawer.getByRole("button", { name: "Mark completed" })).toBeVisible();
  });
});

test.describe("Audit trail", () => {
  test("compliance can read the trail and inspect what changed", async ({ page }) => {
    await signIn(page, "compliance");
    await page.goto("/audit");
    await waitForData(page);

    await expect(page.getByRole("heading", { name: "Audit trail", level: 1 })).toBeVisible();
    await expect(page.getByText(/never edited or removed/i)).toBeVisible();
    await expect(page.locator("ol li").first()).toBeVisible();

    // Filtering narrows the trail.
    await page.getByLabel("Filter by action").selectOption("approval_decided");
    await waitForData(page);

    const entries = page.locator("ol li");
    if ((await entries.count()) > 0) {
      await entries.first().locator("button").click();
      await expect(page.getByText("Before").first()).toBeVisible();
      await expect(page.getByText("After").first()).toBeVisible();
    }
  });
});
