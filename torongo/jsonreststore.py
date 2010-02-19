'''A Mongo-based server for use with dojo.JsonRestStore

start this server and then access a url like:

http://localhost:8888/grid.html

'''

import tornado.httpserver
import tornado.ioloop
import tornado.web
import pymongo
import pymongo.json_util
import thread_util
import mongo_util
import os
import json
import re
import random
import string
import urllib

def newId():
    '''Use the mongo ID mechanism but convert them to strings'''
    return str(pymongo.objectid.ObjectId())
        
# return a page to kick things off simply to avoid the cross-domain stuff
class MainHandler(mongo_util.MongoRequestHandler):
    def get(self, fname):
        bytes = file(fname, 'r').read()
        self.write(bytes)

def TranslateQuery(obj):
    '''Hack to translate the json coded object into a mongo query'''
    if type(obj) == dict:
        # translate all elements of a dictionary
        for key,val in obj.iteritems():
            obj[key] = TranslateQuery(val)
        return obj
    elif type(obj) == list:
        # translate all elements of a list
        for i,val in enumerate(obj):
            obj[i] = TranslateQuery(val)
        return obj
    elif type(obj) == unicode:
        # check a string to see if it might be a regular expression
        if obj.startswith('/') and obj.endswith('/'):
            try:
                obj = re.compile(obj[1:-1])
            except:
                print 'bad re', obj
        return obj
    else:
        # pass anything else on
        return obj
            
# handle requests without an id
class CollectionHandler(mongo_util.MongoRequestHandler):
    def get(self, db_name, collection_name):
        '''Handle queries'''
        collection = self.mongo_conn[db_name][collection_name]

        # check for a query
        spec = {}
        for key,val in self.request.arguments.iteritems():
            q = val[0]
            if key == 'mongoquery':
                # pass an arbitrary query into mongo, the query is json encoded and
                # then url quoted
                
                # remove url quoting
                q = urllib.unquote(q)
                # convert from json
                q = json.loads(q)
                # convert to format expected by mongo
                spec = TranslateQuery(q)
                break
            if '*' in q or '?' in q:
                q = q.replace('*', '.*').replace('?', '.?')
                q = re.compile('^' + q + '$')
            spec[key] = q

        cursor = collection.find(spec)

        # check for a sorting request
        # should handle multiple sorts like sort(-length,+letters)
        s = re.compile(r'sort\(([^)]+)\)').search(self.request.query)
        if s:
            sortSpec = [ (key, {'+':pymongo.ASCENDING, '-':pymongo.DESCENDING}[direction])
                         for direction,key in re.findall(r'([+-])(\w+)', s.group(1)) ]
            cursor = cursor.sort(sortSpec)


        Nitems = cursor.count()

        # see how much we are to send
        r = re.compile(r'items=(\d+)-(\d+)').match(self.request.headers.get('Range', ''))
        if r:
            start = int(r.group(1))
            stop = int(r.group(2))
            cursor = cursor.skip(start).limit(stop-start+1)
        else:
            start = 0
            stop = Nitems

        # send the result
        self.set_header('Content-range', 'items %d-%d/%d' % (start,stop,Nitems))
        s = json.dumps(list(cursor), default=pymongo.json_util.default)
        self.set_header('Content-length', len(s))
        self.set_header('Content-type', 'application/json')
        self.write(s)

    def post(self, db_name, collection_name):
        '''Create a new item and return the single item not an array'''
        collection = self.mongo_conn[db_name][collection_name]

        item = json.loads(self.request.body, object_hook=pymongo.json_util.object_hook)

        id = newId()
        item['_id'] = id
        collection.insert(item)
        # this path should get encoded only one place, fix this
        self.set_header('Location', '/data/%s/%s/%s' % (db_name, collection_name, id))
        s = json.dumps(item, default=pymongo.json_util.default)
        self.set_header('Content-length', len(s))
        self.set_header('Content-type', 'application/json')
        self.write(s)


# handle requests with an id
class ItemHandler(mongo_util.MongoRequestHandler):
    def get(self, db_name, collection_name, id):
        '''Handle requests for single items'''
        collection = self.mongo_conn[db_name][collection_name]
        
        item = collection[{'_id':id}]
        s = json.dumps(item, default=pymongo.json_util.default)
        self.set_header('Content-length', len(s))
        self.set_header('Content-type', 'application/json')
        self.write(s)

    def put(self, db_name, collection_name, id):
        '''update an item after an edit, no response?'''
        collection = self.mongo_conn[db_name][collection_name]
        item = json.loads(self.request.body, object_hook=pymongo.json_util.object_hook)
        collection.save(item)

    def delete(self, db_name, collection_name, id):
        '''Delete an item, what should I return?'''
        collection = self.mongo_conn[db_name][collection_name]
        collection.remove( { '_id' : id }, True )

def run_server():
    settings = {
        'debug': True,
        'thread_count': 5,
    }
    application = mongo_util.MongoApplication([
        (r"/(\w+\.html)", MainHandler),
        # why do we need this optional undefined string, explorer seems to be adding it
        # workaround for the bug fixed (we think) by http://trac.dojotoolkit.org/changeset/21041
        # was
        (r"/data/([a-z][a-z0-9]*)/([a-z][a-z0-9]*)/(?:undefined)?$", CollectionHandler),
        (r"/data/([a-z][a-z0-9]*)/([a-z][a-z0-9]*)/(?:undefined)?([a-f0-9]+)", ItemHandler),
    ], **settings)
    http_server = tornado.httpserver.HTTPServer(application)
    http_server.listen(8888)
    tornado.ioloop.IOLoop.instance().start()

if __name__ == "__main__":
    import sys
    # start with an argument indicating how many items you want in the DB
    if len(sys.argv) > 1:
        import string, random
        n = int(sys.argv[1])
        docs = [ { 'label' : ''.join(random.sample(string.lowercase, random.randint(2,9))),
                   'value': i,
                   '_id': newId() }
                 for i in range(n) ]
        for doc in docs:
            doc['length'] = len(doc['label'])
            doc['letters'] = sorted(list(doc['label']))
            
        connection = pymongo.Connection()
        db = connection.test
        db.drop_collection('posts')
        db.posts.insert(docs)
    run_server()

