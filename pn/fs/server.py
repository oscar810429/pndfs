import time
import string
import random

from urllib import quote_plus

from twisted.python import log, failure
from twisted.internet import defer, protocol, reactor
from twisted.protocols import basic, policies


from pn.util import url
from pn.client.mogilefs import MogileFSError
from pn import model

PAINIU_TIME = 1117555200

CLASSES = ('photo', 'icon', 'meta')

SECRET_CHARS = string.lowercase + string.digits

ERRORS = {
	'mis_params' : 'Missing required argument \'%s\'',
	'bad_params' : 'Invalid argument value \'%s=%s\'',
	'db'         : 'PNFS database error',
	'not_found'  : '%s is not found',
	'unknown_command': 'Unknown server command'
}

class PNFSError(Exception):
	def __init__(self, code, *args):
		self.code = code
		if ERRORS.has_key(code):
			self.msg = ERRORS[code] % args if args else ERRORS[code]
		else:
			self.msg = code
		Exception.__init__(self, self.code, self.msg)

class PNFSCommand(object):
	command = None
	
	def __init__(self, protocol, args):
		self.protocol = protocol
		self.mogilefs = protocol.mogilefs
		self.args = args
		self.__args_cache = {}
		
	def handle(self):
		handler = 'handle_%s' % self['class']
		if hasattr(self, handler):
			return getattr(self, handler)()
		else:
			raise PNFSError('bad_params', key, v)
	
	def has_attr(self, key):
		return self.args.has_key(key)
	
	def __getattr__(self, key):
		if self.__args_cache.has_key(key):
			return self.__args_cache[key]
			
		if not self.args.has_key(key):
			raise PNFSError('mis_params', key)
			
		v = self.args[key]
		if key == 'class':
			if v not in CLASSES:
				raise PNFSError('bad_params', key, v)
		elif key in ('size', 'width', 'height', 'time'):
			try:
				v = int(v)
			except ValueError:
				raise PNFSError('bad_params', key, v)
			
		self.__args_cache[key] = v
		return v
		
	__getitem__ = __getattr__
	
	def get_key(self):
		if hasattr(self, 'mfs_key'):
			return self.mfs_key
		attr = 'get_%s_key' % self['class']
		if hasattr(self, attr):
			self.mfs_key = getattr(self, attr)()
			return self.mfs_key
		else:
			raise PNFSError('bad_params', key, v)
		
	def get_photo_key(self):
		return '%s-%s-%s' % (self.username, self.filename, self.secret)
	
	def get_icon_key(self):
		return 'icons-%s' % self.filename
		
	def get_meta_key(self):
		return '%s-%s-meta' % (self.username, self.filename)

class GetPaths(PNFSCommand):
	def handle_photo(self):
		return self._get_paths()

	def handle_icon(self):
		return self._get_paths()
		
	def handle_meta(self):
		return self._get_paths()

	def _get_paths(self):
		def cbGetPaths(paths):
			num = len(paths)
			l = []
			l.append('paths=%s' % num)
			for x in xrange(num):
				l.append('path%s=%s' % (x, paths[x]))
			return '&'.join(l)
			
		return self.mogilefs.get_paths(self.get_key()).addCallback(cbGetPaths)

class CreateOpen(PNFSCommand):
	"""
	I will take care of command: create_open
	"""
	def handle_photo(self):
		self.filename = self._genFilename()
		self.secret = self._genSecret()
		
		def cbCreateOpen(rsp):
			"""
			return the generated filename and secret,
			and the response received from mogilefs:
			fid, dev_count, devids, paths
			"""
			value = {
					'username': self.username,
					'filename': self.filename,
					'secret'  : self.secret
					}
			value.update(rsp.headers)
			return url.encode_url_string(value)
		
		d = self.mogilefs.create_open(self.get_key(), clas=self['class'])
		d.addCallback(cbCreateOpen)
		return d
		
	def handle_icon(self):
		self.filename = self._genFilename()
		
		def cbCreateOpen(rsp):
			value = {
					'filename': self.filename
					}
			value.update(rsp.headers)
			return url.encode_url_string(value)
			
		d = self.mogilefs.create_open(self.get_key(), clas=self['class'])
		d.addCallback(cbCreateOpen)
		return d
		
	def handle_meta(self):
		def cbCreateOpen(rsp):
			value = {
					'username': self.username,
					'filename': self.filename
					}
			value.update(rsp.headers)
			return url.encode_url_string(value)
			
		d = self.mogilefs.create_open(self.get_key(), clas=self['class'])
		d.addCallback(cbCreateOpen)
		return d
		
	def _genFilename(self):
		if self.has_attr('time'):
			t = int(self.time)
		else:
			t = int(time.time())
		return "%s%x" % (
				''.join([random.choice(string.digits) for i in xrange(5)]),
				(t - PAINIU_TIME)
				)
	
	def _genSecret(self):
		if not self.has_attr('secret'):
			return ''.join([random.choice(SECRET_CHARS) for i in xrange(8)])
		else:
			return self.secret


class CreateClose(PNFSCommand):
	"""
	I will take care of command: create_close
	"""
	def handle_photo(self):
		self.photo = model.Photo(self.username, self.filename, self.secret,
					self.width, self.height, self.size,
					self.content_type, 0, int(time.time()), 0)
		
		def gotMogileFSResponse(rsp):
			"""Insert the photo into database"""
			return self.photo.save().addErrback(self.rollback)
		
		d = self.mogilefs.create_close(self.get_key(), self.fid,
							self.devid, self.size, self.path)
		d.addCallback(gotMogileFSResponse)
		return d
		
	def handle_icon(self):
		d = self.mogilefs.create_close(self.get_key(), self.fid,
							self.devid, self.size, self.path)
		d.addCallback(lambda x: None)
		return d

	def handle_meta(self):
		d = self.mogilefs.create_close(self.get_key(), self.fid,
							self.devid, self.size, self.path)
		d.addCallback(lambda x: None)
		return d
		
	def rollback(self, fail):
		"""
		If database insertion is failed, we have to delete the file just 
		posted to mogilefs, otherwise, the remaining file will be unreachable.
		"""
		log.err(fail)
		def cbDel(result):
			if isinstance(result, failure.Failure) or isinstance(result, Exception):
				# mogilefs file deletion failed, just ignore it??
				# the remaining file will be unreachable
				# log.err(result)
				log.msg(result, isError=True)
			# anyway, this must be done:
			raise PNFSError, 'db'
			
		return self.mogilefs.delete(self.get_key()).addBoth(cbDel) # delete the file from mogilefs
		
class Disable(PNFSCommand):
	def handle_photo(self):
		return model.Photo.load(self.username, self.filename
			).addCallback(self.gotPhoto)
			
	def gotPhoto(self, photo):
		if photo is None:
			raise PNFSError('not_found', 'Photo')
		self.photo = photo
		self.photo.state = model.Photo.STATE_DISABLED
		self.photo.sizes = 0
		return self.photo.save().addCallback(self.deleteFiles)
		
	def deleteFiles(self, x):
		"""delete thumbnails"""
		p = self.photo
		keys = p.keys(thumbsOnly=True)
		defers = []
		for key in keys:
			defers.append(self.mogilefs.delete(key))

		d = defer.DeferredList(defers)
		d.addBoth(lambda x: None)
		return d

class Enable(PNFSCommand):
	def handle_photo(self):
		return model.Photo.load(self.username, self.filename
			).addCallback(self.gotPhoto)
			
	def gotPhoto(self, photo):
		if photo is None:
			raise PNFSError('not_found', 'Photo')
		photo.state = model.Photo.STATE_ACTIVE
		return photo.save()
	
class Delete(PNFSCommand):
	"""
	I will take care of command: delete
	"""
	def handle_photo(self):
		return model.Photo.load(self.username, self.filename
			).addCallback(self.gotPhoto)
			
	def gotPhoto(self, photo):
		if photo is None:
			raise PNFSError('not_found', 'Photo')
		self.photo = photo
		return self.photo.delete().addCallback(self.deleteFiles)		
		
	def deleteFiles(self, x):
		p = self.photo
		keys = p.keys()
		if p.content_type == 'image/jpeg':
			keys.append('%s-%s-meta' % (p.username, p.filename))
		defers = []
		for key in keys:
			defers.append(self.mogilefs.delete(key))
		
		d = defer.DeferredList(defers)
		d.addBoth(lambda x: None)
		return d
		
	def handle_icon(self):
		return self.mogilefs.delete(self.get_key()).addCallback(lambda x: None)

from pn import version as PNFS_version

class Version(PNFSCommand):
	def handle(self):
		return PNFS_version

handlers = {}
for name, value in globals().items():
	if isinstance(value, type):
		if issubclass(value, PNFSCommand):
			cmd = name[0].lower() + name[1:]
			cmd = ''.join([c if c.islower() else '_%s' % c.lower() for c in cmd])
			handlers[cmd] = value

class PNFSProtocol(basic.LineReceiver, policies.TimeoutMixin, object):
	mogilefs = None
	
	def _callLater(self, secs, fun, *args, **kw):
		reactor.callLater(secs, fun, *args, **kw)
	
	def succeed(self, result):
		if result is None:
			rsp = 'OK\r\n'
		else:
			if isinstance(result, dict):
				result = url.encode_url_string(result)
			rsp = 'OK %s\r\n' % result
		self.transport.write(rsp)
	
	def failed(self, fail):
		# fail.printTraceback()
		if fail.check(PNFSError, MogileFSError):
			code, msg = fail.value
		else:
			log.err(fail)
			code, msg = ('server_error', 'Internal server error')
		log.msg('%s: %s' % (code, msg), isError=True)
		self.transport.write('ERR %s %s\r\n' % (code, quote_plus(msg)))

	def connectionLost(self, reason):
		self.setTimeout(None)
		self.mogilefs = None
		self.transport = None
		
	def lineReceived(self, line):
		self.resetTimeout()
		self.pauseProducing()

		def allDone(ignored):
			self.resumeProducing()

		spaceIndex = line.find(' ')
		if spaceIndex != -1:
			cmd = line[:spaceIndex]
			args = url.decode_url_string(line[spaceIndex + 1:])
		else:
			cmd = line
			args = {}
		d = defer.maybeDeferred(self.processCommand, cmd, **args)
		d.addCallbacks(self.succeed, self.failed)
		d.addErrback(log.err)

		# XXX It burnsss
		# LineReceiver doesn't let you resumeProducing inside
		# lineReceived atm
		self._callLater(0, d.addBoth, allDone)

	def processCommand(self, cmd, **params):
		cmd = cmd.lower()
		
		handler = handlers.get(cmd, None)
		if handler is not None:
			return handler(self, params).handle()
			
		return defer.fail(PNFSError('unknown_command'))

class PNFSFactory(protocol.ServerFactory):
	"""Factory for PNFS server."""

	protocol = PNFSProtocol

	protocolArgs = None

	def __init__(self, **kwargs):
		self.protocolArgs = kwargs

	def buildProtocol(self, addr):
		p = protocol.ServerFactory.buildProtocol(self, addr)

		for arg, value in self.protocolArgs.iteritems():
			setattr(p, arg, value)
		return p

if __name__ == '__main__':
	for h in handlers.items():
		print h
