import asyncio
from playwright.async_api import async_playwright

async def main():
    async with async_playwright() as p:
        browser = await p.chromium.launch(headless=True)
        context = await browser.new_context(
            user_agent="Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36",
            extra_http_headers={"Accept-Language": "id-ID,id;q=0.9"}
        )
        page = await context.new_page()
        try:
            print(f"Going to page 2...")
            await page.goto("https://id.investing.com/crypto/currencies/2", wait_until="domcontentloaded", timeout=60000)
            await page.wait_for_timeout(5000)
            await page.screenshot(path="page2.png", full_page=True)
            print("Done")
            
            elements = await page.evaluate('''() => {
                let els = Array.from(document.querySelectorAll('table'));
                return els.length;
            }''')
            print(f"Tables found: {elements}")

        except Exception as e:
            print(f"Global Error: {e}")
        finally:
            await browser.close()

if __name__ == "__main__":
    asyncio.run(main())
