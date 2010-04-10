'''A Mongo-based server for use with dojo.JsonRestStore

start this server and then access a url like:

http://localhost:8888/grid.html

'''

import tornado.httpserver
import tornado.ioloop
import tornado.web
from tornado.web import HTTPError
import tornado.auth
#import access
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
    # Not sure why I prefer the strings, they sure look better than the objects
    return str(pymongo.objectid.ObjectId())

class BaseHandler(mongo_util.MongoRequestHandler):
    '''Manage secure access'''
    def get_current_user(self):
        user_json = self.get_secure_cookie("user")
        if not user_json:
            print 'get current user', None
            return None
        result = tornado.escape.json_decode(user_json)
        print 'get_current_user', result
        return result

class AuthHandler(BaseHandler, tornado.auth.GoogleMixin):
    '''Handle authentication using Google OpenID'''
    @tornado.web.asynchronous
    def get(self, id):
        print 'auth get', id
        if not id:
            # start auth from Google
            if self.get_argument("openid.mode", None):
                print 'calling get_authenticed_user'
                self.get_authenticated_user(self.async_callback(self._on_auth))
                return
            print 'calling authenticate_redirect'
            self.authenticate_redirect()
        else:
            print 'sending response'
            # wrap up the authorization
            resp = '''<html><head></head><body onload="window.opener.handleOpenIDResponse('%s');window.close();">This page is after login is complete.</body></html>''' % id[1:]
            self.write(resp)
            self.finish()

    def _on_auth(self, user):
        print 'on_auth', user
        if user:
            self.set_secure_cookie("user", tornado.escape.json_encode(user))
            print 'set the cookie'
            self.redirect("/data/login-ok")
        else:
            self.redirect("/data/login-failed")

# return a page to kick things off simply to avoid the cross-domain stuff
# we'll replace this with mod_proxy or nginx
class MainHandler(BaseHandler):
    def get(self, fname):
        bytes = file(fname, 'r').read()
        self.write(bytes)

def TranslateQuery(obj):
    '''Hack to translate the json coded object into a mongo query'''
    # some validation might be done in here as well
    
    if type(obj) == dict:
        # translate all elements of a dictionary
        for key,val in obj.iteritems():
            obj[key] = TranslateQuery(val)
        return obj
    elif type(obj) == list:
        # translate all elements of a list, I don't think this happens but doesn't cost much
        for i,val in enumerate(obj):
            obj[i] = TranslateQuery(val)
        return obj
    elif type(obj) == unicode:
        # check a string to see if it might be a regular expression
        if obj.startswith('/') and obj.endswith('/'):
            try:
                obj = re.compile(obj[1:-1])
            except re.error:
                raise HTTPError(400, 'bad query')
        return obj
    else:
        # pass anything else on
        return obj
            
# handle requests without an id
class CollectionHandler(BaseHandler):
    def get(self, db_name, collection_name):
        '''Handle queries'''
        print 'get', db_name, collection_name
        
#        acc =  access.getAccess(db_name, collection_name, self, 'read')
        
        collection = self.mongo_conn[db_name][collection_name]

        # check for a query
        spec = {}
        for key,val in self.request.arguments.iteritems():
            # validate the query key
            if not re.match(r'\w+', key):
                raise HTTPError(400, 'bad query')
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

            # handle the dojo glob style strings
            if '*' in q or '?' in q:
                # protect python re special characters
                q = re.sub(r'([][.+(){}|^\\])', r'\\\1', q)
                # convert * to .* and ? to .?
                q = re.sub(r'([*?])', r'.\1', q)
                try:
                    q = re.compile('^' + q + '$')
                except re.error:
                    raise HTTPError(400, 'bad query')
            spec[key] = q

        #spec = acc.validateQuery(spec)
        cursor = collection.find(spec) #, acc.fields)

        # check for a sorting request
        # should handle multiple sorts like sort(-length,+letters)
        s = re.compile(r'sort\(([^)]+)\)').search(self.request.query)
        if s:
            sortSpec = []
            for direction, key in re.findall(r'([+-])(\w+)', s.group(1)):
                #if acc.schema and key not in acc.schema:
                #    raise HTTPError(400, 'key')
                sortSpec.append((key, {'+':pymongo.ASCENDING, '-':pymongo.DESCENDING}[direction]))
            #sortSpec = acc.validateSort(sortSpec)
            cursor = cursor.sort(sortSpec)

        Nitems = cursor.count()

        # see how much we are to send
        r = re.compile(r'items=(\d+)-(\d+)').match(self.request.headers.get('Range', ''))
        if r:
            start = int(r.group(1))
            stop = int(r.group(2))
        else:
            start = 0
            stop = min(10, Nitems)
        cursor = cursor.skip(start).limit(stop-start+1)

        # send the result
        self.set_header('Content-range', 'items %d-%d/%d' % (start,stop,Nitems))
        s = json.dumps(list(cursor), default=pymongo.json_util.default)
        self.set_header('Content-length', len(s))
        self.set_header('Content-type', 'application/json')
        self.write(s)

    def post(self, db_name, collection_name):
        '''Create a new item and return the single item not an array'''
        #acc =  access.getAccess(db_name, collection_name, self, 'create')
        collection = self.mongo_conn[db_name][collection_name]

        item = json.loads(self.request.body, object_hook=pymongo.json_util.object_hook)
        #item = acc.validateFields(item)

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
class ItemHandler(BaseHandler):
    def get(self, db_name, collection_name, id):
        '''Handle requests for single items'''
        #acc =  access.getAccess(db_name, collection_name, self, 'read')
        collection = self.mongo_conn[db_name][collection_name]
        
        item = collection.find_one({'_id':id})#, acc.fields)
        #item = acc.validateRead(item)
        
        s = json.dumps(item, default=pymongo.json_util.default)
        self.set_header('Content-length', len(s))
        self.set_header('Content-type', 'application/json')
        self.write(s)

    def put(self, db_name, collection_name, id):
        '''update an item after an edit, no response?'''
        #acc =  access.getAccess(db_name, collection_name, self, 'update')
        collection = self.mongo_conn[db_name][collection_name]
        new_item = json.loads(self.request.body, object_hook=pymongo.json_util.object_hook)
        #old_item = collection.find_one({'_id':id}, acc.fields)
        #new_item = acc.validateUpdate(old_item, new_item)
        collection.save(new_item)

    def delete(self, db_name, collection_name, id):
        '''Delete an item, what should I return?'''
        #acc = access.getAccess(db_name, collection_name, self, 'delete')
        collection = self.mongo_conn[db_name][collection_name]
        #old_item = collection[{'_id':id}]
        #acc.validateDelete(old_item)
        collection.remove( { '_id' : id }, True )

def run_server():
    settings = {
        'cookie_secret':"480fae4e819d28eeb1cc9f84dc471bad",
        'debug': True,
        'thread_count': 5,
    }
    application = mongo_util.MongoApplication([
        (r"/(\w+\.html)", MainHandler),
        # why do we need this optional undefined string, explorer seems to be adding it
        # workaround for the bug fixed (we think) by http://trac.dojotoolkit.org/changeset/21041
        # was
        (r"/data/([a-zA-Z][a-zA-Z0-9]*)/([a-zA-Z][a-zA-Z0-9]*)/(?:undefined)?$", CollectionHandler),
        (r"/data/([a-zA-Z][a-zA-Z0-9]*)/([a-zA-Z][a-zA-Z0-9]*)/(?:undefined)?([a-f0-9]+)", ItemHandler),
        (r"/data/login(.*)", AuthHandler),
    ], **settings)
    http_server = tornado.httpserver.HTTPServer(application)
    http_server.listen(8887)
    tornado.ioloop.IOLoop.instance().start()

if __name__ == "__main__":
    import sys
    print 'start server'
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

