import { expect, type Page } from "@playwright/test";

export const DEMO_PASSWORD = "Demo1234!";

export const ACCOUNTS = {
  client: { email: "sarah.johnson@example.com", label: "Client Demo", home: "/dashboard" },
  advisor: { email: "marcus.webb@nexgile.example", label: "Advisor Demo", home: "/advisor" },
  sponsor: { email: "diane.ellis@brightpath.example", label: "Sponsor Demo", home: "/institutional" },
  participant: { email: "andre.fitzgerald@brightpath.example", label: "Participant Demo", home: "/participant" },
  compliance: { email: "priya.raman@nexgile.example", label: "Compliance Demo", home: "/compliance" },
  admin: { email: "ellen.sorensen@nexgile.example", label: "Admin Demo", home: "/admin" },
} as const;

export type AccountKey = keyof typeof ACCOUNTS;

/** Sign in through the real form and wait for the role's workspace to load. */
export async function signIn(page: Page, role: AccountKey): Promise<void> {
  const account = ACCOUNTS[role];
  await page.goto("/login");
  await page.getByLabel("Email address").fill(account.email);
  await page.getByLabel("Password").fill(DEMO_PASSWORD);
  await page.getByRole("button", { name: "Sign in" }).click();
  await page.waitForURL(`**${account.home}`, { timeout: 30_000 });
  await expect(page.getByRole("heading", { level: 1 })).toBeVisible();
}

export async function signOut(page: Page): Promise<void> {
  await page.getByRole("button", { name: /my workspace|sign out/i }).first().click().catch(() => undefined);
  const menu = page.locator("header button", { hasText: /./ }).last();
  await menu.click();
  await page.getByRole("button", { name: "Sign out" }).click();
  await page.waitForURL("**/login");
}

/** Every screen must resolve to content, never a blank frame or a raw error. */
export async function expectNoBlankScreen(page: Page): Promise<void> {
  await expect(page.getByRole("heading", { level: 1 })).toBeVisible();
  await expect(page.locator("body")).not.toContainText("Application error");
  await expect(page.locator("body")).not.toContainText("Unhandled Runtime Error");
}

/** Wait for the first data-backed panel to finish loading. */
export async function waitForData(page: Page): Promise<void> {
  await expect(page.locator(".skeleton").first()).toBeHidden({ timeout: 30_000 }).catch(() => undefined);
  await page.waitForLoadState("networkidle").catch(() => undefined);
}
