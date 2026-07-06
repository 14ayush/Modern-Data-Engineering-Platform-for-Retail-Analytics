from pathlib import Path
import pg8000
import ssl
from urllib.parse import urlparse
import csv
from decimal import Decimal

env_path = Path('.env')
if not env_path.exists():
    raise FileNotFoundError('.env file not found')

conn_str = None
for line in env_path.read_text().splitlines():
    if line.strip().startswith('POSTGRE_CONNECTION_KEY='):
        conn_str = line.split('=', 1)[1].strip()
        break

if not conn_str:
    raise ValueError('POSTGRE_CONNECTION_KEY not found in .env')

url = urlparse(conn_str)
params = {
    'host': url.hostname,
    'port': url.port,
    'database': url.path.lstrip('/'),
    'user': url.username,
    'password': url.password,
}
ctx = ssl.create_default_context()
ctx.check_hostname = False
ctx.verify_mode = ssl.CERT_NONE
params['ssl_context'] = ctx

data_dir = Path('Dataset/data')
if not data_dir.exists():
    raise FileNotFoundError('Dataset/data folder not found')

def convert_value(col, val):
    if val == '':
        return None
    low = col.lower()
    try:
        if low.endswith('_id') or low in ('id', 'quantity'):
            return int(val)
        if 'price' in low or 'amount' in low or 'total' in low or low == 'salary':
            return Decimal(val)
    except Exception:
        pass
    return val

conn = pg8000.connect(**params)
try:
    cur = conn.cursor()
    for csv_path in sorted(data_dir.glob('*.csv')):
        table = csv_path.stem
        with csv_path.open(newline='', encoding='utf-8') as f:
            reader = csv.reader(f)
            headers = next(reader)
            cols = ','.join(headers)
            placeholders = ','.join(['%s'] * len(headers))
            insert_sql = f'INSERT INTO raw.{table} ({cols}) VALUES ({placeholders});'
            count = 0
            for row in reader:
                vals = [convert_value(col, v) for col, v in zip(headers, row)]
                try:
                    cur.execute(insert_sql, tuple(vals))
                    count += 1
                except Exception as e:
                    print(f'Error inserting into {table}:', e)
    conn.commit()
    # Summary
    cur.execute("SELECT table_name FROM information_schema.tables WHERE table_schema='raw' ORDER BY table_name;")
    rows = cur.fetchall()
    print('Loaded CSVs. Tables in schema raw:', [r[0] for r in rows])
finally:
    conn.close()
