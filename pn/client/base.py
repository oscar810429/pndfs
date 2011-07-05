import copy
import time
import random

from twisted.python import log, failure
from twisted.internet import defer, error, protocol, reactor
from twisted.protocols import basic, policies

from pn.util import url
from pn.core import stream as stream_mod

try:
	from collections import deque
except ImportError:
	class deque(list):
		def popleft(self):
			return self.pop(0)


class BaseClientRequest(object):
	"""Base Client Request"""
	
	def __init__(self, cmd, headers, stream=None):
		self.cmd = cmd
		self.headers = headers
		self.stream = stream
		
		if stream is not None:
			self.stream = stream_mod.IByteStream(stream)
		else:
			self.stream = None
			
	def __str__(self):
		return '<%s:%s>' % (self.__class__.__name__, self.cmd)

class BaseClientChannelRequest(object):
	length = None
	
	finished = False
	finishedWriting = False
	finishedReading = False
	
	channel = None
	stream = None
	
	responseDefer = None
	
	def __init__(self, channel, request):
		self.channel = channel
		self.request = request
		self.responseDefer = defer.Deferred()

	def lineReceived(self, line):
		raise NotImplementedError, "must be implemented in subclass"
		
	def rawDataReceived(self, data):
		"""Handle incoming content."""
		datalen = len(data)
		if datalen < self.length:
			self.handleContentChunk(data)
			self.length = self.length - datalen
		else:
			self.handleContentChunk(data[:self.length])
			extraneous = data[self.length:]
			self.allContentReceived()
			self.channel.setLineMode(extraneous)
	
	def allContentReceived(self):
		self.finishedReading = True
		if self.stream is not None and not self.stream.closed:
			self.stream.finish()
		
	def finishRequest(self):
		self.finished = True
		self.channel.requestFinished(self)
		
	def submit(self):
		self.submitHeaders()
		
		if self.request.stream:
			d = stream_mod.StreamProducer(self.request.stream).beginProducing(self)
			d.addCallback(self.finishWriting).addErrback(self.abortWithError)
		else:
			self.finishWriting(None)

	def submitHeaders(self):
		"""Write request headers"""
		r = self.request
		self.channel.write("%s %s\r\n" % (r.cmd, url.encode_url_string(r.headers)))

	def write(self, data):
		if not data:
			return
		self.channel.write(data)

	def finishWriting(self, x=None):
		"""We are finished writing data."""
		self.finishedWriting = True

	def abortWithError(self, err):
		if self.stream is not None:
			self.stream.finish(err)
		if self.responseDefer:
			d = self.responseDefer
			del self.responseDefer
			d.errback(err)
		self.finishRequest()

	def connectionLost(self, reason):
		if not self.finished:
			self.abortWithError(reason)
		
	def createResponse(self):
		if self.length:
			self.stream = stream_mod.ProducerStream()
			self.response = self.channel.createResponse(self)
			self.stream.registerProducer(self, True)
		else:
			self.response = self.channel.createResponse(self)

	def processResponse(self, result=None):
		if result is None:
			result = self.response
		if self.responseDefer:
			d = self.responseDefer
			del self.responseDefer
			d.callback(result)

	def handleContentChunk(self, data):
		if self.stream:
			self.stream.write(data)
		
	def registerProducer(self, producer, streaming):
		"""Register a producer.
		"""
		self.channel.registerProducer(producer, streaming)

	def unregisterProducer(self):
		self.channel.unregisterProducer()
			
	# producer interface
	def pauseProducing(self):
		if not self.finishedReading:
			self.channel.pauseProducing()

	def resumeProducing(self):
		if not self.finishedReading:
			self.channel.resumeProducing()

	def stopProducing(self):
		if not self.finishedReading:
			self.channel.stopProducing()

class BaseClientProtocol(basic.LineReceiver, policies.TimeoutMixin, object):
	"""Base Client Protocol"""
	timeOut = 60
	
	chanRequest = None
	
	ChannelRequest = BaseClientChannelRequest
	
	pool = None
	
	def __init__(self):
		self._requests = deque()
	
	def submitRequest(self, request, *args, **kwargs):
		req = self.ChannelRequest(self, request, *args, **kwargs)
		
		if self.chanRequest is not None:
			self._requests.append(req)
		else:
			self.chanRequest = req
			req.submit()
		return req.responseDefer
		
	def write(self, data):
		self.setTimeout(self.timeOut)
		self.transport.write(data)
		
	def writeSequence(self, sequence):
		self.setTimeout(self.timeOut)
		self.transport.writeSequence(sequence)

	def lineReceived(self, line):
		if not self.chanRequest:
			# server sending random unrequested data.
			self.transport.loseConnection()
			return
		
		self.setTimeout(None)
		try:
			self.chanRequest.lineReceived(line)
			self.setTimeout(self.timeOut)
		except Exception, err:
			self.chanRequest.abortWithError(failure.Failure(err))

	def rawDataReceived(self, data):
		"""Handle incoming content."""
		if not self.chanRequest:
			# server sending random unrequested data.
			self.transport.loseConnection()
			return
		
		self.setTimeout(None)
		try:
			self.chanRequest.rawDataReceived(data)
			self.setTimeout(self.timeOut)
		except Exception, err:
			self.chanRequest.abortWithError(failure.Failure(err))

	def createResponse(self, chanRequest):
		raise NotImplementedError, "must be implemented in subclass"
		
	def requestFinished(self, request):
		"""Request done."""
		if self.chanRequest is not None:
			del self.chanRequest
		
		self.setTimeout(None)
		
		if self._requests:
			self.chanRequest = self._requests.popleft()
			self.chanRequest.submit()
			return
			
		if self.pool and not self.transport.disconnecting:
			self.pool.freeProtocol(self)
			
	def connectionLost(self, reason):
		self.setTimeout(None)
		# Tell all requests to abort.
		if self.chanRequest is not None:
			req = self.chanRequest
			del self.chanRequest
			req.connectionLost(reason)
		while self._requests:
			self._requests.popleft().connectionLost(reason)
			
		if self.pool:
			self.pool.protocolConnectionLost(self, reason)
			
	def loseConnection(self):
		self.transport.loseConnection()
		
	def makeConnection(self, transport):
		basic.LineReceiver.makeConnection(self, transport)
		if self.pool:
			self.pool.protocolCreated(self)
		
	def registerProducer(self, producer, streaming):
		"""Register a producer."""
		self.transport.registerProducer(producer, streaming)

	def unregisterProducer(self):
		self.transport.unregisterProducer()


class ClientProtocolPool(object):
	def __init__(self, addr, factory, maxConn=50, maxIdleTime=600):
		self.addr = addr
		self.factory = factory
		self.maxConn = maxConn
		self.maxIdleTime = maxIdleTime
		
		self._busy = []
		self._idle = []
		self._size = 0
		self.dead = False
		
		self.deferredRequests = deque()
		
	def protocolCreated(self, protocol):
		if self.dead:
			self.dead = False
			
		self._size += 1
		self.touch(protocol)
		
		if self.deferredRequests: # if there's deferred requests, return this protocol
			self._busy.append(protocol)
			self.deferredRequests.popleft().callback(protocol)
		else:
			self._idle.append(protocol)
			protocol.busy = False
	
	def deferRequest(self):
		d = defer.Deferred()
		self.deferredRequests.append(d)
		return d
		
	def markDead(self, reason):
		log.msg('Host[%s:%s] is dead' % self.addr)
		
		if self.dead:
			return
			
		self.dead = True
		
		while self.deferredRequests:
			self.deferredRequests.popleft().errback(reason)
		
		self._busy = []
		self._idle = []
		self._size = 0
	
	def create(self):
		self.factory.createProtocol(self.addr)
		return self.deferRequest()
		
	def get(self, wait=True):
		try:
			p = self._idle.pop(0)
			self._busy.append(p)
			self.touch(p)
			return p
		except IndexError:
			if not wait:
				return None
			if self._size < self.maxConn:
				return self.create()
			elif self._busy:
				# wait busy conn to be idle
				return self.deferRequest()
			return None # should not happen if maxConn > 0
		
	def touch(self, p):
		p.last_access = int(time.time())
		p.busy = True
		
	def free(self, protocol):
		assert protocol.addr == self.addr
		
		if self.deferredRequests: # if there's deferred requests, return this protocol
			self.touch(protocol)
			self.deferredRequests.popleft().callback(protocol)
			return
		
		try:
			self._busy.remove(protocol)
		except:
			log.err()
		
		self._idle.append(protocol)
		protocol.busy = False
	
	def remove(self, protocol):
		assert protocol.addr == self.addr
		
		if protocol.busy:
			ls = (self._busy, self._idle)
		else:
			ls = (self._idle, self._busy)
		
		try:
			ls[0].remove(protocol)
			self._size -= 1
		except:
			try:
				ls[1].remove(protocol)
				self._size -= 1
			except: # already removed
				pass
	
	def maintain(self):
		expire = int(time.time()) - self.maxIdleTime
		
		idles = copy.copy(self._idle)
		for p in idles:
			if not p.connected:
				log.msg('removing disconnected protocol %s from idle pool' % str(p))
				self.remove(p)
			elif p.last_access < expire:
				log.msg('removing expired protocol %s' % str(p))
				p.loseConnection()
				self.remove(p)
		busies = copy.copy(self._busy)
		for p in busies:
			if not p.connected:
				log.msg('removing disconnected protocol %s from busy pool' % str(p))
				self.remove(p)


class PooledClientFactory(protocol.ClientFactory):
	protocol = BaseClientProtocol
	
	def __init__(self, pool):
		self.pool = pool

	def buildProtocol(self, addr):
		p = protocol.ClientFactory.buildProtocol(self, addr)
		p.addr = (addr.host, addr.port)
		p.pool = self.pool
		return p

	def clientConnectionLost(self, connector, reason):
		addr = (connector.host, connector.port)
		self.pool.connectionLost(addr, reason)

	def clientConnectionFailed(self, connector, reason):
		addr = (connector.host, connector.port)
		self.pool.connectionFailed(addr, reason)


class BaseClient(object):
	FactoryClass = PooledClientFactory
	
	def __init__(self, hosts=None, connector=None, connTimeout=30, maintTime=300, deadRetryTime=5, retry=0, **kwargs):
		self.factory = self.FactoryClass(self)
		self.connector = connector or reactor
		self.connTimeout = connTimeout
		self.maintTime = maintTime
		self.deadRetryTime = deadRetryTime
		self.retry = retry
		self.hosts = []
		self.hostsPool = {}
		self.hostsDead = {}
		
		if hosts is not None:
			for host in hosts:
				ip, port = host.split(":")
				port = int(port)
				self.addHost((ip, port))
				
		self.maintID = reactor.callLater(self.maintTime, self._selfMaintain)
	
	def addHost(self, addr):
		pool = self.getPool(addr)
		self.hosts.append(pool)
		
	def protocolCreated(self, protocol):
		addr = protocol.addr
		pool = self.getPool(addr)
		pool.protocolCreated(protocol)
		if self.hostsDead.has_key(addr):
			self.hostsDead.remove(addr)
	
	def getPool(self, addr):
		if self.hostsPool.has_key(addr):
			return self.hostsPool[addr]
		pool = self.hostsPool[addr] = ClientProtocolPool(addr, self)
		return pool
		
	def protocolConnectionLost(self, protocol, reason):
		addr = protocol.addr
		pool = self.getPool(addr)
		pool.remove(protocol)
	
	def connectionLost(self, addr, reason):
		self._maybeDead(addr, reason)
	
	def connectionFailed(self, addr, reason):
		self._maybeDead(addr, reason)
		
	def _maybeDead(self, addr, reason):
		if reason.check(error.ConnectionDone, error.ConnectionLost):
			return
		pool = self.getPool(addr)
		if pool.dead:
			return
		#if reason.check(ConnectionRefusedErrr,...):
		pool.markDead(reason)
	
	def createProtocol(self, addr):
		self.connector.connectTCP(addr[0], addr[1], self.factory, self.connTimeout)
		
	def freeProtocol(self, protocol):
		pool = self.getPool(protocol.addr)
		pool.free(protocol)
		
	def getProtocol(self, addr=None):
		if addr is not None:
			now = time.time()
			# try dead hosts every 5 seconds
			# if host is down and last down time is
			# less than 5 seconds, ignore
			if addr in self.hostsDead and self.hostsDead[addr] > now - self.deadRetryTime:
				return None
			
			return self.getPool(addr).get()
		else:
			p = self._getRandomProtocol(wait=False)
			if p is not None:
				return p
			
			# no idle protocol found
			return self._getRandomProtocol(wait=True)
	
	def _getRandomProtocol(self, wait=True):
		size = len(self.hostsPool)
		
		if size == 0:
			return None
		
		if size > 15:
			tries = 15
		else:
			tries = size
			
		pools = self.hostsPool.values()
		
		idx = random.randint(1, size)
		
		for t in xrange(tries):
			pool = pools[idx % size]
			idx += 1
			
			p = pool.get(wait)
			if p is not None:
				return p
		return None
		
	def _selfMaintain(self):
		self.maintID = None
		pools = self.hostsPool.values()
		for pool in pools:
			pool.maintain()
		self.maintID = reactor.callLater(self.maintTime, self._selfMaintain)
		
	def doRequest(self, request):
		if hasattr(request, 'addr'):
			d = self.getProtocol(getattr(request, 'addr'))
		else:
			d = self.getProtocol()
		if d is None:
			raise error.ConnectError, "Can not connect to host"
		
		if self.retry and not hasattr(request, 'retry'):
			setattr(request, 'retry', self.retry)
		
		if isinstance(d, defer.Deferred):
			d.addCallback(self._doRequest, request)
			d.addErrback(self._errConn, request)
			return d
		else:
			return self._doRequest(d, request)
		
	def _doRequest(self, protocol, request):
		return protocol.submitRequest(request)
		
	def _errConn(self, fail, request):
		log.err(fail)
		fail.trap(error.ConnectError) # I only retry when ConnectError happened
		if self.retry and hasattr(request, 'retry'):
			if request.retry:
				request.retry -= 1
				return self.doRequest(request)
		fail.raiseException()
