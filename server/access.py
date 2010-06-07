# access control for our JsonRestStore

import random
import hmac
import hashlib
import string
from datetime import datetime, timedelta

ModeBits = tuple(1 << i for i in random.sample(xrange(31), 6)) # key values
Create, Read, Update, Delete, DropCollection, CreateNewCollection = ModeBits

iMode = { 'c': Create,
          'r': Read,
          'u': Update,
          'd': Delete,
          'D': DropCollection,
          'C': CreateNewCollection }

Mask = sum(ModeBits)
Key = ''.join(random.choice(string.letters + string.digits + string.punctuation) for i in range(99))
Noise = random.getrandbits(31) & ~Mask

KeyDuration = timedelta(1, 0)

def makeSignature(db, collection, user, modebits, timebits):
    signature = hmac.new(Key, db + collection + modebits + timebits, hashlib.sha1).hexdigest()
    return signature

def makeAccessKey(db, collection, modestring, user, request):
    omode = sum(iMode[c] for c in modestring if c in iMode)
    modebits = '%x' % (omode | Noise)
    timebits = '%x' % int(datetime.now().strftime('%y%m%d%H%M%S'))
    key = '%s-%s-%s' % (modebits, timebits, makeSignature(db, collection, user, modebits, timebits))
    return key

def checkAccessKey(db, collection, mode, user, request):
    key = request.headers.get('Authorization', None)
    if not key:
        return None
    modebits, timebits, signature = key.split('-')
    if signature != makeSignature(db, collection, user, modebits, timebits):
        return False
    timebits = str(int(timebits, 16))
    delay = datetime.now() - datetime.strptime(timebits, '%y%m%d%H%M%S')
    if delay > KeyDuration:
        return False
    allowedMode = int(modebits, 16) & Mask
    return (allowedMode & mode) != 0

if __name__ == '__main__':
    class bag(object):
        pass
    key = makeAccessKey('BigWords', 'wordfreq', 'r', 'gb', None)
    print key
    
    request = bag()
    request.headers = { 'Authorization': key }

    print checkAccessKey('BigWords', 'wordfreq', Read, 'gb', request)
    
