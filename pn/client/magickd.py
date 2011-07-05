import copy

from pn.core import stream as stream_mod
from pn.client import base, http
from pn.web import responsecode


class ClientError(Exception):
	""" Invalid magickd command error """

class MagickdError(Exception):
	""" Magickd error """
	
class ServerError(Exception):
	""" Magickd server error """
	
class FileTooLargeError(Exception):
	""" File too large error """
	
class UnsupportedImageFileError(Exception):
	""" Unsupported image file error """
	

class MagickdRequest(http.HTTPRequest):
	method = 'POST'
	
	def __init__(self, args, stream, uri='/magickd/'):
		self.args = args
		self.stream = stream
		self.uri = uri
		self.headers = {
			'X-ImageMagick-Convert': self.args
		}
		http.HTTPRequest.__init__(self, self.method, self.uri, self.headers, self.stream)
		
	def __str__(self):
		return '<%s:%s>' % (self.__class__.__name__, self.args)
		

class MagickdChannelRequest(http.HTTPChannelRequest):
	pass

class MagickdResponse(http.HTTPResponse):
	pass
	
class MagickdClientProtocol(base.BaseClientProtocol):
	maxHeaderLength = 10240

	ChannelRequest = MagickdChannelRequest

	def createResponse(self, chanRequest):
		return MagickdResponse(chanRequest.code, chanRequest.inHeaders, chanRequest.stream)
		

class MagickdClient(base.BaseClient):
	http_imagemagick_uri = '/magickd/'
	
	def __init__(self, *args, **kwargs):
		base.BaseClient.__init__(self, *args, **kwargs)
		if kwargs and kwargs.has_key('uri'):
			self.http_imagemagick_uri = kwargs['uri']
		if kwargs and kwargs.has_key('httpclient'):
			self.httpclient = kwargs['httpclient']
		else:
			self.httpclient = http.HTTPClient()
		self.factory.protocol = MagickdClientProtocol
	
	def _doRequest(self, protocol, request):
		""" Nginx require Host header """
		headers = request.headers
		headers['Host'] = protocol.addr[0]
		return protocol.submitRequest(request)
	
	def do_request(self, args, stream):
		req = MagickdRequest(args, stream, self.http_imagemagick_uri)
		def cbReq(rsp):
			code = rsp.code
			if code == responsecode.OK:
				return rsp
			elif code == responsecode.UNSUPPORTED_MEDIA_TYPE:
				raise UnsupportedImageFileError, rsp
			elif code == responsecode.REQUEST_ENTITY_TOO_LARGE:
				raise FileTooLargeError, rsp
			elif code == responsecode.INTERNAL_SERVER_ERROR:
				raise ServerError, rsp
			elif code == responsecode.BAD_REQUEST:
				raise ClientError, rsp
			else:
				raise MagickdError, rsp
		
		def ebReq(fail):
			fail.trap(http.BadResponseError)
			raise ServerError()
		
		return self.doRequest(req).addCallbacks(cbReq, ebReq)
		
	def convert(self, args, stream):
		return self.do_request(args, stream)

	def convertURL(self, args, urls):
		req = (args, copy.copy(urls))
		return self._getStream(req)
		
	def _getStream(self, req):
		urls = req[1]
		if urls:
			url = urls.pop(0)
			d = self.httpclient.get(url)
			d.addCallback(self._cbGetStream, req)
			d.addErrback(self._ebGetStream, req)
			return d
		else:
			raise ClientError, 'Failed to get file stream'
			
	def _cbGetStream(self, rsp, req):
		if rsp.code == responsecode.OK:
			return self.convert(req[0], rsp.stream)
		return self._getStream(req)
		
	def _ebGetStream(self, fail, req):
		return self._getStream(req)
		
