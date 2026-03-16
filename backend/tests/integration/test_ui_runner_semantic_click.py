import pytest
from playwright.async_api import async_playwright

from app.engines.runner.ui_runner import UiRunner
from app.engines.vision.dom_service import DomService
from app.schemas.aui_ir import VisualActionIR, VisualLocator


@pytest.mark.asyncio
async def test_ui_runner_semantic_click_disambiguates_repeated_buttons():
    async with async_playwright() as playwright:
        browser = await playwright.chromium.launch(headless=True)
        page = await browser.new_page()
        runner = UiRunner(page, DomService())

        html_content = """
        <html>
            <body>
                <div class="product-card" data-name="Alpha Pack">
                    <h2>Alpha Pack</h2>
                    <button class="add-btn" onclick="window.clicked='Alpha Pack'">Add to cart</button>
                </div>
                <div class="product-card" data-name="Beta Jacket">
                    <h2>Beta Jacket</h2>
                    <button class="add-btn" onclick="window.clicked='Beta Jacket'">Add to cart</button>
                </div>
                <script>window.clicked = '';</script>
            </body>
        </html>
        """

        await page.route(
            "http://semantic.local/*",
            lambda route: route.fulfill(
                status=200,
                body=html_content,
                headers={"Content-Type": "text/html"},
            ),
        )
        await page.goto("http://semantic.local/index.html")

        first_button = page.locator(".add-btn").first
        box = await first_button.bounding_box()
        assert box is not None

        action = VisualActionIR(
            action_type="click",
            target=VisualLocator(strategy="visual", value="47"),
            params={"semantic_hint": "Beta Jacket"},
        )
        id_map = {
            47: {
                "center": (box["x"] + box["width"] / 2, box["y"] + box["height"] / 2),
                "label": "button",
            }
        }

        result = await runner.execute(action, id_map=id_map)

        assert result is True
        assert await page.evaluate("window.clicked") == "Beta Jacket"

        await browser.close()
