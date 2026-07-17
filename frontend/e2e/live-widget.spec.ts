import { expect, test } from "@playwright/test";

const liveUrl = process.env.E2E_LIVE_URL;

test.skip(!liveUrl, "E2E_LIVE_URL is required for deployed smoke tests");

test("deployed widget completes the bilingual sales handoff smoke path", async ({ page }) => {
  const consoleErrors: string[] = [];
  page.on("console", (message) => {
    if (message.type() === "error") consoleErrors.push(message.text());
  });
  page.on("pageerror", (error) => consoleErrors.push(error.message));

  await page.setViewportSize({ width: 390, height: 844 });
  await page.goto("/widget");
  await expect(page.getByText("Chat TBM • En línea", { exact: true })).toBeVisible();
  await expect(page.getByPlaceholder("Escribe tu mensaje…", { exact: true })).toBeDisabled();

  await page.getByRole("button", { name: "Aceptar aviso", exact: true }).click();
  await page.getByRole("button", { name: "Quiero hablar con ventas", exact: true }).click();

  const response = page.getByText(
    "Claro, con gusto. ¿Prefieres que un especialista de ventas de TBM te contacte por correo electrónico o por teléfono?",
    { exact: true },
  );
  await expect(response).toBeVisible({ timeout: 15_000 });
  await expect(response).toHaveCSS("font-family", "Arial, Helvetica, sans-serif");
  await expect(response).toHaveCSS("font-size", "14px");
  await expect(response).toHaveCSS("line-height", "21px");

  const overflow = await page.evaluate(
    () => document.documentElement.scrollWidth > document.documentElement.clientWidth,
  );
  expect(overflow).toBe(false);
  expect(consoleErrors).toEqual([]);
});
