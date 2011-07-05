from pn.db.model import Model, Field
from pn.db.cluster import locator

# class User(Model):
# 	table  = 'pnfs_user'
# 	fields = (
# 			Field('username',	  type='string', ispk=True),
# 		)


class Photo(Model):
	table = 'pnfs_photo'
	fields = (
			Field('username', 	  type='string', ispk=True),
			Field('filename', 	  type='string', ispk=True),
			Field('secret', 		  type='string'),
			Field('width', 		  type='int', 	  default=0),
			Field('height', 		  type='int', 	  default=0),
			Field('file_length', type='int', 	  default=0),
			Field('content_type', type='string'),
			Field('sizes', 		  type='int', 	  default=0),
			Field('created_time', type='int', default=0),
			Field('state', 		  type='int', 	  default=0)
		)
	locator = locator
	
	STATE_ACTIVE = 0
	STATE_DISABLED = 1
	
	#VERSIONS = ('square', 'thumb', 'small', 'medium', 'big', 'large')
	#SIZES = (50, 90, 150, 300, 800, 1024)
	
	VERSIONS = ('square', 'thumb', 'small', 'daogou', 'smedium', 'medium', 'big', 'large', 'thumb50', 'thumb100', 'thumb120')
	SIZES = (50, 90, 150, 198, 208, 300, 800, 1024, 50, 100, 120)

	SIZE_MAPPING = {}
	THUMB_FLAGS = {}
	for i in xrange(len(VERSIONS)):
		SIZE_MAPPING[VERSIONS[i]] = SIZES[i]
		THUMB_FLAGS[VERSIONS[i]] = 1 << (i + 1);
	
	def generated(self, size):
		if self.THUMB_FLAGS.has_key(size):
			self.sizes = self.sizes | self.THUMB_FLAGS[size]
	
	def exists(self, size):
		if self.THUMB_FLAGS.has_key(size):
			return self.sizes & self.THUMB_FLAGS[size] > 0
		return False
	
	def keys(self, thumbsOnly=False):
		base = '%s-%s' % (self.username, self.filename)
		val = []
		if not thumbsOnly:
			val.append('%s-%s' % (base, self.secret))
		for k, v in self.THUMB_FLAGS.items():
			if self.sizes & v > 0:
				val.append('%s-%s' % (base, k))
		return val
		
