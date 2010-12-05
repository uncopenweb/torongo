'''Initialize the Admin db for testing'''

import pymongo
import json
import access
import optparse
import sys
import re

parser = optparse.OptionParser(usage='usage: %prog [options] mongohost mongoport')
parser.add_option("-r", "--reset", dest="reset", action='store_true', default=False,
    help="reset Admin collections (irreversible!)")
(options, args) = parser.parse_args()
if len(args) != 2:
    parser.error('you must provide the hostname and port number for mongo')

host = args[0]
port = int(args[1])

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

conn = pymongo.Connection(host, port=port)

db = conn[access.AdminDbName]

collections = db.collection_names()

# setup users
if options.reset or 'Developers' not in collections:
    db.drop_collection('Developers')
    userRoles = json.load(file('developers.json', 'r'))
    DE = db['Developers']
    for userRole in userRoles:
        insert(DE, userRole)
else:
    print 'not overwriting Developers'
    
# setup users
if options.reset or 'AccessUsers' not in collections:
    db.drop_collection('AccessUsers')
    userRoles = json.load(file('users.json', 'r'))
    AU = db['AccessUsers']
    for userRole in userRoles:
        insert(AU, userRole)
else:
    print 'not overwriting AccessUsers'
    
# setup modes
if options.reset or 'AccessModes' not in collections:
    db.drop_collection('AccessModes')
    modes = json.load(file('modes.json', 'r'))
    AM = db['AccessModes']
    for mode in modes:
        insert(AM, mode)
else:
    print 'not overwriting AccessModes'

# rolodex schema
rolodex = '''
{
    "type": "object",
    "description": "A rolodex object",
    "properties": {
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
        "word": { "type": "string", "maxLength": 25 },
        "value": { "type": "integer" }
    },
    "additionalProperties": false
}'''

AccessUsersSchema = file('AccessUsersSchema.json', 'r').read()
AccessModesSchema = file('AccessModesSchema.json', 'r').read()
DevelopersSchema = file('DevelopersSchema.json', 'r').read()

def compact(j):
    return json.loads(j)

# setup the Schemas
if options.reset or 'Schemas' not in collections:
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
else:
    print 'not overwriting Schemas'


