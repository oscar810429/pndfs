
import urlparse

from pn.core import stream as stream_mod
from pn.client import base
from pn.web.http import parseVersion

__version__ = 1.0


class BadResponseError(Exception):
	"""Invalid HTTP response error"""

class ProtocolError(Exception):
	"""Unsupported protocol error"""

class HTTPRequest(object):
	def __init__(self, method, uri, headers, stream=None):
		self.method = method
		self.uri = uri
		self.headers = headers

		if stream is not None:
			self.stream = stream_mod.IByteStream(stream)
		else:
			self.stream = None

class HTTPChannelRequest(base.BaseClientChannelRequest):
	# Instance vars
	chunkedIn = False
	headerlen = 0
	
	inHeaders = None
	partialHeader = ''
	
	outgoing_version = "HTTP/1.1"
	chunkedOut = False
	
	code = None
	version = None
	
	firstLine = 1

	def __init__(self, channel, request, closeAfter=False):
		base.BaseClientChannelRequest.__init__(self, channel, request)
		self.inHeaders = {}
		self.closeAfter = closeAfter
		
	def submitHeaders(self):
		l = []
		request = self.request
		if request.method == "HEAD":
			# No incoming data will arrive.
			self.length = 0

		l.append('%s %s %s\r\n' % (request.method, request.uri,
								   self.outgoing_version))
		if request.headers is not None:
			for name, value in request.headers.items():
				l.append("%s: %s\r\n" % (name, value))

		if request.stream is not None:
			if request.stream.length is not None:
				l.append("%s: %s\r\n" % ('Content-Length', request.stream.length))
			else:
				# Got a stream with no length. Send as chunked and hope, against
				# the odds, that the server actually supports chunked uploads.
				l.append("%s: %s\r\n" % ('Transfer-Encoding', 'chunked'))
				self.chunkedOut = True

		if self.closeAfter:
			l.append("%s: %s\r\n" % ('Connection', 'close'))
		else:
			l.append("%s: %s\r\n" % ('Connection', 'Keep-Alive'))
			
		l.append("\r\n")
		self.channel.writeSequence(l)

	def lineReceived(self, line):
		if self.firstLine:
			self.firstLine = 0
			self.gotInitialLine(line)
			return
			
		if self.chunkedIn:
			# Parsing a chunked input
			if self.chunkedIn == 1:
				# First we get a line like "chunk-size [';' chunk-extension]"
				# (where chunk extension is just random crap as far as we're concerned)
				# RFC says to ignore any extensions you don't recognize -- that's all of them.
				chunksize = line.split(';', 1)[0]
				try:
					self.length = int(chunksize, 16)
				except:
					raise BadResponseError, "Invalid chunk size, not a hex number: %s!" % chunksize
				if self.length < 0:
					raise BadResponseError, "Invalid chunk size, negative"

				if self.length == 0:
					# We're done, parse the trailers line
					self.chunkedIn = 3
				else:
					# Read self.length bytes of raw data
					self.channel.setRawMode()
			elif self.chunkedIn == 2:
				# After we got data bytes of the appropriate length, we end up here,
				# waiting for the CRLF, then go back to get the next chunk size.
				if line != '':
					raise BadResponseError, "Excess %d bytes sent in chunk transfer mode" % len(line)
				self.chunkedIn = 1
			elif self.chunkedIn == 3:
				# TODO: support Trailers (maybe! but maybe not!)

				# After getting the final "0" chunk we're here, and we *EAT MERCILESSLY*
				# any trailer headers sent, and wait for the blank line to terminate the
				# request.
				if line == '':
					self.allContentReceived()
					self.finishRequest()
		# END of chunk handling
		elif line == '':
			# Empty line => End of headers
			if self.partialHeader:
				self.headerReceived(self.partialHeader)
			self.partialHeader = ''
			self.allHeadersReceived()	 # can set chunkedIn
			self.createResponse()
			if self.chunkedIn:
				# stay in linemode waiting for chunk header
				pass
			elif self.length == 0:
				# no content expected
				self.allContentReceived()
				self.finishRequest()
			else:
				# await raw data as content
				self.channel.setRawMode()
				# Should I do self.pauseProducing() here?
			self.processResponse()
		else:
			self.headerlen += len(line)
			if self.headerlen > self.channel.maxHeaderLength:
				raise BadResponseError, 'Headers too long.'

			if line[0] in ' \t':
				# Append a header continuation
				self.partialHeader += line
			else:
				if self.partialHeader:
					self.headerReceived(self.partialHeader)
				self.partialHeader = line

	def rawDataReceived(self, data):
		"""Handle incoming content."""
		datalen = len(data)
		if datalen < self.length:
			self.handleContentChunk(data)
			self.length = self.length - datalen
		else:
			self.handleContentChunk(data[:self.length])
			extraneous = data[self.length:]
			channel = self.channel # could go away from allContentReceived.
			if not self.chunkedIn:
				self.allContentReceived()
				self.finishRequest()
			else:
				# NOTE: in chunked mode, self.length is the size of the current chunk,
				# so we still have more to read.
				self.chunkedIn = 2 # Read next chunksize

			channel.setLineMode(extraneous)

	def headerReceived(self, line):
		"""Store this header away. Check for too much header data
		   (> channel.maxHeaderLength) and abort the connection if so.
		"""
		nameval = line.split(':', 1)
		if len(nameval) != 2:
			raise BadResponseError, "No ':' in header."

		name, val = nameval
		val = val.lstrip(' \t')
		self.inHeaders[name] = val

	def allHeadersReceived(self):
		headers = self.inHeaders
		
		# Okay, now implement section 4.4 Message Length to determine
		# how to find the end of the incoming HTTP message.
		transferEncoding = headers.get('Transfer-Encoding', None)
		
		if transferEncoding == 'chunked':
			# Chunked
			self.chunkedIn = 1
		else:
			# No transfer-coding.
			self.chunkedIn = 0
			if headers.has_key('Content-Length'):
				try:
					self.length = int(headers.get('Content-Length'))
				except:
					raise BadResponseError, "Invalid header: Content-Length"

	def gotInitialLine(self, initialLine):
		parts = initialLine.split(' ', 2)

		# Parse the initial request line
		if len(parts) != 3:
			raise BadResponseError, 'Bad response line: %s' % initialLine

		strversion, self.code, message = parts

		try:
			protovers = parseVersion(strversion)
			if protovers[0] != 'http':
				raise ValueError()
		except ValueError:
			raise ProtocolError, "Unknown protocol: %s" % strversion


		self.version = protovers[1:3]

		# Ensure HTTP 0 or HTTP 1.
		if self.version[0] != 1:
			raise ProtocolError, "Only HTTP 1.x is supported."

	def allContentReceived(self):
		self.firstLine = 1
		base.BaseClientChannelRequest.allContentReceived(self)

	def finishRequest(self):
		if self.closeAfter:
			self.channel.loseConnection()
		else:
			if self.version > (1, 0):
				conn = self.inHeaders.get('Connection', None)
			else:
				conn = self.inHeaders.get('Connection', 'close')
			close = conn == 'close'
			if not close:
				close = self.inHeaders.get('Proxy-Connection', None) == 'close'
			if close:
				self.channel.loseConnection()
			
		base.BaseClientChannelRequest.finishRequest(self)

	def write(self, data):
		if not data:
			return
		elif self.chunkedOut:
			self.channel.writeSequence(("%X\r\n" % len(data), data, "\r\n"))
		else:
			self.channel.write(data)

	def createResponse(self):
		self.stream = stream_mod.ProducerStream(self.length)
		self.response = self.channel.createResponse(self)
		self.stream.registerProducer(self, True)

	def finishWriting(self, x):
		"""We are finished writing data."""
		if self.chunkedOut:
			# write last chunk and closing CRLF
			self.channel.write("0\r\n\r\n")
		base.BaseClientChannelRequest.finishWriting(self, x)


class HTTPResponse(object):
	"""An object representing an HTTP Response to be sent to the client.
	"""
	code = 200
	headers = None
	stream = None

	def __init__(self, code=None, headers=None, stream=None):
		if code is not None:
			self.code = int(code)

		self.headers = headers
		
		if stream is not None:
			self.stream = stream_mod.IByteStream(stream)

	def discard(self):
		if self.stream is not None:
			stream_mod.readAndDiscard(self.stream)

	def __repr__(self):
		if self.stream is None:
			streamlen = None
		else:
			streamlen = self.stream.length

		return "<%s.%s code=%d, streamlen=%s>" % (self.__module__, self.__class__.__name__, self.code, streamlen)


class HTTPClientProtocol(base.BaseClientProtocol):
	maxHeaderLength = 10240
	
	ChannelRequest = HTTPChannelRequest
	
	def createResponse(self, chanRequest):
		return HTTPResponse(chanRequest.code, chanRequest.inHeaders, chanRequest.stream)


class HTTPClient(base.BaseClient):
	def __init__(self, hosts=None, connector=None, connTimeout=30, maintTime=300, deadRetryTime=0, retry=2):
		base.BaseClient.__init__(self, hosts, connector, connTimeout, maintTime, deadRetryTime, retry)
		self.factory.protocol = HTTPClientProtocol
	
	def parseUrl(self, url):
		components = urlparse.urlsplit(url)
		try:
			host, port = components.netloc.split(':')
			port = int(port)
		except (ValueError, TypeError):
			host = components.netloc
			if components.scheme == 'http':
				port = 80
			else:
				raise NotImplementedError, "scheme %s unsupported for url %s" % (components.scheme, url)
		if components.path:
			path = urlparse.urlunsplit(['', ''] + list(components[2:]))
		else:
			path = urlparse.urlunsplit(['', '', '/'] + list(components[3:]))
		return components.scheme, components.netloc, host, port, path
	
	def request(self, method, url, headers=None, body=None):
		scheme, netloc, host, port, path = self.parseUrl(url)
		
		if headers is None:
			headers = {}
		
		headers['Host'] = netloc

		if not 'User-Agent' in headers:
			headers['User-Agent'] = 'YPHTTPClient/%s' % __version__
			
		request = HTTPRequest(method, path, headers, body)
		request.addr = (host, port)
		
		return self.doRequest(request)
	
	def get(self, url, headers=None):
		return self.request('GET', url, headers)
		
	def post(self, url, headers=None, body=None):
		return self.request('POST', url, headers, body)
		
	def put(self, url, headers=None, body=None):
		return self.request('PUT', url, headers, body)
	
