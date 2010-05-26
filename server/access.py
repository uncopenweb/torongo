# access control for our JsonRestStore

import random
import hmac
import hashlib
import base64
import string

Users = { 'gary.bishop.unc@gmail.com' : 'developer',
          'duncan.lewis@gmail.com' : 'developer',
          'karen.erickson@gmail.com' : 'bigwords_admin',
          '*@gmail.com' : 'known',
          'None' : 'unknown' }

Permissions = { 'developer' : { '*/*' : 'crudD' },
                'bigwords_admin' : { 'BigWords/*' : 'crud' },
                'known' : { 'BigWords/log' : 'c' },
                }

DBs = { 'BigWords' : { 'wordfreq': 'r',
                       'AmericanEnglish': 'r',
                       'Lessons': { 'developer': 'crudD',
                                    'bigwords_admin': 'crud',
                                    'known': 'r' },
                       'Log': { 'developer': 'crudD',
                                'bigwords_admin': 'r',
                                'known': 'c' },
                       'DemoLessons': 'r',
                       },
        }

Create, Read, Update, Delete, Drop = (1 << i for i in random.sample(xrange(31), 5)) # key values

iMode = { 'c': Create, 'r': Read, 'u': Update, 'd': Delete, 'D': Drop }

Mask = Create | Read | Update | Delete | Drop
MaskOff = ~Mask
Key = ''.join(random.choice(string.letters + string.digits + string.punctuation) for i in range(50))
Noise = random.getrandbits(31) & MaskOff

def makeSignature(db, collection, user, modebits):
    digest = hmac.new(Key, db + collection + modebits, hashlib.sha1).digest()
    signature = base64.urlsafe_b64encode(digest)
    return signature

def makeAccessKey(db, collection, modestring, user, request):
    omode = sum(iMode[c] for c in modestring if c in iMode)
    modebits = '%x' % (omode | Noise)
    key = modebits + '|' + makeSignature(db, collection, user, modebits)
    return key

def checkAccessKey(db, collection, mode, user, request):
    key = request.headers.get('Authorization', None)
    if not key:
        return None
    modebits, signature = key.split('|')
    if signature != makeSignature(db, collection, user, modebits):
        return False
    allowedMode = int(modebits, 16) & Mask
    return (allowedMode & mode) != 0

if __name__ == '__main__':
    key, mode = makeAccessKey('BigWords', 'AmericanEnglish', read, { 'email': 'gb@cs.unc.edu' },
                              None)
    print key, mode
    print checkAccessKey('BigWords', 'AmericanEnglish', read, { 'email': 'gb@cs.unc.edu' }, None,
                         key)
    

    
