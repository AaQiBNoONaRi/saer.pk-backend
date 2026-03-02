from pymongo import MongoClient
import json

client = MongoClient('mongodb://localhost:27017')
db = client['saerpk_db']
pkgs = list(db['packages'].find({'package_prices': {'$exists': True, '$ne': None}}, {'title': 1, 'package_prices': 1}))
print(f'Found {len(pkgs)} packages')
for p in pkgs:
    pp = p.get('package_prices', {})
    if pp:
        print(f'\nPackage: "{p["title"]}"')
        print(f'All keys: {list(pp.keys())}')
        print(f'All keys repr: {[repr(k) for k in pp.keys()]}')
        for k, v in pp.items():
            print(f'  key={repr(k)} len={len(k)} bytes={k.encode().hex()} selling={v.get("selling") if isinstance(v, dict) else v}')
