from constants import today
from database import db, metadata # REMEMBER TO IMPLEMENT SERIALIZING METHOD IN DB
##TODO: IMPLEMENT add_manga and add_chapter in db

##TODO: IMPLEMENT INDEXING
class MangaContainer:
	""" Creates a manga with the following parameters:
	title <- str
	artist <- str
	info <- str
	chapters <- {<chapter_number>:{1:page1, 2:page2, 3:page3}}
	type <- str
	genres <- list
	pub_date <- (not sure yet... prolly string: dd/mm/yy)
	date_added <- date, will be defaulted on init
	last_read <- timestamp (e.g. time.time()), will be defaulted to date on init
	"""
	def __init__(self, title, artist, info, chapters, type="Unknown", genres=[], tags=[],
			  pub_date="", date_added=today(), last_read=today()):
		self._title = title
		self._info = info
		self._artist = artist
		self._chapters = chapters
		self._type = type
		self._genres = genres
		self._tags = tags
		self._pub_date = pub_date
		self._date_added = date_added
		self._last_read = last_read
		self._metadata = {}

		self._do_metadata() # make initial metadata
		
		db.MangaDB.add_manga(self._title, self._artist, self._info, self._metadata) # add manga with no chapters into db

		#NOTE: this way we can implement drag & drop, so when zip/cbz/folder of manga
		# is dropped it handles the chapters itself
		self._do_chapters(self._chapters) # handle received chapters and add them to db

	def set_title(self, new_title):
		"Changes manga title"
		pass
	
	def set_genres(self, new_genres):
		"""Changes genres
		Note: think about existing genres and how to deal with them
		"""
		pass

	@property
	def title(self):
		"Returns title in str"
		return self._title

	@property
	def chapter(self, chapter_number):
		"Returns a specific chapter path"
		pass

	@property
	def chapters(self):
		"""Returns a dict with all chapters
		-> chapter_number:path
		"""
		pass

	@property
	def last_read(self):
		"Returns last read timestamp"
		pass

	@property
	def date_added(self):
		"Returns date added str e.g. dd Mmm YYYY"
		d = "{} {} {}".format(self._date_added[0], self._date_added[1], self._date_added[2])
		return d

	def _do_chapters(self, chap_object):
		"""Only meant to be used internally and once, but
		can be used outside too. Just remember, that
		chapters will be overwritten
		"""
		
		#DROPPED
		#def _do_chapter(chapter_number, pages):
		#	"sends metadata to db"
		#	_chap_metadata = [] #meta data for the individual chapter
		#	#OBS: still need to implement indexing
		#	md = {"link":self._index, "chapter":chapter_number,
		#	   "pages":pages, "metadata":self._chap_metadata}

		#	metadata.ChapterDB.add_chapter(md)

		for chap in chap_object:
			for numb, pages in chap:
				raise NotImplementedError("Adding chapters not yet implemented")
				#_do_chapter(numb, pages)

	def _do_metadata(self):
		"will create initial metadata for the manga"

		self._metadata = {"type":self._type, "genres":self._genres, "tags":self._tags,
					"publishing date":self._pub_date,
					"date added":self._date_added, "last read":self._last_read}

class Manga(MangaContainer):
	"""Meant to be used by DB when retriveing manga
	id -> int
	title -> str
	chapters -> {<chapter_number>:{1:page1, 2:page2, 3:page3}}
	metadata -> dict
	"""
	def __init__(self, id, title, artist, info, chapters, metadata):
		self.id = id
		self.title = title
		self.artist = artist
		self.info = info
		self.data = {"id":id, "chapters":chapters}
		self.metadata = metadata


if __name__ == '__main__':
	#unit testing here
	raise RuntimeError("Unit testing still not implemented")
