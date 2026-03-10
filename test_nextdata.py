"""Full test: Extract ALL crypto data from Investing.com using __NEXT_DATA__ + scroll-triggered API capture."""
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
        
        # Capture response bodies for API calls with crypto data
        api_responses = []
        async def on_response(response):
            url = response.url
            # Look for any XHR/fetch that returns crypto data
            if response.request.resource_type in ["xhr", "fetch", "document"]:
                try:
                    ct = response.headers.get("content-type", "")
                    if "json" in ct or "crypto" in url.lower():
                        body = await response.text()
                        if len(body) > 500 and ("crypto" in body.lower() or "bitcoin" in body.lower()):
                            api_responses.append({
                                "url": url[:200],
                                "size": len(body),
                                "preview": body[:300]
                            })
                except:
                    pass
        page.on("response", on_response)
        
        print("Loading page...")
        await page.goto("https://id.investing.com/crypto/currencies", wait_until="domcontentloaded", timeout=30000)
        await page.wait_for_timeout(5000)
        
        # Extract initial data from __NEXT_DATA__
        all_coins = await page.evaluate('''() => {
            let el = document.getElementById('__NEXT_DATA__');
            if (!el) return [];
            let d = JSON.parse(el.textContent);
            let coins = d.props?.pageProps?.state?.cryptoStore?.cryptoCoinsCollection?._collection || [];
            return coins.map(c => ({
                rank: c.rank,
                name: c.name,
                symbol: c.symbol,
                price: c.last,
                change24h: c.changeOneDay,
                change7d: c.changeSevenDays,
                marketCap: c.marketCap,
                volume24h: c.volumeOneDay,
                totalVol: c.totalVol
            }));
        }''')
        print(f"Initial coins from __NEXT_DATA__: {len(all_coins)}")
        
        # Now try aggressive scrolling to trigger infinite scroll API  
        for i in range(30):
            # Scroll to very bottom
            await page.evaluate("window.scrollTo(0, document.body.scrollHeight)")
            await page.wait_for_timeout(1500)
            
            # Check if new API responses with crypto data were captured
            if api_responses:
                print(f"  Scroll {i}: Found {len(api_responses)} crypto API response(s)!")
                for resp in api_responses:
                    print(f"    URL: {resp['url']}")
                    print(f"    Size: {resp['size']}")
                    print(f"    Preview: {resp['preview'][:200]}...")
                break
        else:
            print("  No crypto API responses found after scrolling.")
        
        # Save initial data for verification
        print(f"\nTotal extracted: {len(all_coins)} coins")
        if all_coins:
            print(f"First: {all_coins[0]}")
            print(f"Last: {all_coins[-1]}")
        
        with open("investing_nextdata.json", "w", encoding="utf-8") as f:
            json.dump(all_coins, f, indent=2, ensure_ascii=False)
        print("Saved to investing_nextdata.json")
        
        await browser.close()

if __name__ == "__main__":
    asyncio.run(main())
