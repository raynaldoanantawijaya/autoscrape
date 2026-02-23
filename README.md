# Auto Web Scraper

Auto Web Scraper adalah tools ekstraksi data otomatis yang didesain untuk dijalankan di lingkungan Kali Linux (atau OS berbasis Linux/Windows lainnya). Tools ini berfokus pada penangkapan JSON API dari traffic network dan memiliki kemampuan untuk membypass proteksi website seperti CAPTCHA, hidden variables, dan enkripsi payload.

## Persyaratan
- Python 3.9+
- Lingkungan virtual environment dianjurkan

## Cara Instalasi

1. **Buat Virtual Environment (Sangat disarankan):**
   ```bash
   python3 -m venv venv
   source venv/bin/activate  # Di Linux/Mac
   # atau
   # venv\Scripts\activate   # Di Windows
   ```

2. **Install Dependensi:**
   ```bash
   pip install -r requirements.txt
   ```

3. **Install Browser Playwright:**
   ```bash
   python -m playwright install --with-deps chromium
   ```

## Konfigurasi
Sebelum menjalankan, Anda dapat menyalin file template konfigurasi jika belum ada:
```bash
cp config/settings.py.example config/settings.py
```
Sesuaikan parameter di `config/settings.py` seperti tipe target keyword, penggunaan proxy, dan mode headless/berjalan tanpa UI.

### Menambahkan Proxy
Jika Anda mengaktifkan `USE_PROXY = True` di `settings.py`, Anda dapat mendaftarkan list proxy dengan mengisi file `config/proxies.txt`. Format yang didukung:
- `http://ip:port`
- `http://username:password@ip:port`
- `socks5://...`

Sistem otomatis melakukan rotasi setiap *N* request berdasarkan string yang Anda tentukan di `ROTATE_PROXY_EVERY`.

### Menambahkan User-Agent
Daftar user-agent per penyamaran telah tersedia di `config/user_agents.txt`. Tambahkan string identitas browser web terbaru (Chrome/Firefox/Safari/Edge) baris per baris. Fitur di `interaction.py` secara langsung akan merotasi headers ini kepada server target.

## Penggunaan
Jalankan script utama dengan memasukkan target URL:
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
