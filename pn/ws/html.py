from pn.ws import settings
from pn.web import http
from pn.web import responsecode

HTML_TEMPLATE = """
<html>
<head>
<title>%(title)s</title>
<style type="text/css">
body {font-size:12px;}
</style>
</head>
<body>
<div><h1><a href="http://www.365.com/">365.com</a></h1></div>
%(body)s
</body>
</html>
"""

def _url(photo, v):
	if v == 'original':
		v = photo.secret
	#return 'http://%s.%s:%s/%s/%s/%s/' % (settings.inner_host, settings.server_domain, settings.listen_port, photo.username, photo.filename, v)
	return 'http://%s.%s/%s/%s/%s' % (settings.inner_host, settings.server_domain, photo.username, photo.filename, v)


def sizeListPage(photo):
	body = '<ol>%s</ol>' % ''.join(['<li><a href="%s">%s</a></li>' % (_url(photo, v), v) for v in ('square', 'thumb', 'small', 'medium', 'big', 'large', 'original')])
	return HTML_TEMPLATE % {
      'title': '365 Photo Versions',
      'body': body
    } 
	#return http.Response(responsecode.FORBIDDEN)