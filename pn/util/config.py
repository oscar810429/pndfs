
import os, sys

def load(filename, g, l):
	if not os.path.exists(filename):
		raise RuntimeError, "Configuration file %s is not exists" % filename
	if not os.path.isfile(filename):
		raise RuntimeError, "Configuration file %s is not a file" % filename
	
	try:
		fileObj = open(filename, 'r')
	except:
		raise RuntimeError, "Error reading configuration file %s" % filename
	
	def include(filepath):
		if not os.path.isabs(filepath):
			filepath = os.path.join(os.path.dirname(filename), filepath)
		execfile(filepath, g, l)
	
	g = { 'include': include }
	
	try:
		exec fileObj in g, l
	except:
		print sys.exc_info()[1]
		raise RuntimeError("Error parsing configuration file %s, "
					"make sure the syntex is right.(it should be a valid" 
					"python source file)." % filename)
	
	
