from zope.interface import Interface

class IDatabaseLocator(Interface):
	"""Object used to find the correct database to persist the model object"""
	
	def getDatabase(self, *args, **kwargs):
		"""Locate a database based on arguments passed in"""
		
	def getWritable(self, *args, **kwargs):
		"""Locate a writable database based on arguments passed in"""
		
	def getReadable(self, *args, **kwargs):
		"""Locate a readable database based on arguments passed in"""

class IModelPersister(Interface):
	"""Object used to take care of model persistence"""
	
	def save(self, instance):
		"""Insert/Update instance to database"""
	
	def load(self, *args, **kwargs):
		"""Load one row from database"""
		
	def delete(self, instance):
		"""Delete the instance row from database"""
		
class IModelCache(Interface):
	"""Object used to cache models in memoery"""
	
	def get(self, *args, **kwargs):
		"""Get model object from this cache based on the specified key
		
		@type key: C{str}
		"""
		
	def add(self, instance):
		"""Add/Replace the model object"""
		
	def remove(self, instance):
		"""Remove model object from this cache"""
		
class IModelManager(Interface):
	"""Object used to take care of model object persitence and cache"""
	
	def save(self, instance):
		"""Insert/Update the model instance"""
		
	def load(self, *args, **kwargs):
		"""Load a single row from cache or database"""
		
	def loadAll(self):
		"""Load all instances of the model"""
		
	def delete(self, intance):
		"""Delete the model instance from cache and database"""
