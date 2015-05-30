'''
Utilities for using pymongo and its thread pool in web request handlers.

:copyright: Peter Parente 2010
:license: BSD
'''
from thread_util import ThreadPoolApplication, ThreadedRequestHandler
import pymongo
import bson.json_util
import bson.objectid
import json

class MongoApplication(ThreadPoolApplication):
    '''
    Stores a reference to a pymongo.Connecion or creates a new one to 
    the default port on localhost.
    
    :ivar mongo_conn:
    '''
    def __init__(self, *args, **kwargs):
        super(MongoApplication, self).__init__(*args, **kwargs)
        try:
            self.mongo_conn = kwargs['mongo_conn']
        except KeyError:
            self.mongo_conn = pymongo.Connection()

class MongoRequestHandler(ThreadedRequestHandler):
    '''
    Provides convenience methods for JSON encoding/decoding of mongo results
    and use of the monogo thread pool.
    
    :ivar mongo_conn:
    '''
    def __init__(self, *args, **kwargs):
        super(MongoRequestHandler, self).__init__(*args, **kwargs)
        self.mongo_conn = self.application.mongo_conn
        
    def run_async(self, callback, worker, *args, **kwargs):
        '''
        Runs a worker function in a thread and receives the result in a 
        callback. Cleans up the pymongo.Connection thread pool properly.
        
        :param callback:
        :param worker:
        :param args:
        :param kwargs:
        '''
        def _worker(*args, **kwargs):
            result = worker(*args, **kwargs)
            self.mongo_conn.end_request()
            return result
        self.application.thread_pool(callback, _worker, *args, **kwargs)

    def to_json(self, obj):
        '''
        Serializes an object to JSON. Handles most mongo objects.
        
        :param obj:
        :rtype: str
        '''
        return json.dumps(obj, default=bson.json_util.default)
    
    def from_json(self, text):
        '''
        Unserializes JSON to an object. Handles most monogo objects.
        
        :param text:
        :rtype: object
        '''
        return json.loads(text, object_hook=bson.json_util.object_hook)

def newId():
    '''Use the mongo ID mechanism but convert them to strings'''
    # Not sure why I prefer the strings, they sure look better than the objects
    return str(bson.objectid.ObjectId())


