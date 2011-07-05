"""
Memcache client protocol for Twisted. See
L{http://cvs.danga.com/browse.cgi/wcmtools/memcached/doc/protocol.txt} for
any information.
"""

try:
	from collections import deque
except ImportError:
	class deque(list):
		def popleft(self):
			return self.pop(0)

try:
	import cPickle as pickle
except ImportError:
	import pickle
	
import time

from twisted.python import log
from twisted.internet import error

from pn.client import base


class NoSuchCommand(Exception):
	"""
	Exception raised when a non existent command is called.
	"""

class ClientError(Exception):
	"""
	Error caused by an invalid client call.
	"""


class ServerError(Exception):
	"""
	Problem happening on the server.
	"""

class MemcachedRequest(object):
	"""Memcached Client Request"""
	stream = None
	value = None

	def __init__(self, cmd, fullcmd, **kwargs):
		self.cmd = cmd
		self.fullcmd = fullcmd or cmd
		for k, v in kwargs.items():
			setattr(self, k, v)

class MemcachedChannelRequest(base.BaseClientChannelRequest):
	
	def submit(self):
		req = self.request
		self.channel.write('%s\r\n' % req.fullcmd)
		if req.value is not None:
			self.channel.write('%s\r\n' % req.value)
		self.finishWriting(None)
	
	def response(self, result):
		self.processResponse(result)
		self.finishRequest()
	
	def lineReceived(self, line):
		"""
		Receive line commands from the server.
		"""
		if not line:
			return
		if line == "STORED":
			self.response(True)
		elif line == "NOT_STORED":
			# Set response
			self.response(False)
		elif line == "END":
			req = self.request
			if req.cmd == "get":
				self.response((req.flags, req.value))
			elif req.cmd == "stats":
				self.response(req.values)
		elif line == "NOT_FOUND":
			# Incr/Decr/Delete
			self.response(False)
		elif line.startswith("VALUE"):
			# Prepare Get
			ign, key, flags, length = line.split()
			try:
				self.length = int(length)
			except ValueError:
				raise ServerError, "Invalid response from server: length=%s" % length
				
			self._getBuffer = []
			
			req = self.request
			assert req.key == key
			req.flags = int(flags)
			self.channel.setRawMode()
			
		elif line.startswith("STAT"):
			# Stat response
			ign, key, val = line.split(" ", 2)
			self.request.values[key] = val
		elif line.startswith("VERSION"):
			# Version response
			versionData = line.split(" ", 1)[1]
			self.response(versionData)
		elif line == "ERROR":
			log.err("Non-existent command sent.")
			raise NoSuchCommand
		elif line.startswith("CLIENT_ERROR"):
			errText = line.split(" ", 1)[1]
			log.err("Invalid input: %s" % (errText,))
			raise ClientError, errText
		elif line.startswith("SERVER_ERROR"):
			errText = line.split(" ", 1)[1]
			log.err("Server error: %s" % (errText,))
			raise ServerError, errText
		elif line == "DELETED":
			# Delete response
			self.response(True)
		elif line == "OK":
			# Flush_all response
			self.response(True)
		else:
			# Increment/Decrement response
			val = int(line)
			self.response(val)
			
	def handleContentChunk(self, data):
		self._getBuffer.append(data)
		
	def allContentReceived(self):
		self.finishedReading = True
		if self.request.cmd == 'get':
			self.request.value = "".join(self._getBuffer)
			

class MemcachedClientProtocol(base.BaseClientProtocol):
	ChannelRequest = MemcachedChannelRequest

class MemcachedSerializer(object):
	"""
	Handles serialization of python objects.

	To use a custom serializer/deserializer, set L{_FLAG_CUSTOM} to a valid
	flag value (e.g. 16) and override L{customLoads} and L{customDumps}.
	"""
	_FLAG_PICKLE = 1
	_FLAG_INTEGER = 2
	_FLAG_LONG = 4
	_FLAG_FLOAT = 8
	_FLAG_CUSTOM = 0

	pickleVersion = 2

	def customLoads(self, val):
		"""
		Override this in your custom class if you want to use a custom
		deserializer (e.g. marshal).
		"""
		raise NotImplementedError()

	def customDumps(self, val):
		"""
		Override this in your custom class if you want to use a custom
		serializer (e.g. marshal).
		"""
		raise NotImplementedError()

	def _pickleDumps(self, val):
		"""
		Wrapper pickle dumps.
		"""
		return pickle.dumps(val, self.pickleVersion)

	def serialize(self, val, flags):
		"""
		Manage flags and serialize data before sending object over the wire.
		"""
		if isinstance(val, str):
			pass
		elif isinstance(val, int):
			flags |= self._FLAG_INTEGER
			val = "%d" % val
		elif isinstance(val, long):
			flags |= self._FLAG_LONG
			val = "%d" % val
		elif isinstance(val, float):
			flags |= self._FLAG_FLOAT
			val = "%f" % val
		elif self._FLAG_CUSTOM:
			try:
				val = self.customDumps(val)
			except ValueError:
				flags |= self._FLAG_PICKLE
				val = self._pickleDumps(val)
			else:
				flags |= self._FLAG_CUSTOM
		else:
			flags |= self._FLAG_PICKLE
			val = self._pickleDumps(val)
		return val, flags

	def deserialize(self, result):
		"""
		Unserialize objects when retrieving it.
		"""
		flags, val = result
		if flags & self._FLAG_INTEGER:
			val = int(val)
		elif flags & self._FLAG_LONG:
			val = long(val)
		elif flags & self._FLAG_FLOAT:
			val = float(val)
		elif flags & self._FLAG_CUSTOM:
			val = self.customLoads(val)
		elif flags & self._FLAG_PICKLE:
			val = pickle.loads(val)
		return val, flags


class MemcachedClient(base.BaseClient):
	MAX_KEY_LENGTH = 250
	HOST_RETRIES = 10
	
	def __init__(self, serializer=None, **kwargs):
		base.BaseClient.__init__(self, **kwargs)
		self.factory.protocol = MemcachedClientProtocol
		self.serializer = serializer or MemcachedSerializer()

	def request(self, cmd, fullcmd, *args, **kwargs):
		req = MemcachedRequest(cmd, fullcmd, *args, **kwargs)
		if hasattr(req, 'key'):
			host = self._getHost(getattr(req, 'key'))
			if host is None:
				return defer.fail(error.ConnectError)
			else:
				setattr(req, 'addr', host.addr)
		return self.doRequest(req)

	def _getHost(self, key):
		"""
		Return the host matching the given C{key}.
		"""
		if not self.hosts:
			return
		hostHash = hash(key)
		now = time.time()
		for i in xrange(self.HOST_RETRIES):
			host = self.hosts[hostHash % len(self.hosts)]
			if host.addr in self.hostsDead and self.hostsDead[host.addr] > now - 5:
				hostHash += 1
			else:
				return host
				
	def incr(self, key, val=1):
		"""
		Increment the value of C{key} by given value (default to 1).
		C{key} must be consistent with an int. Return the new value.
		"""
		return self._incrdecr("incr", key, val)

	def decr(self, key, val=1):
		"""
		Decrement the value of C{key} by given value (default to 1).
		C{key} must be consistent with an int. Return the new value, coerced to
		0 if negative.
		"""
		return self._incrdecr("decr", key, val)

	def _incrdecr(self, cmd, key, val):
		"""
		Internal wrapper for incr/decr.
		"""
		key = str(key)
		if len(key) > self.MAX_KEY_LENGTH:
			return defer.fail(ClientError("Key too long"))
		fullcmd = "%s %s %d" % (cmd, key, int(val))		
		return self.request(cmd, fullcmd, key=key)

	def replace(self, key, val, flags=0, expireTime=0):
		"""
		Replace the given C{key}. It must already exists in the server.
		"""
		return self._set("replace", key, val, flags, expireTime)

	def add(self, key, val, flags=0, expireTime=0):
		"""
		Add the given C{key}. It must not exists in the server.
		"""
		return self._set("add", key, val, flags, expireTime)

	def set(self, key, val, flags=0, expireTime=0):
		"""
		Set the given C{key}.
		"""
		return self._set("set", key, val, flags, expireTime)

	def _set(self, cmd, key, val, flags, expireTime):
		"""
		Internal wrapper for setting values.
		"""
		key = str(key)
		if len(key) > self.MAX_KEY_LENGTH:
			return defer.fail(ClientError("Key too long"))
		val, flags = self.serializer.serialize(val, flags)
		length = len(val)
		fullcmd = "%s %s %d %d %d" % (cmd, key, flags, expireTime, length)
		return self.request(cmd, fullcmd, value=val, key=key, flags=flags, length=length, expireTime=expireTime)

	def get(self, key):
		"""
		Get the given C{key}. It doesn't support multiple keys.
		"""
		key = str(key)
		if len(key) > self.MAX_KEY_LENGTH:
			return defer.fail(ClientError("Key too long"))
		fullcmd = "get %s" % key
		
		return self.request("get", fullcmd, key=key, value=None, flags=0)\
				.addCallback(lambda x: self.serializer.deserialize(x))

	def stats(self):
		"""
		Get some stats from the server. It will be available as a dict.
		"""
		return self.request("stats", None, values={})

	def version(self):
		"""
		Get the version of the server.
		"""
		return self.request("version", None)

	def delete(self, key):
		"""
		Delete an existing C{key}.
		"""
		fullcmd = "delete %s" % key
		return self.request("delete", fullcmd, key=key)

	def flushAll(self):
		"""
		Flush all cached values.
		"""
		return self.request("flush_all", None)
	
