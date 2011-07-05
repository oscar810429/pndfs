# Reactor type to use.
# Default is 'select' as it is available on almost every platform.
# For best practice:
#   use 'select' on Win32 system
#   use 'poll' on Unix system
#   use 'epoll' on Linux system
#   use 'kqueue' on FreeBSD/MacOSX system
#
# For more on reactors, see:
# http://twistedmatrix.com/projects/core/documentation/howto/choosing-reactor.html
reactor = 'epoll'

# TCP interface to listening to
listen_interface = '127.0.0.1'
# TCP port to listening to
listen_port = 8080

# Database connection info.
database_module = "MySQLdb"
database_name = 'pnfs_cluster'
database_user = 'root'
database_password = 'zhangsf'
database_host = 'localhost'
database_port = 3306

# MogileFS trackers
mogilefs_trackers = []
mogilefs_domain = 'pic.365.com'
mogilefs_verify_data = False
mogilefs_verify_repcount = False
mogilefs_conn_timeout = 30
mogilefs_maint_time = 300

# Memcached hosts
memcached_servers = []
memcached_conn_timeout = 30
memcached_maint_time = 300

# specified Models should be cached
model_caches = {
	'pn.db.cluster.UserMapping': 3600,
	'pn.model.Photo': 3600

}
