"""Launch the packaged Chromium once to verify the production browser runtime."""

import asyncio
import os

from playwright.async_api import async_playwright


async def main() -> None:
    chromium_sandbox = os.getenv("BROWSER_SMOKE_CHROMIUM_SANDBOX", "true").lower() not in {
        "0",
        "false",
        "no",
    }
    async with async_playwright() as playwright:
        browser = await playwright.chromium.launch(
            headless=True,
            chromium_sandbox=chromium_sandbox,
            executable_path=os.getenv("PLAYWRIGHT_CHROMIUM_EXECUTABLE_PATH") or None,
            env={},
            args=["--disable-extensions", "--disable-file-system"],
        )
        try:
            page = await browser.new_page()
            await page.goto("about:blank")
            if await page.title() != "":
                raise RuntimeError("Unexpected Chromium smoke-test page")
        finally:
            await browser.close()


if __name__ == "__main__":
    asyncio.run(main())
