"""Test: Use Playwright infinite scroll to extract ALL crypto data from Investing.com."""
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
        
        print("Loading page...")
        await page.goto("https://id.investing.com/crypto/currencies", wait_until="domcontentloaded", timeout=30000)
        await page.wait_for_timeout(5000)
        
        # First: get initial data from __NEXT_DATA__
        initial = await page.evaluate('''() => {
            let el = document.getElementById('__NEXT_DATA__');
            if (!el) return null;
            let d = JSON.parse(el.textContent);
            let store = d.props?.pageProps?.state?.cryptoStore;
            let coins = store?.cryptoCoinsCollection?._collection || [];
            return {
                count: coins.length,
                hasNextPage: store?.hasNextPage,
                endCursor: store?.endCursor,
                sample: coins.slice(0, 3).map(c => ({
                    name: c.name, symbol: c.symbol, rank: c.rank,
                    last: c.last, marketCap: c.marketCap
                }))
            };
        }''')
        print(f"Initial __NEXT_DATA__: {initial['count']} coins, hasNextPage={initial['hasNextPage']}")
        print(f"Sample: {json.dumps(initial['sample'], indent=2)}")
        
        # Now try to scroll down and see if more data loads via the React store
        prev_row_count = 0
        for scroll_attempt in range(20):
            # Count current visible rows in the datatable
            row_count = await page.evaluate('''() => {
                // Try multiple selectors for rows
                let rows = document.querySelectorAll('tr[data-test]');
                if (rows.length === 0) rows = document.querySelectorAll('[class*="datatable_row"]');
                if (rows.length === 0) rows = document.querySelectorAll('table tbody tr');
                return rows.length;
            }''')
            
            if row_count == prev_row_count and scroll_attempt > 2:
                print(f"  Scroll {scroll_attempt}: No new rows ({row_count}), stopping.")
                break
            
            prev_row_count = row_count
            print(f"  Scroll {scroll_attempt}: {row_count} rows visible")
            
            await page.evaluate("window.scrollTo(0, document.body.scrollHeight)")
            await page.wait_for_timeout(2000)
        
        # Final count
        final_count = await page.evaluate('''() => {
            let rows = document.querySelectorAll('tr[data-test]');
            if (rows.length === 0) rows = document.querySelectorAll('[class*="datatable_row"]');
            if (rows.length === 0) rows = document.querySelectorAll('table tbody tr');
            return rows.length;
        }''')
        print(f"\nFinal visible rows after scrolling: {final_count}")
        
        await browser.close()

if __name__ == "__main__":
    asyncio.run(main())
