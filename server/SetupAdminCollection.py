'''Initialize the Admin db for testing'''

import pymongo
import json
import access
import optparse
import sys
import re

def newId():
    '''Use the mongo ID mechanism but convert them to strings'''
    return str(pymongo.objectid.ObjectId())
    
def insert(collection, item):
    if '_id' not in item:
        item['_id'] = newId()
    collection.insert(item, safe=True)
    
def replace(collection, item, **spec):
    if not spec:
        return insert(collection, item)
        
    old = collection.find(spec)
    count = old.count()
    if count > 1:
        raise 'duplicates for %s' % spec
    if count == 0:
        return insert(collection, item)
    collection.update({'_id': old['_id']}, item, safe=True);

conn = pymongo.Connection('localhost', port=27000)

db = conn[access.AdminDbName]

# setup users
db.drop_collection('Developers')
userRoles = json.load(file('developers.json', 'r'))
DE = db['Developers']
for userRole in userRoles:
    insert(DE, userRole)
    
# setup users
db.drop_collection('AccessUsers')
userRoles = json.load(file('users.json', 'r'))
AU = db['AccessUsers']
for userRole in userRoles:
    insert(AU, userRole)
    
# setup modes
db.drop_collection('AccessModes')
modes = json.load(file('modes.json', 'r'))
AM = db['AccessModes']
for mode in modes:
    insert(AM, mode)

# rolodex schema
rolodex = '''
{
    "type": "object",
    "description": "A rolodex object",
    "properties": {
        "_id": {
            "type": "string",
            "maxLength": 64
        },
        "firstName": {
            "type": "string",
            "maxLength": 25
        },
        "lastName": {
            "type": "string",
            "maxLength": 25
        }
    },
    "additionalProperties": false
}
'''

status = '''{
    "type": "object",
    "description": "A status object",
    "properties": {
        "_id": {
            "type": "string",
            "maxLength": 64
        },
        "dt": { "type": "string",
                "maxLength": 64 },
        "from": { "type": "string",
                  "maxLength": 64 }
    },
    "additionalProperties": false
}'''

test = '''{
    "type": "object",
    "properties": {
        "_id": {
            "type": "string",
            "maxLength": 64
        },
        "word": { "type": "string", "maxLength": 25 },
        "value": { "type": "integer" }
    },
    "additionalProperties": false
}'''

AccessUsersSchema = file('AccessUsersSchema.json', 'r').read()
AccessModesSchema = file('AccessModesSchema.json', 'r').read()
DevelopersSchema = file('DevelopersSchema.json', 'r').read()

def compact(j):
    try:
        json.loads(j)
    except:
        print 'bad json'
        raise
    return j # re.sub(r'\s+', ' ', j)

# setup the Schemas
db.drop_collection('Schemas')
sc = db['Schemas']
insert(sc, { 'database': 'catalog', 'collection': 'rolodex',
             'schema': compact(rolodex) } )
insert(sc, { 'database': 'catalog', 'collection': 'status',
             'schema': compact(status) } )
insert(sc, { 'database': 'Admin', 'collection': 'AccessUsers',
             'schema': compact(AccessUsersSchema) } )
insert(sc, { 'database': 'Admin', 'collection': 'AccessModes',
             'schema': compact(AccessModesSchema) } )
insert(sc, { 'database': 'Admin', 'collection': 'Developers',
             'schema': compact(DevelopersSchema) } )
insert(sc, { 'database': 'test', 'collection': 'test',
             'schema': compact(test) });


