import random
from collections import deque

from zope.interface import implements
from twisted.python import log
from twisted.internet import defer

from pn.db.interfaces import IDatabaseLocator
from pn.db.model import Model, Field


class ClusterError(Exception):
	"""Cluster Error"""

class Database(Model):
	dbapi = 'MySQLdb'
	table = 'pnc_databases'
	fields = (
			Field('db_id', type='int', ispk=True),
			Field('shard_id', type='int'),
			Field('role', type='string', default='master'), # master/slave
			Field('host', type='string'),
			Field('port', type='int', default=3306),
			Field('db_name', type='string'),
			Field('username', type='string'),
			Field('password', type='string'),
			Field('extra_params', type='string')
		)
		
	def connect(self):
		kwargs = {
			'host'  : self.host,
			'port'  : self.port,
			'db'    : self.db_name,
			'user'  : self.username,
			'passwd': self.password
		}
		
		if self.extra_params:
			pairs = self.extra_params.split('&')
			for pair in pairs:
				kv = pair.split('=')
				kwargs[kv[0]] = kv[1]
		
		from twisted.enterprise import adbapi
		self.connPool = adbapi.ConnectionPool(self.dbapi, **kwargs)
		return self.connPool
	
	def disconnect(self):
		if hasattr(self, 'connPool'):
			self.connPool.close()
			
	def getConnection(self):
		if hasattr(self, 'connPool'):
			return getattr(self, 'connPool')
		try:
			return self.connect()
		except:
			log.err()
	
class Shard(Model):
	table = 'pnc_shards'
	fields = (
			Field('shard_id', type='int', ispk=True),
			Field('weight', type='int', default=1)
		)
	
	def __init__(self, *args, **kwargs):
		Model.__init__(self, *args, **kwargs)
		self.master = None
		self.slaves = deque()
	
	def addServer(self, db):
		if db.role == 'master':
			if self.master is not None:
				self.slaves.append(self.master)
			self.master = db
		else:
			self.slaves.append(db)
			
	def startup(self):
		# if self.master is not None:
		# 	self.master.connect()
		# for slave in self.slaves:
		# 	slave.connect()
		pass
		
	def shutdown(self):
		if self.master is not None:
			self.master.disconnect()
		for slave in self.slaves:
			slave.disconnect()
		
	def getWritable(self):
		if self.master is None:
			return None
		return self.master.getConnection()
		
	def getReadable(self):
		if self.slaves:
			db = self.slaves.popleft()
			self.slaves.append(db)
			return db.getConnection()
		return self.getWritable()

class UserMapping(Model):
	table = 'pnc_user_mappings'
	fields = (
			Field('username', type='string', ispk=True),
			Field('shard_id', type='string')
		)

class Cluster(object):
	def __init__(self):
		self.shards = {}
		self.buckets = []
		
	def startup(self):
		log.msg('Starting database cluster')
		
		def databasesLoaded(dbs):
			databases = dbs
			
			def shardsLoaded(shards):
				for shard in shards:
					log.msg('Init shard %s' % shard)
					self.shards[shard.shard_id] = shard
			
				for db in databases:
					if db.shard_id in self.shards:
						self.shards[db.shard_id].addServer(db)
					else:
						log.msg('Shard[%s] is not exists' % db.shard_id, isError=True)
			
				for shard in self.shards.values():
					shard.startup() # init connection pool
					for i in xrange(shard.weight):
						self.buckets.append(shard)
				
				log.msg('Finish cluster initialzing.')
				return self.shards
			
			return Shard.loadAll().addCallback(shardsLoaded)
		
		return Database.loadAll().addCallback(databasesLoaded)
		
	def addShard(self, shard):
		self.shards[shard.shard_id] = shard
		shard.startup()
		for i in xrange(shard.weight):
			self.buckets.append(shard)
		
	def shutdown(self):
		for shard in self.shards.values():
			shard.shutdown()
		self.shards.clear()
		self.buckets = []
		
	def getShard(self, username):
		def gotMapping(mapping):
			if mapping is None:
				# select a shard for new username
				shard = random.choice(self.buckets)
				log.msg('Creating mapping for user[%s] at shard[%s]' % (username, shard.shard_id))
				mapping = UserMapping(username, shard.shard_id)
				
				def error(fail):
					# log.err(fail)
					log.msg(fail, isError=True)
					raise ClusterError, 'Error saving mapping: %s' % mapping
				
				return mapping.save().addCallbacks(lambda x: shard, error)
			
			if self.shards.has_key(mapping.shard_id):
				return self.shards[mapping.shard_id]
				
			msg = 'Shard[%s] of mapping[%s] is not exists' % (mapping.shard_id, mapping)
			log.msg(msg, isError=True)
			raise ClusterError, msg
		
		d = UserMapping.load(username)
		d.addCallback(gotMapping)
		return d

# Here is some DatabaseLocators
class SimpleDatabaseLocator(object):
	"""docstring for SimpleDatabaseLocator"""
	implements(IDatabaseLocator)
	
	def __init__(self, connPool):
		self.connPool = connPool
		
	def getDatabase(self, *args, **kwargs):
		"""docstring for getDatabase"""
		return defer.succeed(self.connPool)
		
	def getWritable(self, *args, **kwargs):
		"""docstring for getWritable"""
		return self.getDatabase(*args, **kwargs)
	
	def getReadable(self, *args, **kwargs):
		"""docstring for getReadable"""
		return self.getDatabase(*args, **kwargs)

class SingleDatabaseLocator(object):
	implements(IDatabaseLocator)

	def __init__(self, database):
		self.database = database

	def getDatabase(self, *args, **kwargs):
		return self.database.getConnection()

	def getWritable(self, *args, **kwargs):
		return self.getDatabase(*args, **kwargs)

	def getReadable(self, *args, **kwargs):
		return self.getDatabase(*args, **kwargs)

class ShardDatabaseLocator(object):
	implements(IDatabaseLocator)

	def __init__(self, shard):
		self.shard = shard

	def getDatabase(self, *args, **kwargs):
		return self.getWritable(*args, **kwargs)

	def getWritable(self, *args, **kwargs):
		return self.shard.getWritable()

	def getReadable(self, *args, **kwargs):
		return self.shard.getReadable()

class ClusteredLocator(object):
	implements(IDatabaseLocator)

	def __init__(self, clster=None):
		self.cluster = clster or cluster

	def getDatabase(self, *args, **kwargs):
		"""Locate a database based on arguments passed in"""
		return self.getWritable(*args, **kwargs)

	def getWritable(self, *args, **kwargs):
		"""Locate a writable database based on arguments passed in"""
		d = self.cluster.getShard(args[0])
		d.addCallback(self._gotShard, True)
		return d

	def getReadable(self, *args, **kwargs):
		"""Locate a readable database based on arguments passed in"""
		d = self.cluster.getShard(args[0])
		d.addCallback(self._gotShard, False)
		return d

	def _gotShard(self, shard, writable=False):
		if shard is None:
			return None
		if writable:
			return shard.getWritable()
		else:
			return shard.getReadable()


cluster = Cluster()
locator = ClusteredLocator(cluster)

def initCluster(locator):
	"""This method must be called first"""
	global cluster
	
	for name, value in globals().items():
		if isinstance(value, type):
			if issubclass(value, Model):
				setattr(value, 'locator', locator)
	
	def initShards():
		shards = defer.waitForDeferred(cluster.startup())
		yield shards
		shards = shards.getResult()
	d = defer.deferredGenerator(initShards)
	return d()
	
def setupLocator(modules):
	global locator
	for mod in modules:
		for name, value in mod.__dict__.items():
			if isinstance(value, type):
				if issubclass(value, Model):
					setattr(value, 'locator', locator)
	
def shutdown():
	global cluster
	cluster.shutdown()

def getShard(username):
	return cluster.getShard(username)		


