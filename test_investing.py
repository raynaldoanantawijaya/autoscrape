import asyncio
from playwright.async_api import async_playwright

url = "https://id.investing.com/crypto/currencies"

async def main():
    async with async_playwright() as p:
        browser = await p.chromium.launch(headless=True)
        context = await browser.new_context(
            user_agent="Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36",
            extra_http_headers={"Accept-Language": "id-ID,id;q=0.9"}
        )
        page = await context.new_page()
        
        # Block images and other heavy resources
        async def route_intercept(route):
            if route.request.resource_type in ["image", "media", "font", "stylesheet"]:
                await route.abort()
            else:
                await route.continue_()
                
        await page.route("**/*", route_intercept)
        
        try:
            print(f"Going to {url}...")
            await page.goto(url, wait_until="domcontentloaded", timeout=60000)
            await page.wait_for_timeout(3000)
            
            # Find all anchor tags (<a>) near the bottom of the page or containing SVGs
            elements = await page.evaluate('''() => {
                let anchors = Array.from(document.querySelectorAll('a'));
                return anchors
                    .slice(-50) // look at the last 50 anchors on the page
                    .map(a => ({
                        href: a.href,
                        text: a.innerText,
                        html: a.outerHTML,
                        className: a.className
                    }));
            }''')
            
            print(f"Found {len(elements)} anchors at the bottom.")
            with open("temp_anchors.txt", "w", encoding="utf-8") as f:
                for el in elements:
                    f.write(f"HREF: {el['href']}\nCLASS: {el['className']}\nHTML: {el['html']}\n{'-'*50}\n")
                    
            print("Saved anchors to temp_anchors.txt")
                        
        except Exception as e:
            print(f"Global Error: {e}")
        finally:
            await browser.close()

if __name__ == "__main__":
    asyncio.run(main())
