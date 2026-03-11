import requests
h = {"User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36", "Accept": "application/json"}
try:
    r = requests.get("https://www.idx.co.id/primary/ListedCompany/GetCompanyProfiles?start=0&length=9999", headers=h, timeout=10)
    print("Status:", r.status_code)
    try:
        data = r.json()
        print("Data len:", len(data.get("data", [])))
    except Exception as e:
        print("Not JSON:", r.text[:200])
except Exception as e:
    print("Error:", e)
