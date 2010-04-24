'''
Simple REST interface to mongo. Mostly just an example of the mongo_util 
lib right now.

:copyright: Peter Parente 2010
:license: BSD
'''
import tornado.httpserver
import tornado.ioloop
import tornado.web
import pymongo
import pymongo.json_util
import thread_util
import mongo_util

class DatabaseHandler(mongo_util.MongoRequestHandler):
    def get(self, db_name):
        db = self.mongo_conn[db_name]
        names = db.collection_names()
        info = {'collections' : names}
        self.write(self.to_json(info))

class CollectionHandler(mongo_util.MongoRequestHandler):
    def get(self, db_name, coll_name):
        coll = self.mongo_conn[db_name][coll_name]
        count = coll.count()
        name = coll.full_name
        info = {'count' : count, 'full_name' : name}
        self.write(self.to_json(info))

class ObjectHandler(mongo_util.MongoRequestHandler):
    def get(self, db_name, coll_name, object_id):
        coll = self.mongo_conn[db_name][coll_name]
        obj = coll.find_one(pymongo.objectid.ObjectId(object_id))
        if obj is None:
            raise tornado.web.HTTPError(404)
        self.write(self.to_json(obj))

class FindHandler(mongo_util.MongoRequestHandler):
    @tornado.web.asynchronous
    def get(self, db_name, coll_name):
        query = self.request.arguments['query'][0]
        limit = int(self.request.arguments.get('limit', ['10'])[0])
        skip = int(self.request.arguments.get('skip', ['0'])[0])
        query = self.from_json(query)
        coll = self.mongo_conn[db_name][coll_name]
        self.run_async(self._callback, self._worker, coll, query, limit, skip)

    def _worker(self, coll, query, limit, skip):
        cursor = coll.find(query, skip=skip, limit=limit)
        rows = [obj for obj in cursor]
        return {'count' : cursor.count(), 'rows' : rows}
    
    def _callback(self, result, *args):
        self.write(self.to_json(result))
        self.finish()

def run_server(thread_count=5, debug=False):
    valid_name = '[a-z][a-z0-9]+'
    application = mongo_util.MongoApplication([
        (r'/(%(valid_name)s)/' % locals(), DatabaseHandler),
        (r'/(%(valid_name)s)/(%(valid_name)s)/' % locals(), CollectionHandler),
        (r'/(%(valid_name)s)/(%(valid_name)s)/find/' % locals(), FindHandler),
        (r'/(%(valid_name)s)/(%(valid_name)s)/([a-f0-9]+)/' % locals(), ObjectHandler)
    ], debug=debug, thread_count=thread_count)
    http_server = tornado.httpserver.HTTPServer(application)
    http_server.listen(8888)
    ioloop = tornado.ioloop.IOLoop.instance()
    ioloop.start()

if __name__ == '__main__':
    run_server(debug=True)