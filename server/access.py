# access control for our JsonRestStore

import hmac
import hashlib
from datetime import datetime, timedelta
import tornado.web
from tornado.web import HTTPError
import tornado.auth
import pymongo
import pymongo.json_util
import mongo_util
import json
import socket
import struct
import jsonschema
import sys
import httplib
import traceback
import re

localIP = re.compile(r'127\.0\.[01]\.1$')

# mode names
Create = set('c')
Read = set('r')
Update = set('u')
Delete = set('d')
DropCollection = set('D')
List = set('L')
Upload = set('U')

modeSet = Create | Read | Update | Delete | DropCollection | List | Upload

KeyDuration = timedelta(1, 0) # one day

AdminDbName = 'Admin'

def matchIP(ip, pattern):
    if ip == pattern:
        return True
    if '/' in pattern:
        pip, bits = pattern.split('/')
        n0 = struct.unpack('!I', socket.inet_aton(ip))[0]
        n1 = struct.unpack('!I', socket.inet_aton(pip))[0]
        shift = (32 - int(bits))
        return (n0 >> shift) == (n1 >> shift)
    return False
        
class BaseHandler(mongo_util.MongoRequestHandler):
    '''Manage user cookie'''
    def get_current_user(self):
        user_json = self.get_secure_cookie("user")
        if not user_json:
            result = { 'email' : None }
        else:
            result = tornado.escape.json_decode(user_json)
        #print 'get_current_user', result
        return result
        
    def isDeveloper(self, user=None, role=None):
        '''Return true for local developers'''
        if user is None:
            user = self.get_current_user()
        
        if role is None:
            role = self.getRole(user)
        
        # this should probably be disabled on the production server
        # note the db name _Admin is not accessible from this web interface
        if role not in [ 'superuser', 'developer' ]:
            print >>sys.stderr, user, "role not developer"
            return False
        if 'X-Real-Ip' not in self.request.headers:
            print >>sys.stderr, "X-Real-Ip not found"
            return False
        rip = self.request.headers['X-Real-IP']
        if 'X-Uow-User' not in self.request.headers and not localIP.match(rip):
            print >>sys.stderr, "X-Uow-User not found"
            print >>sys.stderr, self.request.headers
            return False
        #print >>sys.stderr, "OK"
        return True   

    def makeSignature(self, db, collection, user, modebits, timebits):
        self.require_setting("cookie_secret", "secure cookies")
        signature = hmac.new(self.application.settings["cookie_secret"], 
                             db + collection + modebits + timebits, 
                             hashlib.sha1).hexdigest()
        return signature
        
    def getRole(self, user = None, db = None):
        if user is None:
            user = self.get_current_user()
            
        # connect to the Admin db
        if db is None:
            db = self.mongo_conn[AdminDbName]
        
        # fetch a role for this user
        Developers = db['Developers']
        info = Developers.find_one( { 'user': user['email'] } )
        if info:
            role = info['role']
        else:
            AccessUsers = db['AccessUsers']
            info = AccessUsers.find_one( { 'user': user['email'] } )
            if info:
                role = info['role']
            elif user['email'] is None: # not logged in
                role = 'anonymous'
            else:
                role = 'identified' # logged in but not specifically given a role
            
        return role


    def makeAccessKey(self, dbName, collection, modestring):
        '''Create an access key for a database/collection pair with the requested mode
        
        Note: We only lookup the user Role and Permissions here. Later we trust the key.
        '''
        # get the user so we can check permissions
        user = self.get_current_user()
        # restrict requested modes to legal ones
        requested_mode = set(modestring) & modeSet
        
        # connect to the Admin db
        db = self.mongo_conn[AdminDbName]
        
        role = self.getRole(user, db)
        
        # fetch permissions for this role
        AccessModes = db['AccessModes']
        # look for the role, db, collection triple
        perms = AccessModes.find_one( { 'role': role, 
                                        'database': dbName, 
                                        'collection': collection } )

        if dbName == 'Admin' and collection == 'Developers':
            if role == "superuser":
                permission = requested_mode
            else:
                permission = ''
                
        elif perms:
            permission = perms['permission']
            
        elif self.isDeveloper(user, role):
            permission = requested_mode # developers get their wish
            
        else:
            permission = '' # others get nothing
                
        # allowed is the intersection between requested and permitted
        allowed_mode = requested_mode & set(permission)
        # include field restrictions here
        #print >>sys.stderr, "allowed mode", allowed_mode
        modebits = ''.join(allowed_mode)
        timebits = '%x' % int(datetime.now().strftime('%y%m%d%H%M%S'))
        # construct the signed result
        key = '%s-%s-%s' % (modebits, timebits, self.makeSignature(dbName, collection, user, modebits,
                            timebits))
        return key

    def checkAccessKey(self, db, collection, mode, key=None):
        '''Validate an access key'''
        self.checkAccessKeyMessage = ''
        key = key or self.request.headers.get('Authorization', None)
        if not key:
            self.checkAccessKeyMessage = 'missing authorization header'
            return None
        try:
            modebits, timebits, signature = key.split('-')
        except ValueError:
            self.checkAccessKeyMessage = 'bad authorization header'
            return False
        user = self.get_current_user()
        if signature != self.makeSignature(db, collection, user, modebits, timebits):
            self.checkAccessKeyMessage = 'invalid signature'
            return False
        timebits = str(int(timebits, 16))
        delay = datetime.now() - datetime.strptime(timebits, '%y%m%d%H%M%S')
        if delay > KeyDuration:
            self.checkAccessKeyMessage = 'key expired'
            return False
        allowedMode = set(modebits) & modeSet
        result = (allowedMode & mode)
        if not result:
            self.checkAccessKeyMessage = 'Mode not in allowed set'
        return result
        
    def validateSchema(self, db, collection, item):
        schemas = self.mongo_conn[AdminDbName]['Schemas']
        info = schemas.find_one({ 'database': db, 'collection': collection })
        #print >>sys.stderr, 'db=', db, 'collection=', collection, 'item', item, 'info', info
        if not info:
            #print >>sys.stderr, "No schema"
            return
        #print >>sys.stderr, "validating"
        try:
            jsonschema.validate(item, json.loads(info['schema']))
        except ValueError, e:
            #print >>sys.stderr, "failed", e.message
            raise HTTPError(403, e.message)
        #print >>sys.stderr, "OK"
        
    def get_error_html(self, status_code, **kwargs):
        '''Override their error message to give developers more info'''
        description = httplib.responses[status_code]
        message = ''
        if self.isDeveloper() and 'exception' in kwargs:
            exc = kwargs['exception']
            if isinstance(exc, HTTPError):
                message = exc.log_message
            else:
                message = traceback.format_exc()

        return '''<html>
  <head>
    <meta charset="utf-8" />
    <title>%(code)d: %(description)s</title>
  </head>
  <body><p>%(code)d: %(description)s<p><pre>%(message)s</pre></body>
</html>''' % {
                "code": status_code,
                "description": description,
                "message": message,
            }
#        return "<html><title>%(code)d: %(description)s</title>" \
#               "<body>%(code)d: %(message)s</body></html>" % {
#            "code": status_code,
#            "description": description,
#            "message": message,
#        }


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
        elif id == '/user':
            user = self.get_current_user()
            user['role'] = self.getRole(user)
            s = json.dumps(user)
            self.set_header('Content-length', len(s))
            self.set_header('Content-type', 'application/json')
            self.write(s)
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
        key = self.makeAccessKey(db, collection, mode)
        if collection == '*':
            url = '/data/%s/' % db
        else:
            url = '/data/%s/%s/' % (db, collection)
        self.write({ 'url' : url,
                     'key' : key })

