
import asyncio
import sys
import logging

# Add backend to path
sys.path.append("d:/project/ChongMing/backend")

# Configure logging
logging.basicConfig(level=logging.INFO)

from app.engines.right_pupil import RightPupilEngine

async def test_stealth():
    print("--- Starting Stealth Mode Test ---")
    engine = RightPupilEngine()
    
    # Start session (this triggers the modified start_session logic)
    await engine.start_session(headless=True)
    page = engine.page
    
    try:
        print("1. Checking navigator.webdriver...")
        webdriver = await page.evaluate("navigator.webdriver")
        print(f"   navigator.webdriver = {webdriver}")
        
        print("2. Checking user agent...")
        ua = await page.evaluate("navigator.userAgent")
        print(f"   User Agent = {ua}")
        
        print("3. Checking chrome.runtime...")
        # Stealth usually mocks this
        chrome_runtime = await page.evaluate("window.chrome && window.chrome.runtime")
        print(f"   window.chrome.runtime exists: {bool(chrome_runtime)}")

        # Verification Logic
        failures = []
        if webdriver:
            failures.append("navigator.webdriver is True")
        
        if "HeadlessChrome" in ua:
             failures.append("User Agent contains 'HeadlessChrome'")
             
        if not failures:
            print("\n✅ PASSED: Stealth mode seems active.")
        else:
            print(f"\n❌ FAILED: {', '.join(failures)}")
            
    finally:
        await engine.stop_session()

if __name__ == "__main__":
    asyncio.run(test_stealth())
