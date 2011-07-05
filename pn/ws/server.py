"""
User -> Photo -> File
"""
import os
import urlparse
import StringIO

from twisted.python import log
from pn.client import magickd

from pn.web import resource
from pn.web import http
from pn.web import http_headers
from pn.web import responsecode
from pn.web import static
from pn.web import iweb
from pn.web import server

from pn.model import Photo
from pn.ws import html
from pn.ws import settings
from pn.ws import imagewater
from pn.core import stream as stream_mod
from urllib2 import Request, urlopen, URLError, HTTPError

class PhotoResponse(http.Response):
	def __init__(self, photo):
		self.photo = photo
		
		output = html.sizeListPage(self.photo)
		#output = None
		
		super(PhotoResponse, self).__init__(
				responsecode.OK,
				{'content-type': http_headers.MimeType('text', 'html')},
				stream=output)
		
	def __repr__(self):
		return "<%s %s %s>" % (self.__class__.__name__, self.code, str(self.photo))


class StaticFileResource(static.Data):
	addSlash = False
	
	def __init__(self, filename, content_type):
		f = open(filename, 'rb')
		data = f.read()
		f.close()
		static.Data.__init__(self, data, content_type)
	
class IconsRootResource(resource.Resource):
	addSlash = True
	
	def __init__(self, root):
		self.root = root
		
	def locateChild(self, request, segments):
		return IconResource(self.root, segments[0]), segments[1:]
	
	def render(self):
		return http.Response(responsecode.FORBIDDEN)

class Root(resource.Resource):
	"""docstring for Root"""

	addSlash = True

	def __init__(self, mogilefs, magickd, httpclient):
		super(Root, self).__init__()
		self.mogilefs = mogilefs
		self.magickd = magickd
		self.httpclient = httpclient
		
	def locateChild(self, request, segments):
		"""
		Locates a child resource of this resource.
		@param request: the request to process.
		@param segments: a sequence of URL path segments.
		@return: a tuple of C{(child, segments)} containing the child
		of this resource which matches one or more of the given C{segments} in
		sequence, and a list of remaining segments.
		"""
		w = getattr(self, 'child_%s' % (segments[0],), None)
		
		if w:
			r = iweb.IResource(w, None)
			if r:
				return r, segments[1:]
			return w(request), segments[1:]
			
		return UserResource(self, segments[0]), segments[1:]
		
	def render(self, request):
		"""docstring for render"""
		return http.RedirectResponse('http://www.%s/' % settings.server_domain)

class UserResource(resource.Resource):
	"""docstring for UserResource"""

	addSlash = False

	def __init__(self, root, username=None):
		super(UserResource, self).__init__()
		self.root = root
		self.username = username
		#self.username = None

	def locateChild(self, request, segments):
		if segments[0] == '':
			request.prepath.append(segments[0]) 
			return self, server.StopTraversal
		return PhotoResource(self.root, self.username, segments[0]), segments[1:]

	def render(self, request):
		"""docstring for render"""
		location = 'http://%s.%s/' % (self.username, settings.server_domain)
		return http.RedirectResponse(location)
		
		
class BaseResource(resource.LeafResource):
	"""docstring for BaseResource"""
	addSlash = False
	content_type = http_headers.MimeType('image', 'jpeg')
	
	inner_request = False
	outer_request = False
	
	def __init__(self, mogilefs, magickd, httpclient):
		super(BaseResource, self).__init__()
		self.mogilefs = mogilefs
		self.magickd = magickd
		self.httpclient = httpclient
		
	def render(self, request):
		"""docstring for render"""
		if self.checkHost(request):
			return self.doRender(request)
		else:
			return http.Response(responsecode.FORBIDDEN)
		#return self.doRender(request)
		
	def checkHost(self, request):
		headers = request.headers
		host = headers.getHeader("host", None)
		if not host:
			return False
		referer = headers.getHeader("referer", None)
		host = host.split('.')[0]
		if host == settings.inner_host:
			self.inner_request = True
			if not referer:
				return False
			schema, netloc, path, querystring, fragment = urlparse.urlsplit(referer)
			parts = netloc.split('.', 1)
			if len(parts) == 1:
				referer_domain = parts[0]
			else:
				referer_domain = parts[1]
			if referer_domain != settings.server_domain:
				return False
		else:
			self.outer_request = True
			# TODO check blocked referers
		return True
		
	def doRender(self, request):
		raise NotImplementedError, "must be implemented in subclass"
		
	def notFound(self):
		return http.Response(responsecode.NOT_FOUND)
	
	def getPaths(self):
		"""docstring for getPaths"""
		d = self.mogilefs.get_paths(self.mfs_key)
		d.addCallbacks(self.cbGetPaths, self.ebGetPaths)
		return d

	def cbGetPaths(self, paths):
		if paths:
			self.paths = paths
			return self.getFile()
		return self.notFound()

	def ebGetPaths(self, fail):
		log.err(fail)
		return self.notFound()
	
	def makewater(self,url):
		if self.version=='medium':
			filename= os.path.join(settings.resources_directory,'%s-%s-%s.jpg' % (self.username, self.filename, self.version))
			#self.filename_water= os.path.join("/users/zhangsf",'%s-%s-%s-water.jpg' % (self.username, self.filename, self.version))
			req = Request(url)
			f = urlopen(req)
			local_file = open(filename, "w" + "b")
			local_file.write(f.read())
			local_file.close()
			#make water
			#imagewater.watermark(filename,settings.water_img_path,imagewater.POSITION[4],opacity=0.9).save(self.filename_water,quality=95)
			self.waterimage = imagewater.watermark(filename,settings.water_img_path,imagewater.POSITION[4],opacity=0.9)
			os.remove(filename);
			
	def getFile(self):
		if self.paths:
			url = self.paths.pop(0)
			if self.version=='medium':
				self.makewater(url)
				memory_stream = stream_mod.MemoryStream(self.waterimage.tostring('jpeg','RGB'))
				#print type(self.waterimage.tostring())
				#print open(StringIO.StringIO(self.waterimage.tostring('jpeg','RGB')))
				#print open(self.waterimage.tostring('jpeg','RGB'),'r')
				#return self.response(StringIO.StringIO(self.waterimage.tostring('jpeg','RGB')))
				return self.response(memory_stream.read())
			else:
				d = self.httpclient.get(url)	
				d.addCallbacks(self.cbGetFile, self.ebGetFile)
				return d
		else:
			return self.notFound()

	def cbGetFile(self, http_response):
		if http_response.code == responsecode.OK:
			return self.response(http_response.stream)
		elif self.paths:
			return self.getFile()
		return self.notFound()

	def ebGetFile(self, fail):
		log.err(fail)
		if self.paths:
			return self.getFile()
		return self.notFound()

	def response(self, stream):
		headers = {'content-type': self.getContentType()}
		#print headers
		#print stream
		return http.Response(responsecode.OK, headers=headers, stream=stream)
		
	def getContentType(self):
		return self.content_type

class IconResource(BaseResource):
	"""docstring for ClassName"""

	def __init__(self, root, filename):
		super(IconResource, self).__init__(root.mogilefs, root.magickd, root.httpclient)
		self.root = root
		self.filename = filename

	def doRender(self, request):
		"""docstring for render"""
		self.mfs_key = 'icons-%s' % self.filename
		return self.getPaths()

class PhotoResource(resource.Resource):
	"""docstring for PhotoResource"""
	addSlash = True

	def __init__(self, root, username, filename):
		super(PhotoResource, self).__init__()
		self.root = root
		self.username = username
		self.filename = filename

	def locateChild(self, request, segments):
		"""docstring for locateChild"""
		if segments[0] == '':
			request.prepath.append(segments[0])
			return self, server.StopTraversal
		return FileResource(self.root, self.username, self.filename, segments[0]), segments[1:]

	def render(self, request):
		"""docstring for render"""
		def cbLoad(photo):
			if photo is None or photo.state != Photo.STATE_ACTIVE:
				return http.Response(responsecode.NOT_FOUND)
			return PhotoResponse(photo)
		return Photo.load(self.username, self.filename).addCallback(cbLoad)

def parseGeometry(w, h, m, crop=False):
	if m < 0 or (w < m and h < m and not crop):
		return (w, h)
	else:
		tw = th = m
		thumbratio = float(tw) / float(th)
		imgratio = float(w) / float(h)
		
		if crop:
			if thumbratio < imgratio:
				tw = round(th * imgratio)
			else:
				th = round(tw / imgratio)
		else:
			if thumbratio < imgratio:
				th = round(tw / imgratio)
			else:
				tw = round(th * imgratio)
		return (tw, th)
		
def sharpParameters(w, h):
	x = round(w + h / 2)
	if x <= 600:
		return ''
	if x <= 800:
		p = '0x0.4+1.0+0'
	elif x <= 900:
		p = '0x0.6+1.5+0'
	elif x <= 1024:
		p = '0x0.7+1.5+0'
	elif x <= 2048:
		p = '0x0.8+1.5+0'
	else:
		p = '0x0.9+1.5+0'
	return ' -filter Lanczos -unsharp %s' % p
	

class FileResource(BaseResource):
	"""docstring for FileResource"""
	
	exists = False
	fake_thumb = False
	
	def __init__(self, root, username, filename, version):
		super(FileResource, self).__init__(root.mogilefs, root.magickd, root.httpclient)
		self.root		 = root
		self.username	 = username
		self.filename	 = filename
		self.version	 = os.path.splitext(version)[0] # remove extension if it exists
		
		if self.version in Photo.SIZE_MAPPING:
			self.max_size = Photo.SIZE_MAPPING[self.version]
		else:
			self.max_size = 0
		self.load_version = self.version
		
	def _get_photo(self):
		if hasattr(self, '_photo'):
			return self._photo
		return None
		
	def _set_photo(self, p):
		self._photo = p
		if self.version == p.secret:
			self.exists = True
		elif self.max_size and p.width <= self.max_size and p.height <= self.max_size:
			# self.exists = True
			self.fake_thumb = True
		elif p.exists(self.version):
			self.exists = True

	photo = property(_get_photo, _set_photo)

	def doRender(self, request):
		"""docstring for render"""
		# TODO check Host & Referer
		return Photo.load(self.username, self.filename).addCallback(self.onLoad)
		
	def onLoad(self, photo):
		if photo is None or photo.state != Photo.STATE_ACTIVE:
			return self.notFound()
		
		self.photo = photo
		if not self.version in Photo.VERSIONS and self.version != photo.secret:
			return self.notFound()
		
		if not self.exists or self.fake_thumb:
			# if not exists, load original file for generating
			# if the original photo is smaller then the requested one, load original one
			self.load_version = self.photo.secret
		
		self.mfs_key = '%s-%s-%s' % (self.username, self.filename, self.load_version)
		return self.getPaths()
		
	def cbGetPaths(self, paths):
		if paths:
			self.paths = paths
			if self.exists or self.fake_thumb:
				return self.getFile()
			else:
				return self.generateThumb()
				
		return self.notFound()
		
	def ebGetPaths(self, fail):
		log.err(fail)
		if self.load_version == self.photo.secret:
			return self.notFound()
		
		self.load_version = self.photo.secret
		return self.getPaths()
			
	def generateThumb(self):
		p = self.photo
		size = self.max_size
		if self.version == 'square':
			w, h = parseGeometry(p.width, p.height, size, True)
			command = '-resize %sx%s>' % (w, h)
			if w > size or h > size:
				command += ' -gravity center -crop %sx%s+0+0 +repage' % (size, size)
		else:
			w = h = size
			command = '-resize %sx%s>' % (w, h)
			
		if self.version == 'medium':
			command = '%s%s -quality 97' % (command, sharpParameters(p.width, p.height))
		
		def ebConvert(fail):
			#fail.trap(magickd.InvalidImageError)
			log.msg('MagickdError occurred while processing %s-%s-%s, error msg: %s' % (self.username, self.filename, self.photo.secret, fail.getErrorMessage()))
			# magickd can not process the image file
			# return original file.
			self.fake_thumb = True
			self.load_version = self.photo.secret
			return self.getPaths()
		d = self.magickd.convertURL('-strip %s' % command, self.paths)
		d.addCallback(self.saveGenerated)
		d.addErrback(ebConvert)
		return d
		
	def saveGenerated(self, rsp):
		#dest = os.path.join("/users/zhangsf",'%s-%s-%s.jpg' % (self.username, self.filename, self.version))
		#if os.path.isfile(dest) == False :
		#if self.version == 'square':
			#print stream_mod.readStream(rsp.stream,None)
			#imagewater.watermark(rsp.stream,imagewater.MARKIMAGE,imagewater.POSITION[4],opacity=0.9).save("/users/zhangsf/watermarked_medium_lt.jpg",quality=95)
			#dest = os.path.join("/users/zhangsf",'%s-%s-%s.jpg' % (self.username, self.filename, self.version))
			#destfile = os.fdopen(os.open(dest, os.O_WRONLY | os.O_CREAT | os.O_EXCL,0775), 'w', 0)
			#stream_mod.readIntoFile(rsp.stream, destfile)
			#os.system("chown zhangsf %s" % dest)
			
		def cbSave(_):
			self.photo.generated(self.version)
			return self.photo.save().addBoth(cbPersist)
		
		def cbPersist(_):
			self.exists = True
			self.load_version = self.version
			del self.paths
			self.mfs_key = '%s-%s-%s' % (self.username, self.filename, self.load_version)
			return self.getPaths()
			
		d = self.mogilefs.send_file('%s-%s-%s' % (self.username, self.filename, self.version), rsp.stream, clas='thumb')
		d.addCallback(cbSave)
		return d

	def getContentType(self):
		p = self.photo
		if (self.fake_thumb or self.version == p.secret) and p.content_type:
			self.content_type = http_headers.MimeType(*p.content_type.split('/'))
		return self.content_type
	
