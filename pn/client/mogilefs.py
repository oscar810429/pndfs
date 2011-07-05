import re
import os
from urllib import unquote_plus

from twisted.internet import defer

from pn.core import stream as stream_mod
from pn.client import base, http
from pn.util import url
from pn.web import responsecode


class MogileFSError(Exception):
	"""Mogile Error occurred"""
	def __init__(self, code=None, message=""):
		Exception.__init__(self, code, message)
		self.code = code

	def __str__(self):
		s = self.__doc__ or self.__class__.__name__
		if self.code:
			s = '%s: %s' % (s, self.code)
		if self[0]:
			s = '%s: %s' % (s, self[0])
		s = '%s.' % s
		return s

class InvalidResponseError(MogileFSError):
	"""Invalid Mogile Response Error"""

class UnknownKeyError(MogileFSError):
	"""Mogile Unknown Key Error"""

def getError(code, msg):
	if code == "unknown_key":
		return UnknownKeyError(code, msg)
	elif code == "invalid_request":
		return InvalidResponseError(code, msg)
	return MogileFSError(code, msg)


class MogileFSRequest(object):
	"""MogileFS Client Request"""
	stream = None
	
	def __init__(self, cmd, headers):
		self.cmd = cmd
		self.headers = headers

class MogileFSChannelRequest(base.BaseClientChannelRequest):
	headers = None
	
	def lineReceived(self, line):
		if not line:
			return
		self.raw_response = line
		if self.raw_response.find(' ') > 0:
			parts = re.split('\s', self.raw_response, 2)
			# ERR <errcode> <errstr>
			if parts[0] == 'ERR':
				raise self._getError(parts[1], unquote_plus(parts[2]))
			# OK <response>
			elif parts[0] == 'OK':
				self.raw_response = parts[1]
			else:
				raise self._getError('invalid_request', self.raw_response)
		else:
			self.raw_response = ''
			
		self.createResponse()
		self.allContentReceived()
		self.processResponse()
		self.finishRequest()
		
	def _getError(self, code, msg):
		return getError(code, msg)

class MogileFSResponse(object):
	def __init__(self, raw_response, headers=None):
		self.raw_response = raw_response
		self.headers = headers
		if self.headers is None:
			self.headers = url.decode_url_string(self.raw_response)

	def has_key(self, key):
		return self.headers.has_key(key)

	def __getitem__(self, key):
		return self.headers[key]

	def items(self):
		for k, v in self.headers.items():
			yield (k, v)

class MogileFSClientProtocol(base.BaseClientProtocol):

	ChannelRequest = MogileFSChannelRequest

	def createResponse(self, chanRequest):
		return MogileFSResponse(chanRequest.raw_response)


def parseDests(rsp):
	dests = [];	 # [ (devid,path), (devid,path), ... ]

	# determine old vs. new format to populate destinations
	if not rsp.has_key('dev_count'):
		dests.append((rsp['devid'], rsp['path']))
	else:
		dev_count = int(rsp['dev_count'])
		for i in xrange (1, dev_count + 1):
			dests.append((rsp['devid_%d' % i] , rsp['path_%d' % i]))
	return dests

class HTTPFile(object):
	def __init__(self, mg, hc, clas, key, stream, length=None):
		self.mg		 = mg
		self.hc		 = hc
		self.clas		 = clas
		self.key		 = key
		self.stream	 = stream
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
		d = self.mg.create_open(self.key, self.clas, multi_dest=0)
		d.addCallbacks(self._got_dests, self._fail)
		return self.deferred

	def _got_dests(self, rsp):
		self.fid = rsp['fid']
		self.dests = parseDests(rsp)

		self._do_send(self.dests)

	def _do_send(self, dests):
		# TODO retry on failure
		if dests:
			self.devid, self.path = dests.pop(0)

			d = self.hc.put(self.path, body=self.stream)
			d.addCallbacks(self._create_close, self._fail)

		else:
			self._fail()

	def _create_close(self, rsp):
		rsp.discard()
		if rsp.code in (responsecode.OK, responsecode.CREATED):
			d = self.mg.create_close(self.key, self.fid, self.devid, self.length, self.path)
			d.addCallbacks(self._finish, self._fail)
		else:
			self._fail()

	def _finish(self, _):
		self.deferred.callback(self)

	def _fail(self, err=None):
		self.deferred.errback(err)

class MogileFSClient(base.BaseClient):
	def __init__(self, domain, hosts=None, clas=None, verify_data=False, verify_repcount=False,
				httpclient=None, connector=None, connTimeout=30, maintTime=300, cache=None):
		base.BaseClient.__init__(self, hosts, connector, connTimeout, maintTime, retry=3)
		self.factory.protocol = MogileFSClientProtocol
		
		self.domain = domain
		self.clas = clas
		
		self.cache = cache
		
		self.verify_data = verify_data
		self.verify_repcount = verify_repcount

		self.httpclient = httpclient
		if self.httpclient is None:
			self.httpclient = http.HTTPClient()
		
	def do_request(self, cmd, args):
		req = MogileFSRequest(cmd, args)
		return self.doRequest(req)
		
	def get_paths(self, key, noverify=1, zone=None):
		if self.cache is None:
			return self._get_paths(key, noverify, zone)
	
		cache_key = 'mogilefs_paths_%s' % key
	
		def cbGet(cached):
			if cached[0] is None:
				return self._get_paths(key, noverify, zone).addCallback(cbFunc)
			else:
				return cached[0]

		def ebGet(fail):
			return self._get_paths(key, noverify, zone)

		def cbFunc(paths):
			if len(paths) > 1:
				# cache it, when the replication is completed
				return self.cache.set(cache_key, paths).addBoth(cbSet, paths)
			else:
				return paths

		def cbSet(cacheResult, result):
			"""Always return the result"""
			return result

		return self.cache.get(cache_key).addCallbacks(cbGet, ebGet)
		
	def _get_paths(self, key, noverify=1, zone=None):
		def cbGetPaths(rsp):
			numpaths = int(rsp['paths'])
			return [rsp['path%d' % x] for x in xrange(1, numpaths + 1)]
			
		return self.do_request("get_paths", {
				'domain'   : self.domain,
				'key'      : key,
				'noverify' : noverify,
				'zone'     : zone
			}).addCallback(cbGetPaths)

	def create_open(self, key, clas=None, multi_dest=1):
		if clas is None:
			clas = self.clas
		return self.do_request("create_open", 	{
				'domain':	   self.domain,
				'class':	   clas,
				'key':		   key,
				'multi_dest':  multi_dest
			})

	def create_close(self, key, fid, devid, size, path):
		return self.do_request("create_close", {
				'fid':	   fid,
				'devid':   devid,
				'domain':  self.domain,
				'size':	   size,
				'key':	   key,
				'path':	   path
			})

	def send_file(self, key, stream, clas=None):
		if clas is None:
			clas = self.clas
		f = HTTPFile(self, self.httpclient, clas, key, stream)
		return f.send()

	def delete(self, key):
		return self.do_request('delete', {
				'domain': self.domain,
				'key': key
			})
