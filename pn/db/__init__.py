class DatabaseError(Exception):
	pass

def init(dbModule):
	mod = __import__(dbModule, {}, {}, [''])
	globals()['DatabaseError'] = getattr(mod, 'DatabaseError')
	
