"""Discover the internal API endpoint Investing.com uses to load more crypto data."""
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
        
        # Block heavy stuff but NOT XHR/fetch
        async def route_intercept(route):
            if route.request.resource_type in ["image", "media", "font", "stylesheet"]:
                await route.abort()
            else:
                await route.continue_()
        await page.route("**/*", route_intercept)
        
        # Capture all API requests
        api_calls = []
        def on_request(request):
            url = request.url
            if "api" in url.lower() or "graphql" in url.lower() or "crypto" in url.lower():
                if request.resource_type in ["xhr", "fetch"]:
                    api_calls.append({
                        "url": url,
                        "method": request.method,
                        "post_data": request.post_data[:500] if request.post_data else None
                    })
        page.on("request", on_request)
        
        print("Loading page 1...")
        await page.goto("https://id.investing.com/crypto/currencies", wait_until="domcontentloaded", timeout=30000)
        await page.wait_for_timeout(3000)
        
        # Extract __NEXT_DATA__ to get the endCursor
        paging = await page.evaluate('''() => {
            let el = document.getElementById('__NEXT_DATA__');
            if (!el) return null;
            let d = JSON.parse(el.textContent);
            let s = d.props?.pageProps?.state?.cryptoStore;
            return { hasNextPage: s?.hasNextPage, endCursor: s?.endCursor, currentContentView: s?.currentContentView };
        }''')
        print(f"Paging: {paging}")
        
        # Now try to scroll down to trigger infinite scroll
        print("Scrolling to bottom to trigger 'load more'...")
        await page.evaluate("window.scrollTo(0, document.body.scrollHeight)")
        await page.wait_for_timeout(3000)
        
        # Try clicking "show more" button if it exists
        show_more = await page.query_selector('button:has-text("Tampilkan Lebih"), button:has-text("Show More"), button:has-text("Load More"), button:has-text("Muat")')
        if show_more:
            print("Found 'show more' button, clicking...")
            await show_more.click()
            await page.wait_for_timeout(3000)
        else:
            print("No 'show more' button found on the page")
        
        # Check if any API calls were made
        print(f"\nAPI calls captured ({len(api_calls)}):")
        for call in api_calls[:20]:
            print(f"  {call['method']} {call['url'][:150]}")
            if call['post_data']:
                print(f"    POST: {call['post_data'][:200]}")
                
        # Also try to find 'load more' by looking at all buttons
        buttons = await page.evaluate('''() => {
            return Array.from(document.querySelectorAll('button'))
                .map(b => ({ text: b.innerText, cls: b.className, html: b.outerHTML.substring(0, 200) }))
                .filter(b => b.text.trim().length > 0);
        }''')
        print(f"\nAll buttons with text ({len(buttons)}):")
        for b in buttons:
            print(f"  TEXT: {b['text'][:50]}  CLASS: {b['cls'][:80]}")
        
        await browser.close()

if __name__ == "__main__":
    asyncio.run(main())
