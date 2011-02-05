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
import httplib
import traceback
import re
import logging
import sys

localIP = re.compile(r'127\.0\.[01]\.1$')

# mode names
Create = set('c')
Read = set('rR')
RestrictedRead = set('R')
Update = set('u')
Delete = set('d')
Override = set('O') # allow writing records owned by others

OwnerKey = '_owner' # key in the schema to store the owner

modeSet = Create | Read | Update | Delete | Override
collectionSet = Create | Read | Update | Delete | Override
dbSet = Read | Delete

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
        if hasattr(self, 'user'):
            return self.user
            
        user_json = self.get_secure_cookie("user")
        if not user_json:
            result = { 'email' : None }
        else:
            result = tornado.escape.json_decode(user_json)
            if 'email' not in result:
                logging.warning('no email in user: %s' % repr(result))
                result['email'] = None
        logging.debug('user: %s' % repr(result))
        self.user = result
        return result
        
    def getUserId(self):
        if hasattr(self, 'user'):
            return self.user['email']
        return self.get_current_user()['email']
        
    def isDeveloper(self, user=None, role=None):
        '''Return true for local developers'''
        return self.getRole() in [ 'developer' ]

    def makeSignature(self, *args):
        self.require_setting("cookie_secret", "secure cookies")
        signature = hmac.new(self.application.settings["cookie_secret"], 
                             ''.join([ str(arg) for arg in args ]), 
                             hashlib.sha1).hexdigest()
        return signature
        
    def getRole(self, userId = None, db = None):
        if hasattr(self, 'role'):
            return self.role
            
        if userId is None:
            userId = self.getUserId()
        
        if not userId:
            self.role = 'anonymous'
            return 'anonymous'
            
        # connect to the Admin db
        if db is None:
            db = self.mongo_conn[AdminDbName]
        
        # fetch a role for this user
        Developers = db['Developers']
        info = Developers.find_one( { 'user': userId } )
        if info:
            role = info['role']
        else:
            AccessUsers = db['AccessUsers']
            info = AccessUsers.find_one( { 'user': userId } )
            if info and info['role'] not in [ 'developer' ]:
                role = info['role']
            else:
                role = 'identified' # logged in but not specifically given a role
        self.role = role
        return role


    def makeAccessKey(self, dbName, collection, modestring):
        '''Create an access key for a database/collection pair with the requested mode
        
        Note: We only lookup the user Role and Permissions here. Later we trust the key.
        '''
        # get the user so we can check permissions
        userId = self.getUserId()
        # restrict requested modes to legal ones
        requested_mode = set(modestring)
        if collection == '*':
            requested_mode &= dbSet
        else:
            requested_mode &= collectionSet
        
        # connect to the Admin db
        db = self.mongo_conn[AdminDbName]
        
        role = self.getRole(userId, db)
        
        # fetch permissions for this role
        AccessModes = db['AccessModes']
        # look for the role, db, collection triple
        perms = AccessModes.find_one( { 'role': role, 
                                        'database': dbName, 
                                        'collection': collection } )
        print >>sys.stderr, role, dbName, collection, perms
        if dbName == 'admin':
            permission = ''
            
        elif dbName == 'Admin' and collection == 'Developers':
            if role == "developer" and  userId == 'gary.bishop.unc@gmail.com':
                permission = requested_mode
            else:
                permission = ''
                
        elif dbName == 'Admin' and collection == 'AccessUsers':
            if role in [ 'developer', 'admin' ]:
                permission = requested_mode
            else:
                permission = ''
                
        elif perms:
            permission = perms['permission']
            
        elif role in [ 'developer' ]:
            permission = requested_mode # developers get their wish
            
        else:
            permission = '' # others get nothing
                
        # allowed is the intersection between requested and permitted
        self.allowedMode = requested_mode & set(permission)

        # include field restrictions here
        modebits = ''.join(sorted(self.allowedMode))
        timebits = '%x' % int(datetime.now().strftime('%y%m%d%H%M%S'))
        # construct the signed result
        key = '%s-%s-%s' % (modebits, timebits, self.makeSignature(dbName, collection, 
                               userId, modebits, timebits))
        return key, modebits

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
        userId = self.getUserId()
        
        if signature != self.makeSignature(db, collection, userId, modebits, timebits):
            self.checkAccessKeyMessage = 'invalid signature'
            return False
        timebits = str(int(timebits, 16))
        delay = datetime.now() - datetime.strptime(timebits, '%y%m%d%H%M%S')
        if delay > KeyDuration:
            self.checkAccessKeyMessage = 'key expired'
            return False
        self.allowedMode = set(modebits) & modeSet
        result = (self.allowedMode & mode)
        if not result:
            self.checkAccessKeyMessage = 'Mode not in allowed set'
        return result
        
    def validateSchema(self, db, collection, item):
        schemas = self.mongo_conn[AdminDbName]['Schemas']
        info = schemas.find_one({ 'database': db, 'collection': collection })
        if not info:
            return
        try:
            schema = info['schema']
            jsonschema.validate(item, schema)
        except ValueError, e:
            raise HTTPError(403, e.message)
        
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
        if not id:
            # start auth from Google
            if self.get_argument("openid.mode", None):
                self.get_authenticated_user(self.async_callback(self._on_auth))
                return
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
            user['role'] = self.getRole()
            self.write(user)
            self.finish()

        else:
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
        if user and 'email' in user and '@' in user['email']:
            self.set_secure_cookie("user", tornado.escape.json_encode(user))
            self.redirect("/data/_auth-ok")
        else:
            self.redirect("/data/_auth-failed")

    def post(self, id):
        '''Open a db/collection with requested permissions'''
        args = json.loads(self.request.body, object_hook=pymongo.json_util.object_hook)
        db = args['database']
        collection = args['collection']
        mode = args['mode']
        key, mode = self.makeAccessKey(db, collection, mode)
        if collection == '*':
            url = '/data/%s-%s/' % (mode, db)
        else:
            url = '/data/%s-%s/%s/' % (mode, db, collection)
        self.write({ 'url' : url,
                     'key' : key })

