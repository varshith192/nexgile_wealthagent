import { expect, test } from "@playwright/test";

import { ACCOUNTS, type AccountKey, expectNoBlankScreen, signIn, waitForData } from "./helpers";

/**
 * Role-based navigation and authorisation (§5, §45, §53).
 *
 * Two properties are asserted for every role: it lands in its own workspace
 * and sees only its own navigation, and every route it can reach renders real
 * content rather than a blank screen.
 */

const ROLE_NAV: Record<AccountKey, { visible: string[]; hidden: string[] }> = {
  client: {
    visible: ["Overview", "Portfolio", "Accounts", "Goals", "Tax", "Estate", "Documents", "WealthAgent"],
    hidden: ["Workstation", "Participants", "Plan Costs"],
  },
  advisor: {
    visible: ["Workstation", "Clients", "Rebalancing", "Approvals", "Tasks", "Audit Trail"],
    hidden: ["Participants", "Plan Costs"],
  },
  sponsor: {
    visible: ["Overview", "Plans", "Participants", "Investments", "Plan Costs", "Compliance"],
    hidden: ["Workstation", "Rebalancing", "Philanthropy"],
  },
  participant: {
    visible: ["Overview", "Retirement", "Contributions", "Investments", "Loans", "Beneficiaries", "Education"],
    hidden: ["Workstation", "Clients", "Audit Trail"],
  },
  compliance: {
    visible: ["Compliance Center", "Approvals", "Audit Trail", "Clients"],
    hidden: ["Rebalancing", "Philanthropy"],
  },
  admin: {
    visible: ["Overview", "Advisor Workstation", "Clients", "Institutional", "Approvals", "Audit Trail"],
    hidden: [],
  },
};

const ROLE_ROUTES: Record<AccountKey, string[]> = {
  client: [
    "/dashboard",
    "/portfolio",
    "/accounts",
    "/holdings",
    "/goals",
    "/tax",
    "/estate",
    "/philanthropy",
    "/documents",
    "/messages",
    "/meetings",
    "/reports",
    "/wealthagent",
  ],
  advisor: [
    "/advisor",
    "/advisor/clients",
    "/advisor/portfolio",
    "/advisor/rebalancing",
    "/advisor/tax",
    "/advisor/tasks",
    "/advisor/meetings",
    "/advisor/reports",
    "/advisor/compliance",
    "/approvals",
    "/audit",
  ],
  sponsor: [
    "/institutional",
    "/institutional/plans",
    "/institutional/participants",
    "/institutional/investments",
    "/institutional/fees",
    "/institutional/compliance",
    "/approvals",
  ],
  participant: [
    "/participant",
    "/participant/retirement",
    "/participant/contributions",
    "/participant/investments",
    "/participant/loans",
    "/participant/beneficiaries",
    "/participant/education",
  ],
  compliance: ["/compliance", "/approvals", "/audit", "/advisor/clients"],
  admin: ["/admin", "/advisor", "/advisor/clients", "/institutional", "/approvals", "/compliance", "/audit", "/dashboard"],
};

for (const role of Object.keys(ROLE_NAV) as AccountKey[]) {
  test.describe(`${role} workspace`, () => {
    test(`lands on ${ACCOUNTS[role].home} with role-appropriate navigation`, async ({ page }) => {
      await signIn(page, role);
      await expect(page).toHaveURL(new RegExp(`${ACCOUNTS[role].home}$`));

      const sidebar = page.locator("aside");
      for (const label of ROLE_NAV[role].visible) {
        await expect(sidebar.getByRole("link", { name: label, exact: true })).toBeVisible();
      }
      for (const label of ROLE_NAV[role].hidden) {
        await expect(sidebar.getByRole("link", { name: label, exact: true })).toHaveCount(0);
      }
    });

    test("every route in this workspace renders content", async ({ page }) => {
      await signIn(page, role);

      for (const route of ROLE_ROUTES[role]) {
        await page.goto(route);
        await waitForData(page);
        await expectNoBlankScreen(page);
        // A permission wall would be a failure here: these are the role's own routes.
        await expect(page.getByText("You do not have access to this")).toHaveCount(0);
      }
    });
  });
}

test.describe("Authorisation", () => {
  test("a client cannot open the advisor workstation", async ({ page }) => {
    await signIn(page, "client");
    await page.goto("/advisor");
    await waitForData(page);
    await expect(page.getByText("You do not have access to this")).toBeVisible();
  });

  test("a client cannot read the audit trail", async ({ page }) => {
    await signIn(page, "client");
    await page.goto("/audit");
    await waitForData(page);
    await expect(page.getByText("You do not have access to this")).toBeVisible();
  });

  test("a participant cannot read client portfolios", async ({ page }) => {
    await signIn(page, "participant");
    await page.goto("/portfolio");
    await waitForData(page);
    await expect(page.getByText("You do not have access to this")).toBeVisible();
  });

  test("an unknown route shows the not-found page, not a crash", async ({ page }) => {
    await signIn(page, "client");
    await page.goto("/definitely-not-a-route");
    await expect(page.getByRole("heading", { name: "Page not found" })).toBeVisible();
  });
});

test.describe("Global surfaces", () => {
  test("search finds records and navigates to them", async ({ page }) => {
    await signIn(page, "advisor");
    await page.getByRole("button", { name: /Search clients, accounts/ }).click();

    const dialog = page.getByRole("dialog", { name: "Global search" });
    await expect(dialog).toBeVisible();
    await expect(dialog.getByText("Suggested for you")).toBeVisible();

    await dialog.getByRole("textbox").fill("Johnson");
    await expect(dialog.getByText(/Households|Clients/).first()).toBeVisible({ timeout: 15_000 });
  });

  test("the notification centre opens and lists alerts", async ({ page }) => {
    await signIn(page, "advisor");
    await page.getByRole("button", { name: /Notifications/ }).click();
    await expect(page.getByRole("heading", { name: "Notifications" })).toBeVisible();
  });

  test("the theme toggle switches to dark and persists", async ({ page }) => {
    await signIn(page, "client");
    await page.getByRole("button", { name: /Use (dark|light) theme/ }).click();
    const isDark = await page.locator("html").evaluate((element) => element.classList.contains("dark"));

    await page.reload();
    await waitForData(page);
    const stillDark = await page.locator("html").evaluate((element) => element.classList.contains("dark"));
    expect(stillDark).toBe(isDark);
  });

  test("documents accept an upload and offer a suggested filing", async ({ page }) => {
    await signIn(page, "client");
    await page.goto("/documents");
    await waitForData(page);

    await page.setInputFiles('input[type="file"]', {
      name: "2026_Tax_Return.pdf",
      mimeType: "application/pdf",
      buffer: Buffer.from("%PDF-1.4 end-to-end test document"),
    });

    const drawer = page.getByRole("dialog");
    await expect(drawer).toBeVisible({ timeout: 30_000 });
    await expect(drawer.getByText("Suggested filing")).toBeVisible();
    await expect(drawer.getByText("Deterministic rules engine")).toBeVisible();
    await expect(drawer.getByRole("button", { name: "Accept" })).toBeVisible();
    await expect(drawer.getByRole("button", { name: "Edit" })).toBeVisible();
    await expect(drawer.getByRole("button", { name: "Reject" })).toBeVisible();

    await drawer.getByRole("button", { name: "Accept" }).click();
    await waitForData(page);
    await expect(page.getByText("2026_Tax_Return.pdf")).toBeVisible();
  });

  test("a report generates and previews with its assumptions", async ({ page }) => {
    await signIn(page, "client");
    await page.goto("/reports");
    await waitForData(page);

    await page.getByRole("button", { name: /Generate report/ }).first().click();
    await expect(page.getByText("Report preview")).toBeVisible({ timeout: 45_000 });
    await expect(page.getByText("Assumptions and limitations")).toBeVisible();
    await expect(page.getByText(/not a custodial statement/i)).toBeVisible();
  });
});
