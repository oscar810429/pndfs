from zope.interface import implements

from twisted.python import log

from pn.db.interfaces import IModelPersister
from pn.db import DatabaseError


class PersistError(Exception):
	"""Persist Error"""
	

class DatabasePersister(object):
	implements(IModelPersister)
	
	_SQL_INSERT = "INSERT INTO %(table)s (%(column)s) VALUES (%(placeholder)s)"
	_SQL_LOAD   = "SELECT %(column)s FROM %(table)s WHERE %(condition)s"
	_SQL_DELETE = "DELETE FROM %(table)s WHERE %(condition)s"
	_SQL_UPDATE = "UPDATE %(table)s SET %(column)s WHERE %(condition)s"
	
	def __init__(self, klass, logsql=True):
		self.model = klass
		self.logsql = logsql
		self._init_sql()
		
	def _init_sql(self):
		self._sql_table = self.model.table
		self._sql_condition = ' AND '.join(["%s = %%s" % field.name for field in self.model.pk_fields])
		self._sql_columns = ', '.join([field.name for field in self.model.fields])
		
		self._sql_insert = self._SQL_INSERT % {
			'column'	 : self._sql_columns,
			'table'		 : self._sql_table,
			'placeholder': ', '.join(['%s' for i in range(len(self.model.fields))])
		}
		self._sql_load = self._SQL_LOAD % {
			'column'   : self._sql_columns,
			'table'	   : self._sql_table,
			'condition': self._sql_condition
		}
		self._sql_update = self._SQL_UPDATE % {
			'column'   : ', '.join(['%s=%%s' % field.name for field in self.model.non_pk_fields]),
			'table'	   : self._sql_table,
			'condition': self._sql_condition
		}
		self._sql_delete = self._SQL_DELETE % {
			'table'	   : self._sql_table,
			'condition': self._sql_condition
		}
		
	def _doWrite(self, action, *args, **kwargs):
		dbargs = [getattr(args[0], field.name) for field in self.model.pk_fields]
		d = self.model.locator.getWritable(*dbargs, **kwargs)
		d.addCallback(self._gotDatabase, action, *args, **kwargs)
		return d
	
	def _doRead(self, action, *args, **kwargs):
		d = self.model.locator.getReadable(*args, **kwargs)
		d.addCallback(self._gotDatabase, action, *args, **kwargs)
		return d
		
	def _gotDatabase(self, db, action, *args, **kwargs):
		if db is None:
			raise PersistError, "Can not locate correct database"
		return db.runInteraction(action, *args, **kwargs)
		
	def _insert(self, instance):
		def doInsert(trans, instance):
			value = [getattr(instance, field.name, field.default) for field in self.model.fields]
			if self.logsql:
				log.msg('Exec SQL: %s with %s' % (self._sql_insert, value))
			trans.execute(self._sql_insert, value)
			setattr(instance, '__model_persisted', True)
			
		return self._doWrite(doInsert, instance)
		
	def _update(self, instance):
		def doUpdate(trans, instance):
			value = [getattr(instance, field.name, field.default) for field in self.model.non_pk_fields] + \
					[getattr(instance, field.name, field.default) for field in self.model.pk_fields]
			if self.logsql:
				log.msg('Exec SQL: %s with %s' % (self._sql_update, value))
			trans.execute(self._sql_update, value)
		
		return self._doWrite(doUpdate, instance)
	
	def save(self, instance):
		if hasattr(instance, '__model_persisted'):
			return self._update(instance)
		
		def ebInsert(fail, instance):
			if fail.check(DatabaseError):
				# try update
				return self._update(instance)
			fail.raiseException()
			
		return self._insert(instance).addErrback(ebInsert, instance)
		
	def load(self, *args, **kwargs):
		def doLoad(trans, *args, **kwargs):
			if len(args) != len(self.model.pk_fields):
				raise RuntimeError, 'arguments not match primary key of <Model of %s>' % self.model.__name__
			if self.logsql:
				log.msg('Exec SQL: %s with %s' % (self._sql_load, args))
			trans.execute(self._sql_load, args)
			result = trans.fetchone()
			if result:
				instance = self.model(*result)
				setattr(instance, '__model_persisted', True)
				return instance
			else:
				return None
		
		return self._doRead(doLoad, *args, **kwargs)
		
	def loadAll(self):
		def doLoadAll(trans):
			sql = "SELECT %s FROM %s" % (self._sql_columns, self._sql_table)
			if self.logsql:
				log.msg('Exec SQL: %s' % sql)
			trans.execute(sql)
			rows = trans.fetchall()
			result = []
			for row in rows:
				instance = self.model(*row)
				setattr(instance, '__model_persisted', True)
				result.append(instance)
			return result
			
		return self._doRead(doLoadAll)
		
	def delete(self, instance):
		def doDelete(trans, instance):
			value = [getattr(instance, field.name, field.default) for field in self.model.pk_fields]
			if self.logsql:
				log.msg('Exec SQL: %s with %s' % (self._sql_delete, value))
			trans.execute(self._sql_delete, value)
		
		return self._doWrite(doDelete, instance)