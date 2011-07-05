#!/usr/bin/python

from distutils.core import setup

__version__ = "0.1.1"

setup(
		name = "PNDFS",
		version	= __version__,
		author = "Zhang Songfu",
		author_email = "songfu.zhang@gmail.com",
		url = "http://blog.painiu.com/",
		description  = "Pndfs Library for Twisted-based Applications",
		platforms = ["Platform Independent"],
		packages=["pn","pn.client","pn.db","pn.core","pn.fs","pn.util","pn.web","pn.web.filter","pn.ws"]
	)