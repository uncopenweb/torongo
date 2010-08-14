'''Initialize the _Admin db for testing'''

import pymongo
import json

def newId():
    '''Use the mongo ID mechanism but convert them to strings'''
    # Not sure why I prefer the strings, they sure look better than the objects
    return str(pymongo.objectid.ObjectId())

conn = pymongo.Connection('localhost', port=27000)

# setup the Developers list
db = conn['_Admin']
db.drop_collection('Developers')
cl = db['Developers']

for id in [ 'gary.bishop.unc@gmail.com',
            'duncan.lewis11@gmail.com',
            'parente@gmail.com',
          ]:
    item = { 'user': id, '_id': newId() }
    cl.insert(item)

# rolodex schema
rolodex = {
    'type': 'object',
    'description': 'A rolodex object',
    'properties': {
        '_id': {
            'type': 'string',
            'maxLength': 64,
        },
        'firstName': {
            'type': 'string',
            'maxLength': 25,
        },
        'lastName': {
            'type': 'string',
            'maxLength': 25,
        },
    },
    'additionalProperties': False,
}

status = {
    'type': 'object',
    'description': 'A status object',
    'properties': {
        '_id': {
            'type': 'string',
            'maxLength': 64,
        },
        'dt': { 'type': 'string',
                'maxLength': 25 },
        'from': { 'type': 'string',
                  'maxLength': 40 }
    },
    'additionalProperties': False,
}

test = {
    'type': 'object',
    'properties': {
        '_id': {
            'type': 'string',
            'maxLength': 64,
        },
        'word': { 'type': 'string', 'maxLength': 25 },
        'value': { 'type': 'integer' },
    },
    'additionalProperties': False,
}

AccessUsersSchema = json.load(file('AccessUsersSchema.json', 'r'))
AccessModesSchema = json.load(file('AccessModesSchema.json', 'r'))

# setup the Schemas
db.drop_collection('Schemas')
cl = db['Schemas']
cl.insert( { 'db': 'catalog', 'collection': 'rolodex', '_id': newId(),
             'schema': rolodex } )
cl.insert( { 'db': 'catalog', 'collection': 'status', '_id': newId(),
             'schema': status } )
cl.insert( { 'db': 'catalog', 'collection': 'AccessUsers', '_id': newId(),
             'schema': AccessUsersSchema } )
cl.insert( { 'db': 'catalog', 'collection': 'AccessModes', '_id': newId(),
             'schema': AccessModesSchema } )
cl.insert( { 'db': 'test', 'collection': 'test', '_id': newId(),
             'schema': test });


# setup roles
db = conn['catalog']
db.drop_collection('AccessUsers')
cl = db['AccessUsers']
cl.insert({ 'user': 'gary.bishop.unc@gmail.com', 'role': 'admin', '_id': newId() })

db.drop_collection('AccessModes')
cl = db['AccessModes']
cl.insert({ 'role': 'admin', 'collection': 'rolodex', 'permission': 'crudDL', '_id': newId() })
cl.insert({ 'role': 'anonymous', 'collection': 'rolodex', 'permission': 'rc', '_id': newId() })
cl.insert({ 'role': '_ANY_', 'collection': 'status', 'permission': 'c', '_id': newId() })
cl.insert({ 'role': 'admin', 'collection': 'AccessUsers', 'permission': 'crud', '_id': newId() })
cl.insert({ 'role': 'admin', 'collection': 'AccessModes', 'permission': 'crud', '_id': newId() })

db = conn['media']
db.drop_collection('AccessUsers')
cl = db['AccessUsers']
cl.insert({ 'user': 'gary.bishop.unc@gmail.com', 'role': 'admin', '_id': newId() })

db.drop_collection('AccessModes')
cl = db['AccessModes']
cl.insert({ 'role': 'admin', 'collection': 'audio', 'permission': 'crudDLU', '_id': newId() })
cl.insert({ 'role': 'admin', 'collection': 'image', 'permission': 'crudDLU', '_id': newId() })
cl.insert({ 'role': 'identified', 'collection': 'audio', 'permission': 'rU', '_id': newId() })
cl.insert({ 'role': 'identified', 'collection': 'image', 'permission': 'rU', '_id': newId() })

# roles for test
db = conn['test']
db.drop_collection('AccessUsers')
cl = db['AccessUsers']
cl.insert({ 'user': 'gary.bishop.unc@gmail.com', 'role': 'admin', '_id': newId() })
cl.insert({ 'user': 'anonymous', 'role': 'anonymous', '_id': newId() })
db.drop_collection('AccessModes')
cl = db['AccessModes']
cl.insert({ 'role': 'admin', 'collection': '_ANY_', 'permission': 'crudDL', '_id': newId() })
cl.insert({ 'role': 'anonymous', 'collection': 'test', 'permission': 'r', '_id': newId() })

# roles for bigwords
db = conn['BigWords']
db.drop_collection('AccessUsers')
cl = db['AccessUsers']
cl.insert({ 'user': 'gary.bishop.unc@gmail.com', 'role': 'admin', '_id': newId() })
cl.insert({ 'user': 'duncan.lewis11@gmail.com', 'role': 'admin', '_id': newId() })
cl.insert({ 'user': 'anonymous', 'role': 'anonymous', '_id': newId() })
db.drop_collection('AccessModes')
cl = db['AccessModes']
cl.insert({ 'role': 'admin', 'collection': '_ANY_', 'permission': 'crudDL', '_id': newId() })
cl.insert({ 'role': 'anonymous', 'collection': '_ANY_', 'permission': 'crud', '_id': newId() })

# clean out the default collections
db.drop_collection('rolodex')
db.drop_collection('status')
