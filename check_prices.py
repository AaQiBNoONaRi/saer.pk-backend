from pymongo import MongoClient
client = MongoClient('mongodb://localhost:27017')
db = client['saerpk_db']
pkgs = list(db['packages'].find({'package_prices': {'$exists': True, '$ne': None}}, {'title': 1, 'package_prices': 1}))
print(f'Found {len(pkgs)} packages')
for p in pkgs:
    pp = p.get('package_prices', {})
    if pp:
        for k, v in pp.items():
            print(f'  Package "{p["title"]}" key repr={repr(k)} val={v}')
