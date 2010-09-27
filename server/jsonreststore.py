'''
A Mongo-based server for use with dojox.data.JsonRestStore.

:copyright: Gary Bishop 2010
:license: BSD
'''
import tornado.httpserver
import tornado.ioloop
import tornado.web
from tornado.web import HTTPError
import pymongo
import pymongo.json_util

import mongo_util
import os
import json
import re
import string
import random
import urllib
import optparse
import access
import logging
import myLogging
import time
import sys

def newId():
    '''Use the mongo ID mechanism but convert them to strings'''
    # Not sure why I prefer the strings, they sure look better than the objects
    return str(pymongo.objectid.ObjectId())

JSRE = re.compile(r'^/(.*)/([igm]*)$')
DojoGlob = re.compile(r'[?*]')

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
        m = JSRE.match(obj)
        if m:
            flags = 0
            for letter in m.group(2):
                flags |= { 'm': re.M,
                           'g': re.G,
                           'i': re.I } [ letter ]
            try:
                obj = re.compile(m.group(1), flags)
            except re.error:
                raise HTTPError(400, 'bad query')

        # check for globbing in the string
        elif DojoGlob.search(obj):
            # protect python re special characters
            q = re.sub(r'([][.+(){}|^\\])', r'\\\1', obj)
            # convert * to .* and ? to .?
            q = re.sub(r'([*?])', r'.\1', q)
            # anchor it
            q = '^' + q + '$'
            # try to compile it
            try:
                obj = re.compile(q)
            except re.error:
                pass # just pass the original string along if it won't compile

        return obj
    else:
        # pass anything else on
        return obj
        
def RestrictQuery(query):
    restricted = {}
    for key,value in query.iteritems():
        if key.startswith('$'):
            continue
        if type(value) in [ unicode, int, float ]:
            restricted[key] = value
    return restricted
        
def doQuery(item, spec):
    '''simulate a mongo query on the collection names'''
    if not spec:
        return True
    if type(spec) == dict:
        for key,value in spec.iteritems():
            if key not in item:
                return False
            if value == item[key] or hasattr(value, 'search') and value.search(unicode(item[key])):
                continue
            else:
                return False
    return True

# handle requests with only a db name
class DatabaseHandler(access.BaseHandler):
    def get(self, db_name, collection_name):
        '''Handle queries for collection names'''
        if collection_name:
            raise HTTPError(400, 'db does not exist')
            
        if not self.checkAccessKey(db_name, '*', access.Read):
            raise HTTPError(403, 'listing not permitted (%s)' % self.checkAccessKeyMessage)
        db = self.mongo_conn[db_name]
        names = db.collection_names()
        result = [ { "_id": name, "url": "/data/%s/%s/" % (db_name, name) }
                   for name in names
                   if name != 'system.indexes' ]

        # handle query parameters
        spec = {}
        if 'mq' in self.request.arguments:
            q = self.request.arguments['mq'][0]
            # remove url quoting
            q = urllib.unquote(q)
            # convert from json
            try:
                q = json.loads(q)
            except ValueError, e:
                raise HTTPError(400, unicode(e));
            # convert to format expected by mongo
            spec = TranslateQuery(q)

        # simulate what mongo would do to select the names...
        result = [ item for item in result if doQuery(item, spec) ]

        # see how much we are to send
        Nitems = len(result)
        r = re.compile(r'items=(\d+)-(\d+)').match(self.request.headers.get('Range', ''))
        if r:
            start = int(r.group(1))
            stop = int(r.group(2))
        else:
            start = 0
            stop = Nitems
        result = result[start:stop+1]
        
        # send the result
        self.set_header('Content-range', 'items %d-%d/%d' % (start,stop,Nitems))
        s = json.dumps(result, default=pymongo.json_util.default)
        s = s.replace('"_ref":', '"$ref":') # restore $ref
        self.set_header('Content-length', len(s))
        self.set_header('Content-type', 'application/json')
        self.write(s)

    def delete(self, db_name, collection_name):
        '''Drop the collection'''
        if not self.checkAccessKey(db_name, '*', access.Delete):
            raise HTTPError(403, 'drop collection not permitted (%s)' % self.checkAccessKeyMessage)
        self.mongo_conn[db_name].drop_collection(collection_name)
        
# handle requests without an id
class CollectionHandler(access.BaseHandler):
    @tornado.web.asynchronous
    def get(self, db_name, collection_name):
        '''Handle queries'''
        readMode = self.checkAccessKey(db_name, collection_name, access.Read)
        restrict = readMode == access.RestrictedRead
        if not readMode:
            raise HTTPError(403, 'read not permitted (%s)' % self.checkAccessKeyMessage)
        
        collection = self.mongo_conn[db_name][collection_name]

        # check for a query
        findSpec = {}
        if 'mq' in self.request.arguments:
            q = self.request.arguments['mq'][0]
            # pass an arbitrary query into mongo, the query is json encoded and
            # then url quoted

            # remove url quoting
            q = urllib.unquote(q)
            # convert from json
            try:
                q = json.loads(q)
            except ValueError, e:
                raise HTTPError(400, unicode(e));
            # convert to format expected by mongo
            findSpec = TranslateQuery(q)
            if restrict:
                findSpec = RestrictQuery(findSpec)

        # check for a sorting request
        sortSpec = []
        if not restrict and 'ms' in self.request.arguments:
            for s in self.request.arguments['ms'][0].split(','):
                sortSpec.append((s[1:], { '+':pymongo.ASCENDING, '-':pymongo.DESCENDING }[s[0]]))

        # see how much we are to send
        r = re.compile(r'items=(\d+)-(\d+)').match(self.request.headers.get('Range', ''))
        if not restrict and r:
            start = int(r.group(1))
            stop = int(r.group(2))
        else:
            start = 0
            stop = None
            
        # hand off to the worker thread to do the possibly slow db access
        self.run_async(self._callback, self._worker, collection, findSpec, sortSpec, start, stop,
                       restrict)

    def _worker(self, collection, findSpec, sortSpec, start, stop, restrict):
        '''Do just the db query in a thread, the hand off to the callback to write the results'''
        cursor = collection.find(findSpec)
        if sortSpec:
            cursor = cursor.sort(sortSpec)
        Nitems = cursor.count()
        if stop is None:
            stop = Nitems-1
        else:
            stop = min(stop, Nitems-1)
        cursor = cursor.skip(start).limit(stop-start+1)

        if restrict and Nitems > 1:
            rows = []
            start = 0
            stop = 0
            Nitems = 0
        else:
            rows = list(cursor)
        return (rows, start, stop, Nitems)
    
    def _callback(self, result, *args):
        '''Report the async worker's results'''
        rows, start, stop, Nitems = result
        
        # send the result
        self.set_header('Content-range', 'items %d-%d/%d' % (start,stop,Nitems))
        s = json.dumps(rows, default=pymongo.json_util.default)
        s = s.replace('"_ref":', '"$ref":') # restore $ref
        self.set_header('Content-length', len(s))
        self.set_header('Content-type', 'application/json')
        self.write(s)
        self.finish()

    def post(self, db_name, collection_name):
        '''Create a new item and return the single item not an array'''
        if not self.checkAccessKey(db_name, collection_name, access.Create):
            raise HTTPError(403, 'create not permitted (%s)' % self.checkAccessKeyMessage)
        
        collection = self.mongo_conn[db_name][collection_name]

        try:
            s = self.request.body
            s = s.replace('"$ref":', '"_ref":') # hide $ref
            item = json.loads(s, object_hook=pymongo.json_util.object_hook)
        except ValueError, e:
            raise HTTPError(400, unicode(e));

        id = newId()
        item['_id'] = id
        
        if access.Owner & self.flags:
            item[access.OwnerKey] = self.get_current_user()['email']
        self.validateSchema(db_name, collection_name, item)
        
        collection.insert(item, safe=True)
        # this path should get encoded only one place, fix this
        self.set_header('Location', '/data/%s/%s/%s' % (db_name, collection_name, id))
        s = json.dumps(item, default=pymongo.json_util.default)
        s = s.replace('"_ref":', '"$ref":') # restore $ref
        self.set_header('Content-length', len(s))
        self.set_header('Content-type', 'application/json')
        self.write(s)

# handle requests with an id
class ItemHandler(access.BaseHandler):
    def get(self, db_name, collection_name, id):
        '''Handle requests for single items'''
        if not self.checkAccessKey(db_name, collection_name, access.Read):
            raise HTTPError(403, 'read not permitted (%s)' % self.checkAccessKeyMessage)
        
        collection = self.mongo_conn[db_name][collection_name]
        
        # restrict fields here
        item = collection.find_one({'_id':id})
        s = json.dumps(item, default=pymongo.json_util.default)
        s = s.replace('"_ref":', '"$ref":') # restore $ref
        self.set_header('Content-length', len(s))
        self.set_header('Content-type', 'application/json')
        self.write(s)

    def put(self, db_name, collection_name, id):
        '''update an item after an edit, no response?'''
        if not self.checkAccessKey(db_name, collection_name, access.Update):
            raise HTTPError(403, 'update not permitted (%s)' % self.checkAccessKeyMessage)
        
        collection = self.mongo_conn[db_name][collection_name]
        try:
            s = self.request.body
            s = s.replace('"$ref":', '"_ref":') # restore $ref
            new_item = json.loads(s, object_hook=pymongo.json_util.object_hook)
            new_item['_id'] = id
        except ValueError, e:
            raise HTTPError(400, unicode(e));
        if access.Owner & self.flags and not (access.Developer & self.flags):
            old_item = collection.find_one({ '_id': id })
            if (not old_item or 
                access.OwnerKey not in old_item or 
                old_item[access.OwnerKey] != new_item[access.OwnerKey]):
                raise HTTPError(403, 'update not permitted (not owner)')
        self.validateSchema(db_name, collection_name, new_item)
        collection.update({ '_id': id }, new_item, upsert=False, safe=True)

    def delete(self, db_name, collection_name, id):
        '''Delete an item, what should I return?'''
        if not self.checkAccessKey(db_name, collection_name, access.Delete):
            raise HTTPError(403, 'delete item not permitted (%s)' % self.checkAccessKeyMessage)
        
        collection = self.mongo_conn[db_name][collection_name]
        if access.Owner & self.flags and not (access.Developer & self.flags):
            old_item = collection.find_one({ '_id': id })
            if (not old_item or 
                access.OwnerKey not in old_item or
                old_item[access.OwnerKey] != self.get_current_user()['email']):
                raise HTTPError(403, 'update not permitted (not owner)')
            
        collection.remove( { '_id' : id }, safe=True )

class TestHandler(access.BaseHandler):
    def get(self, flag):
        if flag == 'reset':
            db = self.mongo_conn['test']
            db.drop_collection('test')
            collection = db['test']
            
            for value,word in enumerate(['foo', 'bar', 'fee', 'baa', 'baa', 'bar']):
                collection.insert({
                    'word': word, 
                    'value': value, 
                    '_id': newId(),
                    access.OwnerKey: self.get_current_user()['email'] }, safe=True)
                    
            self.write('ok')
            
        elif re.match(r'\d+', flag):
            code = int(flag)
            raise HTTPError(code)
            
        
def generate_secret(seed):
    '''Generate the secret string for hmac'''
    random.seed(seed)
    return ''.join(random.choice(string.letters + string.digits + string.punctuation)
                   for i in range(100))

def run(port=8888, threads=4, debug=False, static=False, pid=None, 
        mongo_host='127.0.0.1', mongo_port=27017, seed=0):
    if pid is not None:
        # launch as a daemon and write the pid file
        import daemon
        daemon.daemonize(pid)
    # retry making the mongo connection with exponential backoff
    for i in range(8):
        try:
            conn = pymongo.Connection(mongo_host, mongo_port)
            break
        except pymongo.errors.AutoReconnect:
            t = 2 ** i
            logging.warning('backoff on python connection %d' % t)
            time.sleep(t)
    else:
        raise pymongo.errors.AutoReconnect
            
    kwargs = {
        'cookie_secret': generate_secret(seed),
        'debug': debug,
        'thread_count': threads,
        'mongo_conn' : conn
    }
    if static:
        kwargs['static_path'] = os.path.join(os.path.dirname(__file__), "../")
    application = mongo_util.MongoApplication([
        # why do we need this optional undefined string, explorer seems to be adding it
        # workaround for the bug fixed (we think) by http://trac.dojotoolkit.org/changeset/21041
        # was
        (r"/data/([a-zA-Z][a-zA-Z0-9]*)/([a-zA-Z][a-zA-Z0-9]*)?$", DatabaseHandler),
        (r"/data/([a-zA-Z][a-zA-Z0-9]*)/([a-zA-Z][a-zA-Z0-9]*)/$", CollectionHandler),
        (r"/data/([a-zA-Z][a-zA-Z0-9]*)/([a-zA-Z][a-zA-Z0-9]*)/([a-f0-9]+)", ItemHandler),
        (r"/data/_auth(.*)$", access.AuthHandler),
        (r"/data/_test_(reset|\d+)$", TestHandler),
    ], **kwargs)
    http_server = tornado.httpserver.HTTPServer(application)
    http_server.listen(port)
    tornado.ioloop.IOLoop.instance().start()
    
def generate_sample_data(n, host, port):
    import string, random
    docs = [ { 'label' : ''.join(random.sample(string.lowercase, random.randint(2,9))),
               'value': i * 1.1 + 0.01,
               '_id': newId() }
             for i in range(n) ]
    for doc in docs:
        doc['length'] = len(doc['label'])
        doc['letters'] = sorted(list(doc['label']))
        
    connection = pymongo.Connection(host, port)
    db = connection.test
    db.drop_collection('posts')
    db.posts.insert(docs)
    return n, 'test', 'posts'

def run_from_args():
    '''
    Runs an instance of the torongo server with options pulled from the command
    line.
    '''
    parser = optparse.OptionParser()
    parser.add_option("-p", "--port", dest="port", default=8888,
        help="server port number (default=8888)", type="int")
    parser.add_option("--mongoport", dest="mongoport", default=27017,
        help="mongo server port number (default=27201)", type="int")
    parser.add_option("--mongohost", dest="mongohost", default='127.0.0.1',
        help="mongo server host name (default=127.0.0.1)")
    parser.add_option("-w", "--workers", dest="workers", default=4,
        help="size of the worker pool (default=4)", type="int")
    parser.add_option("-g", "--generate", dest="generate", default=0,
        help="generate N random items in a db collection for testing (default=0)", 
        type="int")
    parser.add_option("--logId", dest="logId", default='', type="str",
        help="identity in syslog (default log to stderr)")
    parser.add_option("--logLevel", dest="logLevel", default="warning", type="str",
        help="logging level (info|debug|warning|error)")
    parser.add_option("--debug", dest="debug", action="store_true", 
        default=False, help="enable Tornado debug mode w/ automatic loading (default=false)")
    parser.add_option("--static", dest="static", action="store_true", 
        default=False, help="enable Tornado sharing of the jsonic root folder (default=false)")
    parser.add_option("--pid", dest="pid", default=None, type="str",
        help="launch as a daemon and write to the given pid file (default=None)")
    parser.add_option("--seed", dest="seed", default=0, type="int",
        help="seed for the random number generator")
    (options, args) = parser.parse_args()
    if options.generate:
        generate_sample_data(options.generate, options.mongohost, 
            options.mongoport)
        #print 'Generated %d random items in db: %s, collection: %s' % vals
        
    # initialize logging
    if options.logId:
        id = '%s:%d' % (options.logId, os.getpid())
        myLogging.init(id, options.logLevel)
    logging.warning('startup')

    # run the server
    run(options.port, options.workers, options.debug, options.static, 
        options.pid, options.mongohost, options.mongoport, options.seed)

if __name__ == "__main__":
    run_from_args()
