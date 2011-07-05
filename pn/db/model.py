"""
Simple O/R Mapping module

model relationship is not supported
"""

from itertools import izip

from zope.interface import implements

from pn.db.interfaces import IModelManager, IModelCache
from pn.db.persist import DatabasePersister

class ModelManager(object):
	implements(IModelManager)
	
	def __init__(self, klass, persister=None):
		self.model = klass
		self.persister = persister or DatabasePersister(klass)
		
	def load(self, *args, **kwargs):
		if not self.model.cache:
			return self.persister.load(*args, **kwargs)
			
		def cbGet(value):
			if value is None:
				return self.persister.load(*args, **kwargs).addCallback(cbFunc)
			else:
				return value
			
		def ebGet(error):
			return self.persister.load(*args, **kwargs)
			
		def cbFunc(result):
			if result is None:
				return result
			return self.model.cache.add(result).addBoth(cbSet, result)
			
		def cbSet(cacheResult, result):
			"""Always return the result"""
			return result
		
		return self.model.cache.get(*args, **kwargs).addCallbacks(cbGet, ebGet)
		
	def loadAll(self):
		"""
		Load all instances of the model
		
		The result will not be cached
		"""
		return self.persister.loadAll()
		
	def delete(self, instance):
		"""
		Delete the model instance
		
		I will delete database row first, then delete it from cache. So, if there is 
		something wrong when deleting cached instance, the cached version will still 
		available while the database row is deleted.
		"""
		assert instance.__class__ == self.model
		
		if not self.model.cache:
			return self.persister.delete(instance)
		
		def cbDel(result):
			return self.model.cache.remove(instance).addBoth(cbFunc, result)
		
		def cbFunc(delResult, result):
			return result
			
		return self.persister.delete(instance).addCallback(cbDel)
		
	def save(self, instance):
		"""Save the model instance"""
		assert instance.__class__ == self.model
		
		if not self.model.cache:
			return self.persister.save(instance)
		
		def cbSave(result):
			"""Update cached instance state/Add the instance to cache"""
			return self.model.cache.add(instance).addBoth(cbFunc, result)
			
		def cbFunc(setResult, result):
			return result
			
		return self.persister.save(instance).addCallback(cbSave)

class Field(object):
	counter = 0
	
	def __init__(self, name=None, column=None, ispk=False, type=None, default=None):
		self.name = name
		self.type = type
		self.column = column
		self.ispk = ispk
		self.default = default
		if self.default is None and self.type == 'int':
			self.default = 0
		
		self.number = Field.counter
		Field.counter += 1
		
	def __repr__(self):
		return '<Field#%s of (%s, %s, %s)>' % (self.number, self.name, self.type, self.default)

class ModelBase(type):
	def __new__(cls, name, bases, attrs):
		# If this isn't a subclass of Model, don't do anything special.
		if name == 'Model' or not filter(lambda b: issubclass(b, Model), bases):
			return super(ModelBase, cls).__new__(cls, name, bases, attrs)

		# Create the class.
		new_class = type.__new__(cls, name, bases, {'__module__': attrs.pop('__module__')})
		for name, value in attrs.items():
			new_class.add_class_attr(name, value)
			if name == 'fields':
				for field in value:
					if field.ispk:
						new_class.add_pk_field(field)
					else:
						new_class.add_non_pk_field(field)
		# if not hasattr(new_class, 'locator') or getattr(new_class, 'locator') is None:
		# 	raise RuntimeError, 'locator must be specified for model class'
		if attrs.has_key('managerFactory'):
			mgr = attrs['managerFactory'](new_class)
		else:
			mgr = ModelManager(new_class)
		new_class.add_class_attr('manager', mgr)
		cache = getattr(new_class, 'cache', False)
		if cache:
			setattr(cache, 'model', new_class)
		new_class._prepare()
		return new_class

class Model(object):
	__metaclass__ = ModelBase
	
	table = ''
	fields = ()
	locator = None # database locator, must be specified in subclasses
	cache = False # specify a IModelCache instance for caching support, disabled by default
	cacheExpire = 0 # specify cache expire time, only used when cache is specified
	
	def __init__(self, *args, **kwargs):
		for field in self.fields:
			setattr(self, field.name, field.default)
		
		if args:
			for val, field in izip(args, self.fields):
				setattr(self, field.name, val)
				
		if kwargs:
			for key, val in kwargs.items():
				if hasattr(self, key):
					setattr(self, key, val)
	
	@classmethod
	def add_class_attr(cls, name, value):
		setattr(cls, name, value)
	
	@classmethod
	def add_pk_field(cls, field):
		if not hasattr(cls, 'pk_fields'):
			setattr(cls, 'pk_fields', [])
		pk_fields = getattr(cls, 'pk_fields')
		pk_fields.append(field)
	
	@classmethod
	def add_non_pk_field(cls, field):
		if not hasattr(cls, 'non_pk_fields'):
			setattr(cls, 'non_pk_fields', [])
		non_pk_fields = getattr(cls, 'non_pk_fields')
		non_pk_fields.append(field)
	
	@classmethod
	def _prepare(cls):
		# fields = getattr(cls, 'fields')
		# fields.sort(key=lambda x: x.number)
		pass

	@classmethod
	def load(cls, *args, **kwargs):
		return cls.manager.load(*args, **kwargs)

	@classmethod
	def loadAll(cls):
		return cls.manager.loadAll()
		
	def save(self):
		return self.manager.save(self)
	
	def delete(self):
		return self.manager.delete(self)
		
	def __repr__(self):
		return '<%s at %#x>{%s}' % (
					self.__class__.__name__,
					id(self),
					', '.join(["%s=%s" % (field.name, getattr(self, field.name, field.default)) for field in self.fields])
				)

class MemcachedModelCache(object):
	"""
	Memcached based ModelCache
	"""
	implements(IModelCache)

	def __init__(self, memcached, model=None):
		self.model = model
		self.memcached = memcached

	def get(self, *args, **kwargs):
		"""Get model object from this cache based on the specified key"""
		key = self._key(*args)
		return self.memcached.get(key).addCallbacks(lambda x: x[0], lambda x: None)

	def add(self, instance):
		"""Add/Replace the model object"""
		args = [getattr(instance, field.name) for field in self.model.pk_fields]
		key = self._key(*args)
		return self.memcached.set(key, instance)

	def remove(self, instance):
		"""Remove model object from this cache"""
		args = [getattr(instance, field.name) for field in self.model.pk_fields]
		key = self._key(*args)
		return self.memcached.delete(key)

	def _key(self, *args):
		return '%s.%s-%s' % (self.model.__module__, self.model.__name__, '-'.join(args))
