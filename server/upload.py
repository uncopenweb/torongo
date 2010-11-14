'''upload.py handle uploading images and audio

needs sox (with mp3 compiled in) and timidity

'''

SOXPATH = '/usr/local/bin/sox'
TIMIDITYPATH = '/usr/bin/timidity'

import access
import tornado.web
from tornado.web import HTTPError
import logging
from PIL import Image
from datetime import datetime
import shutil
import magic
import re
import sys
import os
import traceback
import subprocess
import json
import pymongo
import mongo_util

MediaDB = 'Media'
MediaURL = '/Media/'
MediaRoot = '/var/Media/'

class UploadHandler(access.BaseHandler):
    @tornado.web.asynchronous
    def post(self):
        '''Create a new item and return the single item not an array'''
        args = self.request.arguments
        try:
            tags = [ tag for tag in args['tags'][0].strip().split()
                     if re.match(r'^\w+$', tag) ]
            fname = args['file.name'][0].strip()
            ftype = args['file.content_type'][0].strip()
            fpath = args['file.path'][0].strip()
            key = args['Authorization'][0]
        except Exception, e:
            raise HTTPError(400, unicode(e))

        if ftype.startswith('image/'):
            worker = self._imageWorker
            medium = 'Image'
        elif ftype.startswith('audio/'):
            worker = self._audioWorker
            medium = 'Audio'
        else:
            raise HTTPError(400, 'invalid mimetype')

        if not self.checkAccessKey(MediaDB, medium, access.Create, key):
            raise HTTPError(403, 'upload not permitted (%s)' % self.checkAccessKeyMessage)

        collection = self.mongo_conn[MediaDB][medium]

        self.run_async(self._callback, worker, collection, tags, fname, ftype, fpath)

    def _imageWorker(self, collection, tags, fname, ftype, fpath):
        acceptable_extensions = set(['.jpg', '.gif', '.jpeg', '.bmp', '.png', '.tif', '.tiff',
                                    '.wbmp', '.jng', '.svg'])
        print >>sys.stderr, '_imageWorker', tags, fname, ftype, fpath
        root, ext = os.path.splitext(fname)
        toRemove = [ fpath ]
        try:
            if ext not in acceptable_extensions:
                raise TypeError('unknown extension')
            id = mongo_util.newId()
            img = Image.open(file(fpath, 'rb'))
            w, h = img.size
            opath = os.path.join(MediaRoot, 'Image', id[-2:], id + ext)
            upath = os.path.join(MediaURL, 'Image', id + ext)
            dirname = os.path.dirname(opath)
            if not os.path.exists(dirname):
                os.makedirs(dirname)
            shutil.move(fpath, opath)
        except Exception, e:
            traceback.print_exc()
            return (False, e, None)
        finally:
            for f in toRemove:
                try:
                    os.remove(f)
                except:
                    pass

        item = {}
        item['width'] = w
        item['height'] = h
        item['originalName'] = fname
        item['URL'] = upath
        item['tags'] = tags
        user = self.get_current_user()
        item['uploadedBy'] = user['email']
        item['uploadedOn'] = datetime.now().isoformat()
        item['_id'] = id

#        self.validateSchema(MediaDB, 'image', item)

        collection.insert(item, safe=True)

        return (True, item, 'Image')

    def _audioWorker(self, collection, tags, fname, ftype, fpath):
        print >>sys.stderr, '_audioWorker', tags, fname, ftype, fpath
        root, ext = os.path.splitext(fname)
        toRemove = [ fpath ]
        if not ext:
            return (False, 'bad extension', None)

        id = mongo_util.newId()
        try:
            opath = os.path.join(MediaRoot, 'Audio', id[-2:], id)
            upath = os.path.join(MediaURL, 'Audio', id)

            dirname = os.path.dirname(opath)
            if not os.path.exists(dirname):
                os.makedirs(dirname)
            if ftype == 'audio/midi':
                # check the magic number to try to assure it is midi since timidity doesn't seem to error
                ms = magic.open(magic.MAGIC_NONE)
                ms.load()
                if not re.search(r'\smidi\s', ms.file(fpath), re.I):
                    raise TypeError('not midi')
                tmp = fpath + '.wav'
                toRemove.append(tmp)
                r1 = subprocess.call([TIMIDITYPATH, '-Ow', '-idqq', fpath, '-o', tmp])
                if r1:
                    raise RuntimeError('midi decode failed')
            elif ext != '.wav':
                tmp = fpath + '.wav'
                r1 = subprocess.call([SOXPATH, '-t', ext, fpath, tmp])
                toRemove.append(tmp)
                if r1:
                    raise RuntimeError('wav decode failed')
            else:
                tmp = fpath
            # at this point we should have a wav file in tmp
            r1 = subprocess.call([SOXPATH, '-t', '.wav', tmp, opath + '.mp3', 'rate', '22050', 'norm'])
            r2 = subprocess.call([SOXPATH, '-t', '.wav', tmp, opath + '.ogg', 'rate', '22050', 'norm'])
            if r1 or r2:
                raise RuntimeError('encoding failed')
        except Exception, e:
            traceback.print_exc()
            return (False, e, None)
        finally:
            for f in toRemove:
                try:
                    os.remove(f)
                except:
                    pass

        item = {}
        item['originalName'] = fname
        item['URL'] = upath
        item['tags'] = tags
        user = self.get_current_user()
        item['uploadedBy'] = user['email']
        item['uploadedOn'] = datetime.now().isoformat()
        item['_id'] = id
        return (True, item, 'Audio')

    def _callback(self, result, *args):
        print >>sys.stderr, '_callback', result, args
        flag, value, medium = result
        if flag:
            # this path should get encoded only one place, fix this
            self.set_header('Location', '/%s/%s/%s' % (MediaDB, medium, id))
            s = json.dumps(value, default=pymongo.json_util.default)
            wrapper = '''<html><body><textarea>%s</textarea></body></html>'''
            s = wrapper % s
            self.set_header('Content-length', len(s))
            # self.set_header('Content-type', 'application/json')
            self.write(s)
            self.finish()
        else:
            raise HTTPError(400, value)

