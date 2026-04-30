import asyncio
from playwright.async_api import async_playwright

async def check_browser():
    async with async_playwright() as p:
        browser = await p.chromium.launch(headless=True)
        page = await browser.new_page()
        
        errors = []
        page.on("console", lambda msg: errors.append(f"CONSOLE {msg.type}: {msg.text}") if msg.type == "error" else None)
        page.on("pageerror", lambda err: errors.append(f"PAGE ERROR: {err}"))
        page.on("requestfailed", lambda req: errors.append(f"REQUEST FAILED: {req.url} - {req.failure}"))
        
        print("Navigating to http://115.191.10.107:5173/ ...")
        await page.goto("http://115.191.10.107:5173/")
        
        await page.wait_for_timeout(3000)
        
        print("\n--- Errors Collected ---")
        for err in errors:
            print(err)
            
        print("\n--- Clicking Run Button ---")
        try:
            await page.click("button:has-text('运行')")
            await page.wait_for_timeout(3000)
        except Exception as e:
            print(f"Could not click Run button: {e}")
            
        print("\n--- Errors After Click ---")
        for err in errors:
            print(err)
            
        await browser.close()

if __name__ == "__main__":
    asyncio.run(check_browser())
