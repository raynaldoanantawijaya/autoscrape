import logging

logger = logging.getLogger(__name__)

def apply_stealth(context):
    """
    Menyuntikkan script untuk menyamarkan indikator otomatisasi (webdriver).
    Playwright Context Init Script.
    """
    logger.debug("Menerapkan Stealth mode script ke browser context...")
    
    script = """
    // Override navigator.webdriver
    Object.defineProperty(navigator, 'webdriver', {
        get: () => undefined
    });
    
    // Mock window.chrome if not exists (berguna untuk headless)
    if (!window.chrome) {
        window.chrome = {
            runtime: {}
        };
    }
    
    // Override permissions fallback
    const originalQuery = window.navigator.permissions.query;
    window.navigator.permissions.query = (parameters) => (
        parameters.name === 'notifications' ?
            Promise.resolve({ state: Notification.permission }) :
            originalQuery(parameters)
    );
    
    // Mock Plugin list agar tidak terdeteksi kosong
    Object.defineProperty(navigator, 'plugins', {
        get: () => [
            {
                0: {type: "application/x-google-chrome-pdf", suffixes: "pdf", description: "Portable Document Format", enabledPlugin: Plugin},
                description: "Portable Document Format",
                filename: "internal-pdf-viewer",
                length: 1,
                name: "Chrome PDF Plugin"
            }
        ]
    });
    
    // Mock WebGL Vendor
    const getParameter = WebGLRenderingContext.getParameter;
    WebGLRenderingContext.prototype.getParameter = function(parameter) {
        if (parameter === 37445) { // UNMASKED_VENDOR_WEBGL
            return 'Intel Inc.';
        }
        if (parameter === 37446) { // UNMASKED_RENDERER_WEBGL
            return 'Intel Iris OpenGL Engine';
        }
        return getParameter.apply(this, arguments);
    };
    """
    
    context.add_init_script(script)


def detect_captcha(html_content):
    """
    Pengecekan simpel mendeteksi keberadaan elemen CAPTCHA populer dari HTML.
    Bisa diekstensi untuk memanggil 2captcha API jika perlu (fallback module).
    """
    if not html_content:
        return False
        
    html_lower = html_content.lower()
    
    indicators = [
        'g-recaptcha',
        'hcaptcha',
        'cf-turnstile',
        'arkose',
        'funcaptcha'
    ]
    
    for indicator in indicators:
        if indicator in html_lower:
            logger.warning(f"Terindikasi adanya CAPTCHA di Halaman!: '{indicator}'")
            return indicator
            
    return False
