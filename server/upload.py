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
import os
import traceback
import subprocess
import json
import pymongo
import mongo_util
import mad
from sanity import sanitize

MediaDB = 'Media'
MediaURL = '/Media/'
MediaRoot = '/var/Media/'

class Bag(object):
    pass

class UploadHandler(access.BaseHandler):
    @tornado.web.asynchronous
    def post(self):
        '''Create a new item and return the single item not an array'''
        args = self.request.arguments
        info = Bag()
        try:
            info.tags = [ tag for tag in args['tags'][0].strip().split()
                          if re.match(r'^\w+$', tag) ]
            info.fname = args['file.name'][0].strip()
            info.ftype = args['file.content_type'][0].strip()
            info.fpath = args['file.path'][0].strip()
            key = args['Authorization'][0]
            info.title = args.get('title', [''])[0]
            info.description = args.get('description', [''])[0]
            info.creditURL = args.get('creditURL', [''])[0]
        except Exception, e:
            raise HTTPError(400, unicode(e))

        if info.ftype.startswith('image/'):
            worker = self._imageWorker
            medium = 'Image'
        elif info.ftype.startswith('audio/'):
            worker = self._audioWorker
            medium = 'Audio'
        else:
            raise HTTPError(400, 'invalid mimetype')

        if not self.checkAccessKey(MediaDB, medium, access.Create, key):
            raise HTTPError(403, 'upload not permitted (%s)' % self.checkAccessKeyMessage)

        collection = self.mongo_conn[MediaDB][medium]

        self.run_async(self._callback, worker, collection, info)

    def _imageWorker(self, collection, info):
        acceptable_extensions = set(['.jpg', '.gif', '.jpeg', '.bmp', '.png', '.tif', '.tiff',
                                    '.wbmp', '.jng', '.svg'])
        root, ext = os.path.splitext(info.fname)
        toRemove = [ info.fpath ]
        try:
            if ext not in acceptable_extensions:
                raise TypeError('unknown extension')
            id = mongo_util.newId()
            img = Image.open(file(info.fpath, 'rb'))
            w, h = img.size
            opath = os.path.join(MediaRoot, 'Image', id[-2:], id + ext)
            upath = os.path.join(MediaURL, 'Image', id + ext)
            dirname = os.path.dirname(opath)
            if not os.path.exists(dirname):
                os.makedirs(dirname)
            shutil.move(info.fpath, opath)
        except Exception:
            return (False, traceback.format_exc(), None)
        finally:
            for f in toRemove:
                try:
                    os.remove(f)
                except:
                    pass

        item = {}
        item['width'] = w
        item['height'] = h
        item['originalName'] = sanitize(info.fname)
        item['URL'] = sanitize(upath)
        item['tags'] = [ sanitize(tag) for tag in info.tags ]
        item['title'] = sanitize(info.title)
        item['description'] = sanitize(info.description)
        item['creditURL'] = sanitize(info.creditURL)
        user = self.get_current_user()
        item['uploadedBy'] = user['email']
        item['uploadedOn'] = datetime.now().isoformat()
        item['_id'] = id

        collection.insert(item, safe=True)

        return (True, item, 'Image')

    def _audioWorker(self, collection, info):
        root, ext = os.path.splitext(info.fname)
        toRemove = [ info.fpath ]
        if not ext:
            return (False, 'bad extension', None)

        id = mongo_util.newId()
        try:
            opath = os.path.join(MediaRoot, 'Audio', id[-2:], id)
            upath = os.path.join(MediaURL, 'Audio', id)

            dirname = os.path.dirname(opath)
            if not os.path.exists(dirname):
                os.makedirs(dirname)
            if info.ftype == 'audio/midi':
                # check the magic number to try to assure it is midi since timidity doesn't seem to error
                ms = magic.open(magic.MAGIC_NONE)
                ms.load()
                if not re.search(r'\smidi\s', ms.file(info.fpath), re.I):
                    raise TypeError('not midi')
                tmp = info.fpath + '.wav'
                toRemove.append(tmp)
                r1 = subprocess.call([TIMIDITYPATH, '-Ow', '-idqq', info.fpath, '-o', tmp])
                if r1:
                    raise RuntimeError('midi decode failed')
            elif ext != '.wav':
                tmp = info.fpath + '.wav'
                r1 = subprocess.call([SOXPATH, '-t', ext, info.fpath, tmp])
                toRemove.append(tmp)
                if r1:
                    raise RuntimeError('wav decode failed')
            else:
                tmp = info.fpath
            # at this point we should have a wav file in tmp
            r1 = subprocess.call([SOXPATH, '-t', '.wav', tmp, opath + '.mp3', 'rate', '22050', 'norm'])
            r2 = subprocess.call([SOXPATH, '-t', '.wav', tmp, opath + '.ogg', 'rate', '22050', 'norm'])
            if r1 or r2:
                raise RuntimeError('encoding failed')
                
            # get the duration
            mf = mad.MadFile(opath + '.mp3')
            duration = mf.total_time() / 1000.0
            
        except Exception:
            return (False, traceback.format_exc(), None)
        finally:
            for f in toRemove:
                try:
                    os.remove(f)
                except:
                    pass
        item = {}
        item['originalName'] = sanitize(info.fname)
        item['URL'] = upath
        item['tags'] = [ sanitize(tag) for tag in info.tags ]
        item['title'] = sanitize(info.title)
        item['description'] = sanitize(info.description)
        item['creditURL'] = sanitize(info.creditURL)
        user = self.get_current_user()
        item['uploadedBy'] = user['email']
        item['uploadedOn'] = datetime.now().isoformat()
        item['duration'] = duration
        item['_id'] = id

        collection.insert(item, safe=True)
        return (True, item, 'Audio')

    def _callback(self, result, *args):
        flag, value, medium = result
        if flag:
            # this path should get encoded only one place, fix this
            self.set_header('Location', '/%s/%s/%s' % (MediaDB, medium, id))
            s = json.dumps(value, default=pymongo.json_util.default)
            wrapper = '''<html><body><textarea>%s</textarea></body></html>'''
            s = wrapper % s
            self.set_header('Content-length', len(s))
            self.write(s)
            self.finish()
        else:
            logging.warning('upload failed: ' + value)
            raise HTTPError(400, value)

