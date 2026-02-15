import pytest
import asyncio
from playwright.async_api import async_playwright
from app.engines.runner.ui_runner import UiRunner
from app.engines.vision.dom_service import DomService
from app.schemas.aui_ir import VisualActionIR, VisualLocator

@pytest.mark.asyncio
async def test_ui_runner_execution():
    """Verify UiRunner can execute actions on a real browser page"""
    
    async with async_playwright() as p:
        browser = await p.chromium.launch(headless=True)
        page = await browser.new_page()
        
        # 1. Initialize Runner
        dom_service = DomService()
        runner = UiRunner(page, dom_service)
        
        try:
            # 2. Test Navigation
            # Using a data URL for speed and reliability (no network dep)
            html_content = """
            <html>
                <body>
                    <button id="btn">Click Me</button>
                    <input id="inp" type="text" />
                    <div id="result"></div>
                    <script>
                        document.getElementById('btn').addEventListener('click', () => {
                            document.getElementById('result').innerText = 'Clicked';
                        });
                    </script>
                </body>
            </html>
            """
            await page.route("http://test.local/*", lambda route: route.fulfill(
                status=200, 
                body=html_content, 
                headers={"Content-Type": "text/html"}
            ))
            
            nav_action = VisualActionIR(
                action_type="navigate",
                params={"url": "http://test.local/index.html"},
                target=VisualLocator(strategy="dom", value="body") # Dummy target for navigate
            )
            result = await runner.execute(nav_action)
            assert result is True
            assert page.url == "http://test.local/index.html"
            
            # 3. Test DOM Click
            click_action = VisualActionIR(
                action_type="click",
                target=VisualLocator(strategy="dom", value="#btn")
            )
            result = await runner.execute(click_action)
            assert result is True
            
            # Verify effect
            text = await page.inner_text("#result")
            assert text == "Clicked"
            
            # 4. Test DOM Type
            type_action = VisualActionIR(
                action_type="type",
                target=VisualLocator(strategy="dom", value="#inp"),
                params={"text": "Hello World"}
            )
            result = await runner.execute(type_action)
            assert result is True
            
            # Verify effect
            input_value = await page.input_value("#inp")
            assert input_value == "Hello World"
            
            # 5. Test Visual Click (Mocking the ID Map)
            # transform #btn position to coordinates
            box = await page.locator("#btn").bounding_box()
            x, y = box["x"] + box["width"] / 2, box["y"] + box["height"] / 2
            
            # Mock ID Map from SoM
            id_map = {
                99: {"center": (x, y), "label": "button"}
            }
            
            visual_click = VisualActionIR(
                action_type="click",
                target=VisualLocator(strategy="visual", value="99")
            )
            
            # Reset state
            await page.evaluate("document.getElementById('result').innerText = ''")
            
            result = await runner.execute(visual_click, id_map=id_map)
            assert result is True
            
            # Verify effect again
            text = await page.inner_text("#result")
            assert text == "Clicked"
            
        finally:
            await browser.close()
