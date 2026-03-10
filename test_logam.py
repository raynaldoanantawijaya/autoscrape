import requests
from bs4 import BeautifulSoup
import urllib3
urllib3.disable_warnings()

headers = {'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36'}
r = requests.get('https://www.logammulia.com/id/harga-emas-hari-ini', headers=headers, verify=False)
soup = BeautifulSoup(r.text, 'html.parser')
for i, table in enumerate(soup.find_all('table')):
    data_trs = table.find('tbody').find_all('tr') if table.find('tbody') else table.find_all('tr')
    print(f'Table {i} rows: {len(data_trs)}')
    for j, tr in enumerate(data_trs[:5]):
        print(f'  Row {j}: {[td.get_text(strip=True) for td in tr.find_all(["td", "th"])]}')
    if len(data_trs) > 5:
        print('  ...')
        for j, tr in enumerate(data_trs[-5:]):
            print(f'  Row {len(data_trs)-5+j}: {[td.get_text(strip=True) for td in tr.find_all(["td", "th"])]}')
