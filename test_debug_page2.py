"""Debug: Find out WHY page 2 breaks and explore __NEXT_DATA__ approach."""
import asyncio, json
from playwright.async_api import async_playwright

async def main():
    async with async_playwright() as p:
        browser = await p.chromium.launch(headless=True)
        context = await browser.new_context(
            user_agent="Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36",
            extra_http_headers={"Accept-Language": "id-ID,id;q=0.9"}
        )
        page = await context.new_page()
        
        # Block heavy stuff
        async def route_intercept(route):
            if route.request.resource_type in ["image", "media", "font", "stylesheet"]:
                await route.abort()
            else:
                await route.continue_()
        await page.route("**/*", route_intercept)

        for pg in [1, 2]:
            url = f"https://id.investing.com/crypto/currencies/{pg}" if pg > 1 else "https://id.investing.com/crypto/currencies"
            print(f"\n=== PAGE {pg}: {url} ===")
            try:
                await page.goto(url, wait_until="domcontentloaded", timeout=30000)
            except Exception as e:
                print(f"  goto error (continuing): {e}")
            
            await page.wait_for_timeout(5000)
            
            # Check __NEXT_DATA__
            next_data = await page.evaluate('''() => {
                let el = document.getElementById('__NEXT_DATA__');
                return el ? el.textContent.length : 0;
            }''')
            print(f"  __NEXT_DATA__ length: {next_data}")
            
            # Check tables
            table_count = await page.evaluate('() => document.querySelectorAll("table").length')
            print(f"  Tables found: {table_count}")
            
            if table_count > 0:
                row_count = await page.evaluate('() => document.querySelectorAll("table tr").length')
                print(f"  Table rows: {row_count}")
            
            # Extract __NEXT_DATA__ crypto data
            crypto_count = await page.evaluate('''() => {
                let el = document.getElementById('__NEXT_DATA__');
                if (!el) return 0;
                try {
                    let d = JSON.parse(el.textContent);
                    let c = d.props?.pageProps?.state?.cryptoStore?.cryptoCoinsCollection?._collection;
                    return c ? c.length : -1;
                } catch(e) { return -2; }
            }''')
            print(f"  Crypto items in __NEXT_DATA__: {crypto_count}")
            
            # Get hasNextPage & endCursor
            paging = await page.evaluate('''() => {
                let el = document.getElementById('__NEXT_DATA__');
                if (!el) return null;
                try {
                    let d = JSON.parse(el.textContent);
                    let s = d.props?.pageProps?.state?.cryptoStore;
                    return { hasNextPage: s?.hasNextPage, endCursor: s?.endCursor };
                } catch(e) { return null; }
            }''')
            print(f"  Paging info: {paging}")

        await browser.close()

if __name__ == "__main__":
    asyncio.run(main())
