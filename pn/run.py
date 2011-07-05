# Ensure the user is running the version of python we require.
import sys, os

if not hasattr(sys, "version_info") or sys.version_info < (2, 3):
	raise RuntimeError("PNFS requires Python 2.5 or later.")

# Ensure twisted is installed
try:
	from twisted.application import app
except ImportError:
	raise ImportError("you need Twisted installed "
					  "(http://twistedmatrix.com/)")

from twisted.python import log


def initDatabase(settings):
	"""Init database module"""
	from pn.db import init
	try:
		init(settings.database_module)
	except:
		abort()

def initCluster(settings):
	"""Init database cluster"""
	from twisted.enterprise import adbapi
	from pn.db.cluster import SimpleDatabaseLocator, initCluster, setupLocator
	from pn import model
	
	ringPool = adbapi.ConnectionPool(
				settings.database_module,
				host=settings.database_host,
				port=settings.database_port,
				db=settings.database_name,
				user=settings.database_user,
				passwd=settings.database_password)
	
	ringLocator = SimpleDatabaseLocator(ringPool)
	
	initCluster(ringLocator)
	setupLocator((model,))

def initCaches(settings):
	"""Init memcached client"""
	from pn.client.memcached import MemcachedClient
	from pn.db.model import Model, MemcachedModelCache
	
	memcached = MemcachedClient(hosts=settings.memcached_servers,
						connTimeout=settings.memcached_conn_timeout,
						maintTime=settings.memcached_maint_time)
	
	setattr(settings, 'memcached', memcached)
	
	if not isinstance(settings.model_caches, dict):
		abort("model_cache should be a dict.", "Configuration error")
	
	for name, value in settings.model_caches.items():
		try:
			value = int(value)
		except:
			abort(prefix='Configuration error')
		
		pkg, klass = name.rsplit('.', 1)
		
		try:
			mod = getattr(__import__(pkg, {}, {}, ['']), klass)
		except:
			abort(prefix='Configuration error')
			
		if isinstance(mod, type) and issubclass(mod, Model):
			setattr(mod, 'cache', MemcachedModelCache(memcached, mod))
			setattr(mod, 'cacheExpire', value)
		else:
			abort("keys of model_caches should be a subclass of pn.db.model.Model.", "Configuration error")

def abort(err=None, prefix=None):
	if err is None:
		err = sys.exc_info()[1]
	if isinstance(err, str):
		msg = err
	else:
		msg = err[0]
	if prefix is not None:
		msg = '%s: %s' % (prefix, msg)
		
	log.msg(msg)
	sys.exit('\n' + msg + '\n')
	
def loadConfigurations(config, settings):
	from pn.util import config as cfg
	filename = config['config']
	log.msg("Loading configuration from %s..." % filename)

	d = { '__file__': os.path.abspath(filename) }

	try:
		cfg.load(filename, d, d)
	except:
		abort()
		
	settings.__dict__.update(d)
	d = settings.__dict__
	
	if config['interface'] is not None:
		d['listen_interface'] = config['interface']
	if config['port'] is not None:
		try:
			d['listen_port'] = int(config['port'])
		except ValueError:
			abort("port must be an integer")
