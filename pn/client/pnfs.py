import os

from twisted.internet import defer
from pn.client import base, mogilefs, http
from pn.web import responsecode


class PNFSError(mogilefs.MogileFSError):
	"""PNFSError Error occurred"""


class PNFSRequest(object):
	"""PNFS Client Request"""
	stream = None
	
	def __init__(self, cmd, headers):
		self.cmd = cmd
		self.headers = headers


class PNFSChannelRequest(mogilefs.MogileFSChannelRequest):
	def _getError(self, code, msg):
		return PNFSError(code, msg)


class PNFSResponse(mogilefs.MogileFSResponse):
	pass


class PNFSClientProtocol(base.BaseClientProtocol):

	ChannelRequest = PNFSChannelRequest

	def createResponse(self, chanRequest):
		return PNFSResponse(chanRequest.raw_response)
		

class PNFSFile(object):
	def __init__(self, pnfs, httpclient, clas, username, filename, stream, length):
		self.pnfs			 = pnfs
		self.httpclient		 = httpclient
		self.username		 = username
		self.filename = filename
		self.clas			 = clas
		self.stream			 = stream
		self.length = length

		if self.length is None:
			if hasattr(stream, 'length') and stream.length:
				self.length = stream.length
			elif isinstance(stream, str):
				self.length = len(stream)
			elif isinstance(stream, file):
				self.length = os.fstat(stream.fileno()).st_size

	def send(self):
		self.deferred = defer.Deferred()
		d = self.create_open()
		d.addCallbacks(self.cb_create_open, self._fail)
		return self.deferred
		
	def create_open(self):
		return self.pnfs.create_open(self.clas, self.username, self.filename)

	def cb_create_open(self, rsp):
		self.fid = rsp['fid']
		self.filename = rsp['filename']
		self.dests = mogilefs.parseDests(rsp)
		self._do_send(self.dests)

	def _do_send(self, dests):
		# TODO retry on failure
		if dests:
			self.devid, self.path = dests.pop(0)

			d = self.httpclient.put(self.path, body=self.stream)
			d.addCallbacks(self.cb_send, self._fail)

		else:
			self._fail()

	def cb_send(self, rsp):
		rsp.discard()
		if rsp.code in (responsecode.OK, responsecode.CREATED):
			d = self.create_close()
			d.addCallbacks(self._finish, self._fail)
		else:
			self._fail()
			
	def create_close(self):
		return self.pnfs.create_close(self.clas, self.username, self.filename,
				self.fid, self.devid, self.length, self.path)

	def _finish(self, _):
		self.deferred.callback(self)

	def _fail(self, err=None):
		self.deferred.errback(err)

class PNFSPhoto(PNFSFile):
	def __init__(self, pnfs, httpclient, username, width, height, content_type, stream, length=None):
		PNFSFile.__init__(self, pnfs, httpclient, 'photo', username, None, stream, length)
		self.width = width
		self.height = height
		self.content_type = content_type
		
	def cb_create_open(self, rsp):
		PNFSFile.cb_create_open(self, rsp)
		self.secret = rsp['secret']
		
	def create_close(self):
		return self.pnfs.create_close(self.clas, self.username, self.filename,
				self.fid, self.devid, self.length, self.path, secret=self.secret,
				width=self.width, height=self.height, content_type=self.content_type)

class PNFSIcon(PNFSFile):
	def __init__(self, pnfs, httpclient, username, stream, length=None):
		PNFSFile.__init__(self, pnfs, httpclient, 'icon', username, None, stream, length)
	
class PNFSMeta(PNFSFile):
	def __init__(self, pnfs, httpclient, username, filename, stream, length=None):
		PNFSFile.__init__(self, pnfs, httpclient, 'meta', username, filename, stream, length)

class PNFSClient(base.BaseClient):
	def __init__(self, hosts=None, httpclient=None, connector=None, connTimeout=30, maintTime=300):
		base.BaseClient.__init__(self, hosts, connector, connTimeout, maintTime)
		self.factory.protocol = PNFSClientProtocol
		
		self.httpclient = httpclient
		if self.httpclient is None:
			self.httpclient = http.HTTPClient()
		
	def do_request(self, cmd, args):
		req = PNFSRequest(cmd, args)
		return self.doRequest(req)
		
	def create_open(self, clas, username, filename=None):
		return self.do_request("create_open", 	{
				'class':       clas,
				'username':	   username,
				'filename':    filename
			})

	def create_close(self, clas, username, filename,
					fid, devid, size, path, **kwargs):
		args = {
			'class': clas,
			'username':	username,
			'filename': filename,
			'fid':	   fid,
			'devid':   devid,
			'size':	   size,
			'path':	   path
		}
		if kwargs:
			args.update(kwargs)
		return self.do_request("create_close", args)
	
	def send_photo(self, username, width, height, content_type, stream, length=None):
		f = PNFSPhoto(self, self.httpclient, username, width, height, content_type, stream, length)
		return f.send()
		
	def send_icon(self, username, stream, length=None):
		f = PNFSIcon(self, self.httpclient, username, stream, length=None)
		return f.send()
		
	def send_meta(self, username, filename, stream, length=None):
		f = PNFSMeta(self, self.httpclient, username, filename, stream, length)
		return f.send()
		
	def __getattr__(self, name):
		if '_' in name:
			cmd, clas = name.split('_', 1)
		else:
			cmd, clas = name, None
		if cmd not in ('enable', 'disable', 'delete'):
			raise AttributeError, name
		if clas is not None and clas not in ('photo', 'icon', 'meta'):
			raise AttributeError, name
		def _func(*args, **kwargs):
			if clas is not None:
				params = {
					'class': clas,
					'username': args[0],
					'filename': args[1]
				}
			else:
				if args[0] not in ('photo', 'icon', 'meta'):
					raise RuntimeError, 'invalid argument \'%s\'' % args[0]
				params = {
					'class': args[0],
					'username': args[1],
					'filename': args[2]
				}
			return self.do_request(cmd, params)
		setattr(self, name, _func)
		return _func
