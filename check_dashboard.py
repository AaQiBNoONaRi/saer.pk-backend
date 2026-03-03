from pymongo import MongoClient
client = MongoClient('mongodb://localhost:27017')
db = client['saerpk_db']

# Check booking_status values used across all booking collections
for col in ['umrah_bookings', 'custom_bookings', 'ticket_bookings']:
    statuses = db[col].distinct('booking_status')
    count = db[col].count_documents({})
    print(f'{col}: total={count}, statuses={statuses}')

# Check employee collection structure
emp = db['employees'].find_one({}, {'_id':1,'branch_id':1,'name':1,'status':1})
print(f'\nEmployee sample: {emp}')

# Check payments structure
pay = db['payments'].find_one({}, {'_id':0,'status':1,'sender_role':1,'branch_id':1,'agency_id':1,'amount':1})
print(f'\nPayment sample: {pay}')
