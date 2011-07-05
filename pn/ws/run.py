# Ensure the user is running the version of python we require.
import sys, os

from twisted.application import app
from twisted.python import log
from twisted.python.runtime import platformType, shortPythonVersion

from pn import version
from pn.ws import settings

if platformType == "win32":
	from twisted.scripts._twistw import ServerOptions as _ServerOptions, \
		WindowsApplicationRunner as _SomeApplicationRunner
else:
	from twisted.scripts._twistd_unix import ServerOptions as _ServerOptions, \
		UnixApplicationRunner as _SomeApplicationRunner

from pn.run import *

def createApplication(config):
	from twisted.application import internet, service
	from pn.client.mogilefs import MogileFSClient
	from pn.client.magickd import MagickdClient
	from pn.client.http import HTTPClient
	from pn.web import server as webserver
	from pn.web import channel
	from pn.ws import server
	
	initDatabase(settings)
	initCluster(settings)
	initCaches(settings)
	
	# init mogilefs client
	mogilefs = MogileFSClient(settings.mogilefs_domain, settings.mogilefs_trackers,
						verify_data=settings.mogilefs_verify_data,
						verify_repcount=settings.mogilefs_verify_repcount,
						connTimeout=settings.mogilefs_conn_timeout,
						maintTime=settings.mogilefs_maint_time,
						cache=settings.memcached)
	
	httpclient = HTTPClient()
	
	magickd = MagickdClient(settings.magickd_servers,
						connTimeout=settings.magickd_conn_timeout,
						maintTime=settings.magickd_maint_time,
						magickd_uri=settings.magickd_uri,
						httpclient=httpclient)
	
	# create application
	root = server.Root(mogilefs, magickd, httpclient)
	root.putChild('icons', server.IconsRootResource(root))
	root.putChild('favicon.ico', server.StaticFileResource(settings.favicon_path, 'image/x-icon'))
	# from pn.web import static
	#root = static.File('/home/zhangsf')
	site = webserver.Site(root)
	factory = channel.HTTPFactory(site)
	
	application = service.Application("pnws")  # create the Application
	pnwsService = internet.TCPServer(settings.listen_port, factory,
								interface=settings.listen_interface) # create the service
	# add the service to the application
	pnwsService.setServiceParent(application)
	return application


def initialLog():
	from twisted.internet import reactor
	log.msg("PNWS %s (%s %s) starting up" % (version,
											   sys.executable,
											   shortPythonVersion()))
	log.msg('reactor class: %s' % reactor.__class__)

app.initialLog = initialLog

class ApplicationRunner(_SomeApplicationRunner):
	def createOrGetApplication(self):
		return createApplication(self.config)	


class ServerOptions(_ServerOptions):
	optParameters = [
					['config', 'c', '/etc/pnfs/pnws.conf', "Configuration file (default: /etc/pnfs/pnws.conf)"],
					['interface', None, None, "TCP interface to listening to"],
					['port', None, None, "TCP port to listening to"],
					['prefix', None, 'pnws', "use the given prefix when syslogging"],
					['pidfile', '', 'pnws.pid', "Name of the pidfile"]
					]
	zsh_altArgDescr = {"prefix": "Use the given prefix when syslogging (default: pnws)",
					   "pidfile": "Name of the pidfile (default: pnws.pid)", }
	
	def opt_version(self):
		"""Print version information and exit.
		"""
		print 'PNDFS (the pnws daemon) %s' % version
		print 'Copyright (c) 2009-2010 365.com.'
		sys.exit()



def runApp(config):
	loadConfigurations(config, settings)
	
	if not sys.modules.has_key('twisted.internet.reactor'):
		from twisted.application.reactors import installReactor
		installReactor(settings.reactor)
	ApplicationRunner(config).run()

def run():
	app.run(runApp, ServerOptions)
	
__all__ = ['run', 'runApp']
