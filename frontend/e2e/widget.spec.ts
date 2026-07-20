import { expect, test, type Page, type Route } from "@playwright/test";

const localUrl = "http://127.0.0.1:3100";
const mockApiUrl = "https://api.example.invalid";
const consoleErrors = new WeakMap<Page, string[]>();

const replies = {
  salesEs:
    "Claro, con gusto. ¿Prefieres que un especialista de ventas de TBM te contacte por correo electrónico o por teléfono?",
  salesEn:
    "Of course, happy to help. Would you prefer a TBM sales specialist to contact you by email or phone?",
  quoteEs:
    "Con gusto te ayudo a solicitar una cotización.\n\n**¿Cuál es la ruta?**\n\n- Ciudad de origen\n- Ciudad de destino\n\n**¿Qué tipo de mercancía necesitas transportar?**",
  pricingEs:
    "Puedo ayudarte a obtener un precio exacto con un especialista de TBM, pero no puedo dar ni estimar tarifas aquí. ¿Cuál es el origen, destino, tipo de carga, volumen o frecuencia y fecha prevista de envío?",
} as const;

function sse(text: string, done: Record<string, unknown> = { message_count: 1 }) {
  return [
    `event: token\ndata: ${JSON.stringify({ text })}`,
    `event: done\ndata: ${JSON.stringify(done)}`,
    "",
  ].join("\n\n");
}

async function fulfillApi(route: Route) {
  const request = route.request();
  const path = new URL(request.url()).pathname;
  const headers = {
    "Access-Control-Allow-Headers": "Authorization, Content-Type, X-Widget-Origin",
    "Access-Control-Allow-Methods": "POST, OPTIONS",
    "Access-Control-Allow-Origin": localUrl,
    "Cache-Control": "no-store",
  };

  if (request.method() === "OPTIONS") {
    await route.fulfill({ status: 204, headers, body: "" });
    return;
  }

  if (path === "/api/session") {
    await route.fulfill({
      status: 201,
      contentType: "application/json",
      headers,
      body: JSON.stringify({ session_id: "00000000-0000-4000-8000-000000000001", widget_token: "e2e-token" }),
    });
    return;
  }
  if (path.endsWith("/consent")) {
    await route.fulfill({
      status: 201,
      contentType: "application/json",
      headers,
      body: JSON.stringify({ consent_id: "00000000-0000-4000-8000-000000000002" }),
    });
    return;
  }
  if (path.endsWith("/feedback")) {
    await route.fulfill({ status: 204, headers, body: "" });
    return;
  }
  if (path.endsWith("/message")) {
    const content = (request.postDataJSON() as { content: string }).content;
    if (content === "__rate_limit_test__") {
      await route.fulfill({ status: 429, contentType: "application/json", headers, body: "{}" });
      return;
    }
    if (content === "__close_test__") {
      await route.fulfill({
        status: 200,
        contentType: "text/event-stream",
        headers,
        body: sse(
          "Fue un placer ayudarte. Un miembro del equipo de ventas de TBM te contactará en breve para continuar con tu solicitud.",
          { closed: true },
        ),
      });
      return;
    }
    if (content === "__unsafe_markdown_test__") {
      await route.fulfill({
        status: 200,
        contentType: "text/event-stream",
        headers,
        body: sse("Texto seguro <script>window.__xss = true</script> [malicioso](javascript:alert(1))"),
      });
      return;
    }
    const reply =
      content === "Quiero hablar con ventas"
        ? replies.salesEs
        : content === "I want to speak with sales"
          ? replies.salesEn
          : content === "Quiero solicitar una cotización"
            ? replies.quoteEs
            : replies.pricingEs;
    await route.fulfill({
      status: 200,
      contentType: "text/event-stream",
      headers,
      body: sse(reply),
    });
    return;
  }

  await route.fulfill({ status: 404, contentType: "application/json", body: "{}" });
}

test.beforeEach(async ({ page }) => {
  const errors: string[] = [];
  consoleErrors.set(page, errors);
  page.on("console", (message) => {
    if (message.type() === "error") errors.push(message.text());
  });
  page.on("pageerror", (error) => errors.push(error.message));
  await page.route(`${mockApiUrl}/api/**`, fulfillApi);
});

test.afterEach(async ({ page }) => {
  expect(consoleErrors.get(page) ?? [], "browser console errors").toEqual([]);
});

async function acceptNotice(page: Page, label: string) {
  const button = page.getByRole("button", { name: label, exact: true });
  await expect(button).toBeEnabled();
  await button.click();
}

test("Spanish sales shortcut uses the normal chat voice and typography", async ({ page }) => {
  await page.goto("/widget");
  await expect(page.getByText("Chat TBM • En línea", { exact: true })).toBeVisible();
  await expect(page.getByPlaceholder("Escribe tu mensaje…", { exact: true })).toBeDisabled();

  await acceptNotice(page, "Aceptar aviso");
  await page.getByRole("button", { name: "Quiero hablar con ventas", exact: true }).click();

  const greeting = page.getByText(
    "Hola, ¿en qué puedo ayudarte? Puedes preguntarme sobre envíos, servicios o cómo contactar a TBM.",
    { exact: true },
  );
  const response = page.getByText(replies.salesEs, { exact: true });
  await expect(response).toBeVisible();
  await expect(response).toHaveCSS("font-family", "Arial, Helvetica, sans-serif");
  await expect(response).toHaveCSS("font-size", "14px");
  await expect(response).toHaveCSS("line-height", "21px");
  await expect(greeting).toHaveCSS("font-family", "Arial, Helvetica, sans-serif");
});

test("English sales shortcut follows the same intake path", async ({ page }) => {
  await page.goto("/widget");
  await page.getByRole("button", { name: "EN", exact: true }).click();
  await expect(page.getByText("TBM chat • Online", { exact: true })).toBeVisible();

  await acceptNotice(page, "Accept notice");
  await page.getByRole("button", { name: "I want to speak with sales", exact: true }).click();

  await expect(page.getByText(replies.salesEn, { exact: true })).toBeVisible();
});

test("quote formatting and pricing guardrail render safely", async ({ page }) => {
  await page.goto("/widget");
  await acceptNotice(page, "Aceptar aviso");
  await page.getByRole("button", { name: "Quiero solicitar una cotización", exact: true }).click();

  await expect(page.getByText("¿Cuál es la ruta?", { exact: true })).toHaveCSS(
    "font-weight",
    "800",
  );
  await expect(page.getByRole("listitem")).toHaveCount(2);
  await expect(page.getByText("**¿Cuál es la ruta?**", { exact: true })).toHaveCount(0);

  const textbox = page.getByPlaceholder("Escribe tu mensaje…", { exact: true });
  await textbox.fill("¿Cuánto cuesta un envío de Tijuana a Phoenix?");
  await textbox.press("Enter");

  const pricingReply = page.getByText(replies.pricingEs, { exact: true });
  await expect(pricingReply).toBeVisible();
  await expect(pricingReply).not.toContainText(/[$€£]|\b\d+(?:[.,]\d+)?\s*(?:USD|MXN|pesos?|dólares?)/i);
});

test("mobile widget has no horizontal overflow", async ({ page }) => {
  await page.setViewportSize({ width: 390, height: 844 });
  await page.goto("/widget");
  await expect(page.getByText("Chat TBM • En línea", { exact: true })).toBeVisible();

  const layout = await page.evaluate(() => ({
    documentOverflow: document.documentElement.scrollWidth > document.documentElement.clientWidth,
    widgetOverflow: document.querySelector("main")
      ? document.querySelector("main")!.scrollWidth > document.querySelector("main")!.clientWidth
      : true,
  }));
  expect(layout).toEqual({ documentOverflow: false, widgetOverflow: false });
});

test("server closure ends the conversation instead of restarting it", async ({ page }) => {
  await page.goto("/widget");
  await acceptNotice(page, "Aceptar aviso");

  const textbox = page.getByPlaceholder("Escribe tu mensaje…", { exact: true });
  await textbox.fill("__close_test__");
  await textbox.press("Enter");

  await expect(
    page.getByText(
      "Fue un placer ayudarte. Un miembro del equipo de ventas de TBM te contactará en breve para continuar con tu solicitud.",
      { exact: true },
    ),
  ).toBeVisible();
  await expect(
    page.getByText(
      "Conversación finalizada. El equipo de ventas de TBM dará seguimiento a tu solicitud.",
      { exact: true },
    ),
  ).toBeVisible();
  await expect(page.getByRole("textbox")).toBeDisabled();
});

test("feedback succeeds and rate limits show a recoverable message", async ({ page }) => {
  await page.goto("/widget");
  await acceptNotice(page, "Aceptar aviso");
  await page.getByRole("button", { name: "Quiero hablar con ventas", exact: true }).click();
  await page.getByRole("button", { name: "Sí, fue útil", exact: true }).click();
  await expect(page.getByText("✓ Gracias por tus comentarios.", { exact: true })).toBeVisible();

  const textbox = page.getByPlaceholder("Escribe tu mensaje…", { exact: true });
  await textbox.fill("__rate_limit_test__");
  await textbox.press("Enter");
  await expect(
    page.getByText("Has enviado mensajes muy rápido. Espera un momento e inténtalo de nuevo.", {
      exact: true,
    }),
  ).toBeVisible();
  await expect(textbox).toBeEnabled();
  const expectedErrors = consoleErrors.get(page) ?? [];
  expect(expectedErrors.some((message) => message.includes("429 (Too Many Requests)"))).toBe(true);
  expectedErrors.length = 0;
});

test("assistant markup is rendered as text unless it is an allowed HTTPS link", async ({ page }) => {
  await page.goto("/widget");
  await acceptNotice(page, "Aceptar aviso");

  const textbox = page.getByPlaceholder("Escribe tu mensaje…", { exact: true });
  await textbox.fill("__unsafe_markdown_test__");
  await textbox.press("Enter");

  await expect(page.getByText(/<script>window\.__xss = true<\/script>/)).toBeVisible();
  await expect(page.locator("script").filter({ hasText: "window.__xss" })).toHaveCount(0);
  await expect(page.locator('a[href^="javascript:"]')).toHaveCount(0);
  expect(await page.evaluate(() => (window as Window & { __xss?: boolean }).__xss)).toBeUndefined();
});
