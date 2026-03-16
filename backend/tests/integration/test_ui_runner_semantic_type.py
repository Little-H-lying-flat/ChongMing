import pytest
from playwright.async_api import async_playwright

from app.engines.runner.ui_runner import UiRunner
from app.engines.vision.dom_service import DomService
from app.schemas.aui_ir import VisualActionIR, VisualLocator


@pytest.mark.asyncio
async def test_ui_runner_semantic_type_disambiguates_repeated_inputs():
    async with async_playwright() as playwright:
        browser = await playwright.chromium.launch(headless=True)
        page = await browser.new_page()
        runner = UiRunner(page, DomService())

        html_content = """
        <html>
            <body>
                <section class="checkout-form" style="width: 480px; padding: 16px; border: 1px solid #ccc;">
                    <div class="field">
                        <label for="first-name">First Name</label>
                        <input id="first-name" name="firstName" />
                    </div>
                    <div class="field" style="margin-top: 16px;">
                        <label for="last-name">Last Name</label>
                        <input id="last-name" name="lastName" />
                    </div>
                </section>
            </body>
        </html>
        """

        await page.route(
            "http://semantic-form.local/*",
            lambda route: route.fulfill(
                status=200,
                body=html_content,
                headers={"Content-Type": "text/html"},
            ),
        )
        await page.goto("http://semantic-form.local/index.html")

        form = page.locator(".checkout-form")
        box = await form.bounding_box()
        assert box is not None

        action = VisualActionIR(
            action_type="type",
            target=VisualLocator(strategy="visual", value="15"),
            params={
                "text": "Codex",
                "field_hint": "First Name",
                "semantic_hint": "First Name",
            },
        )
        id_map = {
            15: {
                "center": (box["x"] + box["width"] / 2, box["y"] + box["height"] / 2),
                "label": "form",
            }
        }

        result = await runner.execute(action, id_map=id_map)

        assert result is True
        assert await page.locator("#first-name").input_value() == "Codex"
        assert await page.locator("#last-name").input_value() == ""

        await browser.close()
