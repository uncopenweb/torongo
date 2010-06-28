# access control for our JsonRestStore

import random
import hmac
import hashlib
import string
from datetime import datetime, timedelta
import tornado.web
from tornado.web import HTTPError
import tornado.auth
import pymongo
import pymongo.json_util
import mongo_util
import json
import os

# seed the random number generator so all instances get the same key
stat = os.stat(__file__)
seed = stat.st_mtime * os.getppid()
random.seed(seed)

ModeBits = tuple(1 << i for i in random.sample(xrange(31), 6)) # key values
Create, Read, Update, Delete, DropCollection, List = ModeBits

iMode = { 'c': Create,          # create records
          'r': Read,            # read/search records
          'u': Update,          # update record
          'd': Delete,          # delete record
          'D': DropCollection,  # drop whole collection
          'L': List }           # list collections

Mask = sum(ModeBits)
Key = ''.join(random.choice(string.letters + string.digits + string.punctuation) 
              for i in range(99))
Noise = random.getrandbits(31) & ~Mask

KeyDuration = timedelta(1, 0) # default to one day

def makeSignature(db, collection, user, modebits, timebits):
    signature = hmac.new(Key, db + collection + modebits + timebits, hashlib.sha1).hexdigest()
    return signature

class BaseHandler(mongo_util.MongoRequestHandler):
    '''Manage user cookie'''
    def get_current_user(self):
        user_json = self.get_secure_cookie("user")
        if not user_json:
            result = { 'email' : 'None' }
        else:
            result = tornado.escape.json_decode(user_json)
        #print 'get_current_user', result
        return result

    def makeAccessKey(self, db, collection, modestring):
        # fetch the access collection for this database
        user = self.get_current_user()
        omode = sum(iMode[c] for c in modestring if c in iMode)
        modebits = '%x' % (omode | Noise)
        timebits = '%x' % int(datetime.now().strftime('%y%m%d%H%M%S'))
        key = '%s-%s-%s' % (modebits, timebits, makeSignature(db, collection, user, modebits,
                            timebits))
        return key

    def checkAccessKey(self, db, collection, mode):
        print self.request.headers
        key = self.request.headers.get('Authorization', None)
        if not key:
            return None
        modebits, timebits, signature = key.split('-')
        user = self.get_current_user()
        if signature != makeSignature(db, collection, user, modebits, timebits):
            return False
        timebits = str(int(timebits, 16))
        delay = datetime.now() - datetime.strptime(timebits, '%y%m%d%H%M%S')
        if delay > KeyDuration:
            return False
        allowedMode = int(modebits, 16) & Mask
        return (allowedMode & mode) != 0

class AuthHandler(BaseHandler, tornado.auth.GoogleMixin):
    '''Handle authentication using Google OpenID'''
    @tornado.web.asynchronous
    def get(self, id):
        #print 'auth get', id
        if not id:
            # start auth from Google
            if self.get_argument("openid.mode", None):
                #print 'calling get_authenticed_user'
                self.get_authenticated_user(self.async_callback(self._on_auth))
                return
            #print 'calling authenticate_redirect'
            self.authenticate_redirect()
        elif id == '-start':
            resp = '''
<html>
  <head>
  </head>
  <body onload="window.opener.uow._handleOpenIDStart();window.location='_auth';>
    This page is just before redirect to Google.
  </body>
</html>
'''
            self.write(resp)
            self.finish()
        else:
            #print 'sending response'
            # wrap up the authorization
            resp = '''
<html>
  <head>
  </head>
  <body onload="window.opener.uow._handleOpenIDResponse('%s');window.close();">
    This page is after login is complete.
  </body>
</html>'''
            resp = resp % id[1:]
            self.write(resp)
            self.finish()

    def _on_auth(self, user):
        #print 'on_auth', user
        if user:
            self.set_secure_cookie("user", tornado.escape.json_encode(user))
            #print 'set the cookie', user
            self.redirect("/data/_auth-ok")
        else:
            self.redirect("/data/_auth-failed")

    def post(self, id):
        '''Open a db/collection with requested permissions'''
        args = json.loads(self.request.body, object_hook=pymongo.json_util.object_hook)
        db = args['database']
        collection = args['collection']
        mode = args['mode']
        user = self.get_current_user()
        key = self.makeAccessKey(db, collection, mode)
        if collection == '*':
            url = '/data/%s/' % db
        else:
            url = '/data/%s/%s/' % (db, collection)
        self.write({ 'url' : url,
                     'key' : key })

