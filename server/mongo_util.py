'''
Utilities for using pymongo and its thread pool in web request handlers.

:copyright: Peter Parente 2010
:license: BSD
'''
from thread_util import ThreadPoolApplication, ThreadedRequestHandler
import pymongo
import pymongo.json_util
import json

class MongoApplication(ThreadPoolApplication):
    '''
    Stores a reference to a pymongo.Connecion or creates a new one to 
    the default port on localhost.
    
    :ivar mongo_conn:
    '''
    def __init__(self, *args, **kwargs):
        super(MongoApplication, self).__init__(*args, **kwargs)
        self.mongo_conn = kwargs.get('mongo_conn', pymongo.Connection())

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
        cb = self.async_callback(callback)
        def _worker(*args, **kwargs):
            result = worker(*args, **kwargs)
            self.mongo_conn.end_request()
            return result
        self.application.thread_pool(cb, _worker, *args, **kwargs)

    def to_json(self, obj):
        '''
        Serializes an object to JSON. Handles most mongo objects.
        
        :param obj:
        :rtype: str
        '''
        return json.dumps(obj, default=pymongo.json_util.default)
    
    def from_json(self, text):
        '''
        Unserializes JSON to an object. Handles most monogo objects.
        
        :param text:
        :rtype: object
        '''
        return json.loads(text, object_hook=pymongo.json_util.object_hook)