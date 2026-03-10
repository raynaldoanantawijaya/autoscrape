import json
import glob
import os

files = glob.glob('hasil_scrape/id_investing_com_*.json')
file = max(files, key=os.path.getctime)

with open(file, 'r', encoding='utf-8') as f:
    data = json.load(f)

print("Technique:", data.get('technique_used', 'Unknown'))
tables = data.get('data', {}).get('tables', [])
if tables:
    print("Total rows:", len(tables[0]['rows']))
else:
    print(data.keys())
    print("No tables found")
