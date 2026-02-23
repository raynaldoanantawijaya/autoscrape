# Auto Web Scraper

Auto Web Scraper adalah tools ekstraksi data otomatis yang didesain untuk dijalankan di lingkungan Kali Linux (atau OS berbasis Linux/Windows lainnya). Tools ini berfokus pada penangkapan JSON API dari traffic network dan memiliki kemampuan untuk membypass proteksi website seperti CAPTCHA, hidden variables, dan enkripsi payload.

## Persyaratan
- Python 3.9+
- Lingkungan virtual environment dianjurkan

## 🚀 Cara Instalasi

### 1. Buat Virtual Environment (Penting untuk Kali Linux/Debian)
Gunakan venv untuk menghindari error `externally-managed-environment`:
```bash
python3 -m venv venv
source venv/bin/activate  # Linux/Kali/Mac
# venv\Scripts\activate   # Windows
```

### 2. Install Dependensi & Browser
```bash
pip install -r requirements.txt
playwright install chromium
```

## 📋 Penggunaan

### 🎮 Mode Menu (Interaktif)
Ini adalah cara yang direkomendasikan untuk user di Kali Linux. Jalankan menu terpadu untuk memilih target (Emas, Crypto, Berita, Saham, dll):
```bash
python menu.py
```

### ⚙️ Mode Command Line (Spesifik)
Jalankan script utama untuk target URL tertentu:
```bash
python main.py <TARGET_URL>
```

Contoh:
```bash
python main.py https://jsonplaceholder.typicode.com/posts/
```

### URL Untuk Uji Coba (Testing):
1. **API Publik Ringan:** `https://jsonplaceholder.typicode.com/users`
2. **Web Dengan Inline JSON:** `https://dummyjson.com/products`
3. **Situs Trading (WebSocket / XHR):** `https://id.tradingview.com/`
4. **Proteksi Anti-Bot (Light):** Coba pada situs yang menggunakan infrastruktur CDN/Cloudflare ringan (pastikan sesuai TOS situs).

## Patchright / Camoufox Support
Tools ini mendukung penggunaan **Patchright** (versi Playwright yang di-patch agar tidak terdeteksi) atau **Camoufox**.
Jika Anda ingin perlindungan anti-bot tingkat lanjut (Advanced Bypass):
1. Install [Patchright](https://github.com/kaliiiiiiiiii/patchright).
2. Sesuaikan konfigurasi `USE_PATCHRIGHT = True` dan set `PATCHRIGHT_PATH` pada `config/settings.py`.

## Output
Hasil data berformat JSON akan disimpan di dalam folder `hasil_scrape/`.
File HAR untuk debugging akan tersimpan di `har/`.
Sesi browser tersimpan di `sessions/`.
Log detil akan dicatat di `logs/scrape.log`.
