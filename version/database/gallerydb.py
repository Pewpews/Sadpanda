﻿"""
This file is part of Happypanda.
Happypanda is free software: you can redistribute it and/or modify
it under the terms of the GNU General Public License as published by
the Free Software Foundation, either version 2 of the License, or
any later version.
Happypanda is distributed in the hope that it will be useful,
but WITHOUT ANY WARRANTY; without even the implied warranty of
MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE.  See the
GNU General Public License for more details.
You should have received a copy of the GNU General Public License
along with Happypanda.  If not, see <http://www.gnu.org/licenses/>.
"""

import datetime, os, threading, logging, queue, uuid # for unique filename
from PyQt5.QtCore import Qt, QObject, pyqtSignal
from PyQt5.QtGui import QImage

from ..utils import (today, ArchiveFile, generate_img_hash, delete_path,
					 ARCHIVE_FILES, get_gallery_img)
from .db import CommandQueue, ResultQueue
from ..gui import gui_constants
from .db_constants import THUMBNAIL_PATH, IMG_FILES, CURRENT_DB_VERSION

PROFILE_TO_MODEL = queue.Queue()
TestQueue = queue.Queue()

log = logging.getLogger(__name__)
log_i = log.info
log_d = log.debug
log_w = log.warning
log_e = log.error
log_c = log.critical


def gen_thumbnail(chapter_path, width=gui_constants.THUMB_W_SIZE,
				height=gui_constants.THUMB_H_SIZE): # 2 to align it properly.. need to redo this
	"""Generates a thumbnail with unique filename in the cache dir.
	Returns absolute path to the created thumbnail
	"""
	assert isinstance(chapter_path, str), "Path to chapter should be a string"

	img_path_queue = queue.Queue()
	# generate a cache dir if required
	if not os.path.isdir(THUMBNAIL_PATH):
		os.mkdir(THUMBNAIL_PATH)

	def generate(cache, chap_path, w, h, img_queue):
		try:
			if chap_path[-4:] in ARCHIVE_FILES:
				log_d('Generating Thumb from {}'.format(chap_path[-3:]))
				img_path = get_gallery_img(chap_path)
			else:
				log_d('Generating Thumb from folder')
				img_path = os.path.join(chap_path, [x for x in sorted(os.listdir(chap_path)) if x[-3:] in IMG_FILES][0]) #first image in chapter
			suff = img_path[-4:] # the image ext with dot
		
			# generate unique file name
			file_name = str(uuid.uuid4()) + suff
			new_img_path = os.path.join(cache, (file_name))
			if not os.path.isfile(img_path):
				raise IndexError
			# Do the scaling
			image = QImage()
			image.load(img_path)
			if image.isNull():
				raise IndexError
			image = image.scaled(w, h, Qt.KeepAspectRatio, Qt.SmoothTransformation)
			image.save(new_img_path, quality=100)
		except IndexError:
			new_img_path = gui_constants.NO_IMAGE_PATH

		abs_path = os.path.abspath(new_img_path)
		img_queue.put(abs_path)
		return True

	thread = threading.Thread(target=generate, args=(THUMBNAIL_PATH,
												  chapter_path, width, height,
												  img_path_queue,))
	thread.start()
	thread.join()
	return img_path_queue.get()

def gallery_map(row, gallery):
	gallery.title = row['title']
	gallery.artist = row['artist']
	gallery.profile = bytes.decode(row['profile'])
	gallery.path = bytes.decode(row['series_path'])
	gallery.info = row['info']
	gallery.language = row['language']
	gallery.status = row['status']
	gallery.type = row['type']
	gallery.fav = row['fav']
	gallery.pub_date = row['pub_date']
	gallery.last_update = row['last_update']
	gallery.last_read = row['last_read']
	gallery.date_added = row['date_added']
	gallery.times_read = row['times_read']
	gallery._db_v = row['db_v']
	gallery.exed = row['exed']
	try:
		gallery.link = bytes.decode(row['link'])
	except TypeError:
		gallery.link = row['link']

	gallery.chapters = ChapterDB.get_chapters_for_gallery(gallery.id)

	gallery.tags = TagDB.get_gallery_tags(gallery.id)

	gallery.hashes = HashDB.get_gallery_hashes(gallery.id)

	return gallery

def default_exec(object):
	def check(obj):
		if obj == None:
			return "None"
		else:
			return obj
	executing = [["""INSERT INTO series(title, artist, profile, series_path, 
					info, type, fav, status, pub_date, date_added, last_read, link, last_update,
					times_read, exed)
				VALUES(:title, :artist, :profile, :series_path, :info, :type, :fav,
					:status, :pub_date, :date_added, :last_read, :link, :last_update,
					:times_read, :exed)""",
				{
				'title':check(object.title),
				'artist':check(object.artist),
				'profile':str.encode(object.profile),
				'series_path':str.encode(object.path),
				'info':check(object.info),
				'fav':check(object.fav),
				'type':check(object.type),
				'language':check(object.language),
				'status':check(object.status),
				'pub_date':check(object.pub_date),
				'date_added':check(object.date_added),
				'last_read':check(object.last_read),
				'last_update':check(object.last_update),
				'link':str.encode(object.link),
				'times_read':check(object.times_read),
				'db_v':check(CURRENT_DB_VERSION),
				'exed':check(object.exed)
				}
				]]
	return executing

class GalleryDB:
	"""
	Provides the following s methods:
		rebuild_galleries -> Rebuilds the galleries in DB
		modify_gallery -> Modifies gallery with given gallery id
		fav_gallery_set -> Set fav on gallery with given gallery id, and returns the gallery
		get_all_gallery -> returns a list of all gallery (<Gallery> class) currently in DB
		get_gallery_by_id -> Returns gallery with given id
		get_gallery_by_artist -> Returns gallery with given artist
		get_gallery_by_title -> Returns gallery with given title
		get_gallery_by_tags -> Returns gallery with given list of tags
		get_gallery_by_path -> Returns gallery with given path
		add_gallery -> adds gallery into db
		add_gallery_return -> adds gallery into db AND returns the added gallery
		set_gallery_title -> changes gallery title
		gallery_count -> returns amount of gallery (can be used for indexing)
		del_gallery -> deletes the gallery with the given id recursively
		check_exists -> Checks if provided string exists
	"""
	def __init__(self):
		raise Exception("GalleryDB should not be instantiated")

	@staticmethod
	def rebuild_galleries():
		"Rebuilds the galleries in DB"
		galleries = GalleryDB.get_all_gallery()
		try:
			log_i('Rebuilding galleries')
			for gallery in galleries:
				if gallery.validate():
					log_i("Rebuilding gallery {}".format(gallery.id))
					GalleryDB.modify_gallery(
						gallery.id,
						title=gallery.title,
						artist=gallery.artist,
						info=gallery.info,
						type=gallery.type,
						fav=gallery.fav,
						tags=gallery.tags,
						language=gallery.language,
						status=gallery.status,
						pub_date=gallery.pub_date,
						link=gallery.link,
						times_read=gallery.times_read,
						_db_v=CURRENT_DB_VERSION,
						exed=gallery.exed)
		except:
			log.exception('Failed rebuilding galleries')
			return False
		log_i('Finished rebuilding galleries')
		return True

	@staticmethod
	def modify_gallery(series_id, title=None, artist=None, info=None, type=None, fav=None,
				   tags=None, language=None, status=None, pub_date=None, link=None,
				   times_read=None, series_path=None, chapters=None, _db_v=None,
				   hashes=None, exed=None):
		"Modifies gallery with given gallery id"
		executing = []
		assert isinstance(series_id, int)
		executing = []
		if title:
			assert isinstance(title, str)
			executing.append(["UPDATE series SET title=? WHERE series_id=?", (title, series_id)])
		if artist:
			assert isinstance(artist, str)
			executing.append(["UPDATE series SET artist=? WHERE series_id=?", (artist, series_id)])
		if info:
			assert isinstance(info, str)
			executing.append(["UPDATE series SET info=? WHERE series_id=?", (info, series_id)])
		if type:
			assert isinstance(type, str)
			executing.append(["UPDATE series SET type=? WHERE series_id=?", (type, series_id)])
		if fav:
			assert isinstance(fav, int)
			executing.append(["UPDATE series SET fav=? WHERE series_id=?", (fav, series_id)])
		if language:
			assert isinstance(language, str)
			executing.append(["UPDATE series SET language=? WHERE series_id=?", (language, series_id)])
		if status:
			assert isinstance(status, str)
			executing.append(["UPDATE series SET status=? WHERE series_id=?", (status, series_id)])
		if pub_date:
			executing.append(["UPDATE series SET pub_date=? WHERE series_id=?", (pub_date, series_id)])
		if link:
			executing.append(["UPDATE series SET link=? WHERE series_id=?", (link, series_id)])
		if times_read:
			executing.append(["UPDATE series SET times_read=? WHERE series_id=?", (times_read, series_id)])
		if series_path:
			executing.append(["UPDATE series SET series_path=? WHERE series_id=?", (str.encode(series_path), series_id)])
		if _db_v:
			executing.append(["UPDATE series SET db_v=? WHERE series_id=?", (_db_v, series_id)])
		if exed:
			executing.append(["UPDATE series SET exed=? WHERE series_id=?", (exed, series_id)])
		if tags:
			assert isinstance(tags, dict)
			TagDB.modify_tags(series_id, tags)
		if chapters:
			assert isinstance(chapters, Gallery)
			ChapterDB.update_chapter(chapters)

		if hashes:
			assert isinstance(hashes, Gallery)
			HashDB.rebuild_gallery_hashes(hashes)

		CommandQueue.put(executing)
		c = ResultQueue.get()
		del c


	@staticmethod
	def fav_gallery_set(series_id, fav):
		"Set fav on gallery with given gallery id, and returns the gallery"
		# NOTE: USELESS BECAUSE OF THE METHOD ABOVE; CONSIDER REVISING & DELETING
		executing = [["UPDATE series SET fav=? WHERE series_id=?", (fav, series_id)]]
		GalleryDB.modify_gallery(series_id, fav=fav)		

	@staticmethod
	def get_all_gallery():
		"""Careful, might crash with very large libraries i think...
		Returns a list of all galleries (<Gallery> class) currently in DB"""
		executing = [["SELECT * FROM series"]]
		CommandQueue.put(executing)
		cursor = ResultQueue.get()
		all_gallery = cursor.fetchall()
		gallery_list = []
		for gallery_row in all_gallery:
			gallery = Gallery()
			gallery.id = gallery_row['series_id']
			gallery = gallery_map(gallery_row, gallery)
			gallery.validate()
			gallery_list.append(gallery)

		return gallery_list

	@staticmethod
	def get_gallery_by_id(id):
		"Returns gallery with given id"
		assert isinstance(id, int), "Provided ID is invalid"
		executing = [["SELECT * FROM series WHERE series_id=?", (id,)]]
		CommandQueue.put(executing)
		cursor = ResultQueue.get()
		row = cursor.fetchone()
		gallery = Gallery()
		try:
			gallery.id = row['series_id']
			gallery = gallery_map(row, gallery)
			return gallery
		except TypeError:
			return None


	@staticmethod
	def get_gallery_by_artist(artist):
		"Returns gallery with given artist"
		assert isinstance(artist, str), "Provided artist is invalid"
		executing = [["SELECT * FROM series WHERE artist=?", (artist,)]]
		CommandQueue.put(executing)
		cursor = ResultQueue.get()
		row = cursor.fetchone() # TODO: an artist can have multiple galleries :^)
		gallery = Gallery()
		gallery.id = row['series_id']
		gallery = gallery_map(row, gallery)
		return gallery

	@staticmethod
	def get_gallery_by_title(title):
		"Returns gallery with given title"
		assert isinstance(id, int), "Provided title is invalid"
		executing = [["SELECT * FROM series WHERE title=?", (title,)]]
		CommandQueue.put(executing)
		cursor = ResultQueue.get()
		row = cursor.fetchone()
		gallery = Gallery()
		gallery.id = row['series_id']
		gallery = gallery_map(row, gallery)
		return gallery

	@staticmethod
	def get_gallery_by_tags(list_of_tags):
		"Returns gallery with given list of tags"
		assert isinstance(list_of_tags, list), "Provided tag(s) is/are invalid"
		pass

	@staticmethod
	def get_gallery_by_path(path):
		"Returns gallery with given path"
		assert isinstance(path, str), "Provided path should be a str"
		executing = [["SELECT * FROM series where series_path=?", (str.encode(path),)]]
		CommandQueue.put(executing)
		cursor = ResultQueue.get()
		row = cursor.fetchone()
		if row:
			gallery = Gallery()
			gallery.id = row['series_id']
			gallery = gallery_map(row, gallery)
			return gallery

	@staticmethod
	def get_gallery_by_fav():
		"Returns a list of all gallery with fav set to true (1)"
		x = 1
		executing = [["SELECT * FROM series WHERE fav=?", (x,)]]
		CommandQueue.put(executing)
		cursor = ResultQueue.get()
		
		gallery_list = []
		for row in cursor.fetchall():
			gallery = Gallery()
			gallery.id = row["series_id"]
			gallery = gallery_map(row, gallery)
			gallery_list.append(gallery)
		return gallery_list

	@staticmethod
	def add_gallery(object, test_mode=False):
		"Receives an object of class gallery, and appends it to DB"
		"Adds gallery of <Gallery> class into database"
		assert isinstance(object, Gallery), "add_gallery method only accepts gallery items"

		object.profile = gen_thumbnail(object.chapters[0])

		executing = default_exec(object)
		CommandQueue.put(executing)
		cursor = ResultQueue.get()
		series_id = cursor.lastrowid
		object.id = series_id
		if object.tags:
			TagDB.add_tags(object)
		ChapterDB.add_chapters(object)

	@staticmethod
	def add_gallery_return(object):
		"""Adds gallery of <Gallery> class into database AND returns the profile generated"""
		assert isinstance(object, Gallery), "[add_gallery_return] method only accept gallery items"

		object.profile = gen_thumbnail(object.chapters[0])
		PROFILE_TO_MODEL.put(object.profile)

		executing = default_exec(object)
		CommandQueue.put(executing)
		cursor = ResultQueue.get()
		series_id = cursor.lastrowid
		object.id = series_id
		if object.tags:
			TagDB.add_tags(object)
		ChapterDB.add_chapters(object)
		return GalleryDB.get_gallery_by_id(object.id)

	@staticmethod
	def gallery_count():
		"""Returns the amount of galleries in db.
		"""
		pass

	@staticmethod
	def del_gallery(list_of_gallery, local=False):
		"Deletes all galleries in the list recursively."
		assert isinstance(list_of_gallery, list), "Please provide a valid list of galleries to delete"
		for gallery in list_of_gallery:
			if not gallery.validate():
				log_d('Invalid gallery not removable')
				continue
			if local:
				for chap in gallery.chapters:
					path = gallery.chapters[chap]
					s = delete_path(path)
					if not s:
						log_e('Failed to delete chapter {}:{}, {}'.format(chap,
														gallery.id, gallery.title.encode('utf-8', 'ignore')))
						continue

				s = delete_path(gallery.path)
				if not s:
					log_e('Failed to delete gallery:{}, {}'.format(gallery.id,
													  gallery.title.encode('utf-8', 'ignore')))
					continue

			if gallery.profile != os.path.abspath(gui_constants.NO_IMAGE_PATH):
				try:
					os.remove(gallery.profile)
				except FileNotFoundError:
					pass
			executing = [["DELETE FROM series WHERE series_id=?", (gallery.id,)]]
			CommandQueue.put(executing)
			c = ResultQueue.get()
			del c
			ChapterDB.del_all_chapters(gallery.id)
			TagDB.del_gallery_mapping(gallery.id)
			HashDB.del_gallery_hashes(gallery.id)
			log_i('Successfully deleted: {}'.format(gallery.title.encode('utf-8', 'ignore')))

	@staticmethod
	def check_exists(name, data=None):
		"""
		Checks if provided string exists in provided sorted
		list based on path name
		"""
		if not data:
			db_data = GalleryDB.get_all_gallery()
			filter_list = []
			for gallery in db_data:
				p = os.path.split(gallery.path)
				filter_list.append(p[1])
			filter_list = sorted(filter_list)

		def binary_search(key):
			low = 0
			high = len(filter_list) - 1
			while high >= low:
				mid = low + (high - low) // 2
				if filter_list[mid] < key:
					low = mid + 1
				elif filter_list[mid] > key:
					high = mid - 1
				else:
					return mid
			return None

		if binary_search(name):
			return True
		else: return False


class ChapterDB:
	"""
	Provides the following database methods:
		update_chapter -> Updates an existing chapter in DB
		add_chapter -> adds chapter into db
		add_chapter_raw -> links chapter to the given seires id, and adds into db
		get_chapters_for_gallery -> returns a dict with chapters linked to the given series_id
		get_chapter-> returns a dict with chapter matching the given chapter_number
		get_chapter_id -> returns id of the chapter number
		chapter_size -> returns amount of manga (can be used for indexing)
		del_all_chapters <- Deletes all chapters with the given series_id
		del_chapter <- Deletes chapter with the given number from gallery
	"""

	def __init__(self):
		raise Exception("ChapterDB should not be instantiated")

	@staticmethod
	def update_chapter(gallery, chapters=[]):
		"""
		Updates an existing chapter in DB.
		Pass a gallery. Specify which chapters to update with list of ints,
		leave empty to update all chapters.
		"""
		assert isinstance(gallery, Gallery) and isinstance(chapters, (list, tuple))
		if not chapters:
			chapters = [x for x in range(len(gallery.chapters))]
		executing = []
	
		for numb in chapters:
			new_path = gallery.chapters[numb]
			executing.append(
			["UPDATE chapters SET chapter_path=? WHERE series_id=? AND chapter_number=?", (
				str.encode(new_path), gallery.id, numb)])
		CommandQueue.put(executing)
		c = ResultQueue.get()
		del c

	@staticmethod
	def add_chapters(gallery_object):
		"Adds chapters linked to gallery into database"
		assert isinstance(gallery_object, Gallery), "Parent gallery need to be of class gallery"
		series_id = gallery_object.id
		for chap_number in gallery_object.chapters:
			chap_path = str.encode(gallery_object.chapters[chap_number])
			executing = [["""
			INSERT INTO chapters(series_id, chapter_number, chapter_path)
			VALUES(:series_id, :chapter_number, :chapter_path)""",
			{'series_id':series_id,
			'chapter_number':chap_number,
			'chapter_path':chap_path}
			]]
			CommandQueue.put(executing)
			# neccessary to keep order... feels awkward, will prolly redo this.
			d = ResultQueue.get()
			del d

	def add_chapters_raw(series_id, chapters_dict):
		"Adds chapter(s) to a gallery with the received series_id"
		assert isinstance(chapters_dict, dict), "chapters_dict must be a dictionary: {numb:path}"
		for chap_number in chapters_dict:
			chap_path = str.encode(chapters_dict[chap_number])
			if not ChapterDB.get_chapter(series_id, chap_number):
				executing = [["""
				INSERT INTO chapters(series_id, chapter_number, chapter_path)
				VALUES(:series_id, :chapter_number, :chapter_path)""",
				{'series_id':series_id,
				'chapter_number':chap_number,
				'chapter_path':chap_path}
				]]
			else:
				executing = [["""
				UPDATE chapters SET chapter_path=?
				WHERE series_id=? AND chapter_number=?""",
				(series_id, chap_number,)]]
			CommandQueue.put(executing)
			d = ResultQueue.get()
			del d
				

	@staticmethod
	def get_chapters_for_gallery(series_id):
		"""Returns a dict of chapters matching the received series_id
		{<chap_number>:<chap_path>}
		"""
		assert isinstance(series_id, int), "Please provide a valid gallery ID"
		executing = [["""SELECT chapter_number, chapter_path
							FROM chapters WHERE series_id=?""",
							(series_id,)]]
		CommandQueue.put(executing)
		cursor = ResultQueue.get()
		rows = cursor.fetchall()
		chapters = {}
		for row in rows:
			chapters[row['chapter_number']] = bytes.decode(row['chapter_path'])

		return chapters


	@staticmethod
	def get_chapter(series_id, chap_numb):
		"""Returns a dict of chapter matching the recieved chapter_number
		{<chap_number>:<chap_path>}
		return None for no match
		"""
		assert isinstance(chap_numb, int), "Please provide a valid chapter number"
		executing = [["""SELECT chapter_number, chapter_path
							FROM chapters WHERE series_id=? AND chapter_number=?""",
							(series_id, chap_numb,)]]
		CommandQueue.put(executing)
		cursor = ResultQueue.get()
		try:
			rows = cursor.fetchall()
			chapters = {}
			for row in rows:
				chapters[row['chapter_number']] = bytes.decode(row['chapter_path'])
		except TypeError:
			return None
		return chapters

	@staticmethod
	def get_chapter_id(series_id, chapter_number):
		"Returns id of the chapter number"
		assert isinstance(series_id, int) and isinstance(chapter_number, int),\
			"Passed args must be of int not {} and {}".format(type(series_id), type(chapter_number))
		executing = [["SELECT chapter_id FROM chapters WHERE series_id=? AND chapter_number=?",
						(series_id, chapter_number,)]]
		CommandQueue.put(executing)
		cursor = ResultQueue.get()
		try:
			row = cursor.fetchone()
			chp_id = row['chapter_id']
			return chp_id
		except KeyError:
			return None

	@staticmethod
	def chapter_size(series_id):
		"""Returns the amount of chapters for the given
		manga id
		"""
		pass

	@staticmethod
	def del_all_chapters(series_id):
		"Deletes all chapters with the given series_id"
		assert isinstance(series_id, int), "Please provide a valid gallery ID"
		executing = [["DELETE FROM chapters WHERE series_id=?", (series_id,)]]
		CommandQueue.put(executing)
		c = ResultQueue.get()
		del c

	@staticmethod
	def del_chapter(series_id, chap_number):
		"Deletes chapter with the given number from gallery"
		assert isinstance(series_id, int), "Please provide a valid gallery ID"
		assert isinstance(chap_number, int), "Please provide a valid chapter number"
		executing = [["DELETE FROM chapters WHERE series_id=? AND chapter_number=?",
				(series_id, chap_number,)]]
		CommandQueue.put(executing)
		c = ResultQueue.get()
		del c



class TagDB:
	"""
	Tags are returned in a dict where {"namespace":["tag1","tag2"]}
	The namespace "default" will be used for tags without namespaces.

	Provides the following methods:
	del_tags <- Deletes the tags with corresponding tag_ids from DB
	del_gallery_tags_mapping <- Deletes the tags and gallery mappings with corresponding series_ids from DB
	get_gallery_tags -> Returns all tags and namespaces found for the given series_id;
	get_tag_gallery -> Returns all galleries with the given tag
	get_ns_tags -> Returns all tags linked to the given namespace
	get_ns_tags_gallery -> Returns all galleries linked to the namespace tags
	add_tags <- Adds the given dict_of_tags to the given series_id
	modify_tags <- Modifies the given tags
	get_all_tags -> Returns all tags in database
	get_all_ns -> Returns all namespaces in database
	"""

	def __init__(self):
		raise Exception("TagsDB should not be instantiated")

	@staticmethod
	def del_tags(list_of_tags_id):
		"Deletes the tags with corresponding tag_ids from DB"
		pass

	@staticmethod
	def del_gallery_mapping(series_id):
		"Deletes the tags and gallery mappings with corresponding series_ids from DB"
		assert isinstance(series_id, int), "Please provide a valid gallery id"
		# We first get all the current tags_mappings_ids related to gallery
		tag_m_ids = []
		executing = [["SELECT tags_mappings_id FROM series_tags_map WHERE series_id=?",
				(series_id,)]]
		CommandQueue.put(executing)
		c = ResultQueue.get()
		for tmd in c.fetchall():
			tag_m_ids.append(tmd['tags_mappings_id'])

		# Then we delete all mappings related to the given series_id
		executing = [["DELETE FROM series_tags_map WHERE series_id=?", (series_id,)]]

		for tmd_id in tag_m_ids:
			executing.append(["DELETE FROM tags_mappings WHERE tags_mappings_id=?",
					 (tmd_id,)])

		CommandQueue.put(executing)
		c = ResultQueue.get()
		del c

	@staticmethod
	def get_gallery_tags(series_id):
		"Returns all tags and namespaces found for the given series_id"
		assert isinstance(series_id, int), "Please provide a valid gallery ID"
		executing = [["SELECT tags_mappings_id FROM series_tags_map WHERE series_id=?",
				(series_id,)]]
		CommandQueue.put(executing)
		cursor = ResultQueue.get()
		tags = {}
		result = cursor.fetchall()
		for tag_map_row in result: # iterate all tag_mappings_ids
			try:
				if not tag_map_row:
					continue
				# get tag and namespace 
				executing = [["""SELECT namespace_id, tag_id FROM tags_mappings
								WHERE tags_mappings_id=?""", (tag_map_row['tags_mappings_id'],)]]
				CommandQueue.put(executing)
				c = ResultQueue.get()
				for row in c.fetchall(): # iterate all rows
					# get namespace
					executing = [["SELECT namespace FROM namespaces WHERE namespace_id=?",
					(row['namespace_id'],)]]
					CommandQueue.put(executing)
					c = ResultQueue.get()
					namespace = c.fetchone()['namespace']

					# get tag
					executing = [["SELECT tag FROM tags WHERE tag_id=?", (row['tag_id'],)]]
					CommandQueue.put(executing)
					c = ResultQueue.get()
					tag = c.fetchone()['tag']

					# add them to dict
					if not namespace in tags:
						tags[namespace] = [tag]
					else:
						# namespace already exists in dict
						tags[namespace].append(tag)
			except IndexError:
				continue
		return tags

	@staticmethod
	def add_tags(object):
		"Adds the given dict_of_tags to the given series_id"
		assert isinstance(object, Gallery), "Please provide a valid gallery of class gallery"
		
		series_id = object.id
		dict_of_tags = object.tags

		def look_exists(tag_or_ns, what):
			"""check if tag or namespace already exists in base
			returns id, else returns None"""
			executing = [["SELECT {}_id FROM {}s WHERE {} LIKE ?".format(what, what, what),
				('%'+tag_or_ns+'%',)]]
			CommandQueue.put(executing)
			c = ResultQueue.get()
			try: # exists
				return c.fetchone()['{}_id'.format(what)]
			except TypeError: # doesnt exist
				return None

		tags_mappings_id_list = []
		# first let's add the tags and namespaces to db
		for namespace in dict_of_tags: 
			tags_list = dict_of_tags[namespace]
			# don't add if it already exists
			try:
				namespace_id = look_exists(namespace, "namespace")
				assert namespace_id
			except AssertionError:
				executing = [["""INSERT INTO namespaces(namespace)
								VALUES(?)""", (namespace,)]]
				CommandQueue.put(executing)
				c = ResultQueue.get()
				namespace_id = c.lastrowid
			
			tags_id_list = []
			for tag in tags_list:
				try:
					tag_id = look_exists(tag, "tag")
					assert tag_id
				except AssertionError:
					executing = [["""INSERT INTO tags(tag)
								VALUES(?)""", (tag,)]]
					CommandQueue.put(executing)
					c = ResultQueue.get()
					tag_id = c.lastrowid
				
				tags_id_list.append(tag_id)


			def look_exist_tag_map(tag_id):
				"Checks DB if the tag_id already exists with the namespace_id, returns id else None"
				executing = [["""SELECT tags_mappings_id FROM tags_mappings
								WHERE namespace_id=? AND tag_id=?""", (namespace_id, tag_id,)]]
				CommandQueue.put(executing)
				c = ResultQueue.get()
				try: # exists
					return c.fetchone()['tags_mappings_id']
				except TypeError: # doesnt exist
					return None

			# time to map the tags to the namespace now
			for tag_id in tags_id_list:
				# First check if tags mappings exists
				try:
					t_map_id = look_exist_tag_map(tag_id)
					if t_map_id:
						tags_mappings_id_list.append(t_map_id)
					else:
						raise TypeError
				except TypeError:
					executing = [["""
					INSERT INTO tags_mappings(namespace_id, tag_id)
					VALUES(?, ?)""", (namespace_id, tag_id,)]]
					CommandQueue.put(executing)
					c = ResultQueue.get()
					# add the tags_mappings_id to our list
					tags_mappings_id_list.append(c.lastrowid)

		# Lastly we map the series_id to the tags_mappings
		for tags_map in tags_mappings_id_list:
				executing = [["""
				INSERT INTO series_tags_map(series_id, tags_mappings_id)
				VALUES(?, ?)""", (series_id, tags_map,)]]
				CommandQueue.put(executing)
				c = ResultQueue.get()
				del c

	@staticmethod
	def modify_tags(series_id, dict_of_tags):
		"Modifies the given tags"

		# We first delete all mappings
		TagDB.del_gallery_mapping(series_id)

		# Now we add the new tags to DB
		weak_gallery = Gallery()
		weak_gallery.id = series_id
		weak_gallery.tags = dict_of_tags

		TagDB.add_tags(weak_gallery)


	@staticmethod
	def get_tag_gallery(tag):
		"Returns all galleries with the given tag"
		pass

	@staticmethod
	def get_ns_tags(namespace):
		"Returns all tags linked to the given namespace"
		pass

	@staticmethod
	def get_ns_tags_gallery(ns_tags):
		"""Returns all galleries linked to the namespace tags.
		Receives a dict like this: {"namespace":["tag1","tag2"]}"""
		pass

	@staticmethod
	def get_all_tags():
		"""
		Returns all tags in database in a list
		"""
		executing = [['SELECT tag FROM tags']]
		CommandQueue.put(executing)
		cursor = ResultQueue.get()
		tags = [t['tag'] for t in cursor.fetchall()]
		return tags

	@staticmethod
	def get_all_ns():
		"""
		Returns all namespaces in database in a list
		"""
		executing = [['SELECT namespace FROM namespaces']]
		CommandQueue.put(executing)
		cursor = ResultQueue.get()
		ns = [n['namespace'] for n in cursor.fetchall()]
		return ns


class HashDB:
	"""
	Contains the following methods:

	get_gallery_hashes -> returns all hashes with the given gallery id in a list
	gen_gallery_hashes <- generates hashes for gallery's chapters and inserts them to db
	rebuild_gallery_hashes <- inserts hashes into DB only if it doesnt already exist
	"""

	@staticmethod
	def get_gallery_hashes(gallery_id):
		"Returns all hashes with the given gallery id in a list"
		executing = [['SELECT hash FROM hashes WHERE series_id=?',
				(gallery_id,)]]
		CommandQueue.put(executing)
		cursor = ResultQueue.get()
		rows = cursor.fetchall()

		hashes = []
		try:
			for row in rows:
				hashes.append(row['hash'])
		except IndexError:
			return []
		return hashes

	@staticmethod
	def gen_gallery_hashes(gallery):
		"Generates hashes for gallery's first chapter and inserts them to DB"
		if gallery.id:
			chap_id = ChapterDB.get_chapter_id(gallery.id, 0)
		try:
			chap_path = gallery.chapters[0]
			imgs = os.listdir(chap_path)
			# filter
		except NotADirectoryError:
			# HACK: Do not need to extract all.. can read bytes form acrhive!!!
			zip = ArchiveFile(gallery.chapters[0])
			chap_path = os.path.join(gui_constants.temp_dir, str(uuid.uuid4()))
			zip.extract_all(chap_path)
			imgs = os.listdir(chap_path)

		except FileNotFoundError:
			return False

		# filter
		imgs = [os.path.join(chap_path,x)\
			for x in imgs if x.endswith(tuple(IMG_FILES))]

		hashes = []
		for i in imgs:
			with open(i, 'rb') as img:
				hashes.append(generate_img_hash(img))
		
		if gallery.id:
			executing = []
			for hash in hashes:
				executing.append(["""INSERT INTO hashes(hash, series_id, chapter_id)
				VALUES(?, ?, ?)""", (hash, gallery.id, chap_id)])

			CommandQueue.put(executing)
			c = ResultQueue.get()
			del c
		return hashes

	@staticmethod
	def rebuild_gallery_hashes(gallery):
		"Inserts hashes into DB only if it doesnt already exist"
		assert isinstance(gallery, Gallery)
		hashes = HashDB.get_gallery_hashes(gallery.id)

		if not hashes:
			hashes = HashDB.gen_gallery_hashes(gallery)
		return hashes

	@staticmethod
	def del_gallery_hashes(gallery_id):
		"Deletes all hashes linked to the given gallery id"
		executing = [["DELETE FROM hashes WHERE series_id=?", gallery_id]]
		CommandQueue.put(executing)
		c = ResultQueue.get()
		del c


class Gallery:
	"""Base class for a gallery.
	Available data:
	id -> Not to be editied. Do not touch.
	title <- [list of titles] or str
	profile <- path to thumbnail
	path <- path to gallery
	artist <- str
	chapters <- {<number>:<path>}
	chapter_size <- int of number of chapters
	info <- str
	fav <- int (1 for true 0 for false)
	type <- str (Manga? Doujin? Other?)
	language <- str
	status <- "unknown", "completed" or "ongoing"
	tags <- list of str
	pub_date <- date
	date_added <- date, will be defaulted to today if not specified
	last_read <- timestamp (e.g. time.time())
	last_update <- last updated file
	last_read <- an integer telling us how many times the gallery has been opened
	hashes <- a list of hashes of the gallery's chapters
	exed <- indicator on if gallery metadata has been fetched
	valid <- a bool indicating the validity of the gallery
	"""
	def __init__(self):
		
		self.id = None # Will be defaulted.
		self.title = None
		self.profile = None
		self.path = None
		self.artist = None
		self.chapters = {}
		self.info = None
		self.fav = 0
		self.type = None
		self.link = ""
		self.language = None
		self.status = None
		self.tags = {}
		self.pub_date = None
		self.date_added = datetime.date.today()
		self.last_read = None
		self.last_update = None
		self.times_read = 0
		self.valid = False
		self._cache_id = None
		self._db_v = None
		self.hashes = []
		self.exed = 0
	def gen_hashes(self):
		"Generate hashes while inserting them into DB"
		if not self.hashes:
			hash = HashDB.gen_gallery_hashes(self)
			if hash:
				self.hashes = hash
				return True
			else:
				return False
		else:
			return True

	def validate(self):
		"Validates gallery, returns status"
		# TODO: Extend this
		validity = []
		status = False

		#if not self.hashes:
		#	HashDB.gen_gallery_hashes(self)
		#	self.hashes = HashDB.get_gallery_hashes(self.id)

		if all(validity):
			status = True
			self.valid = True
		return status

	def invalidities(self):
		"""
		Checks all attributes for invalidities.
		Returns list of string with invalid attribute names
		"""
		return []

	def __str__(self):
		string = """
		ID: {}
		Title: {}
		Profile Path: {}
		Path: {}
		Author: {}
		Description: {}
		Favorite: {}
		Type: {}
		Language: {}
		Status: {}
		Tags: {}
		Publication Date: {}
		Date Added: {}
		Exed: {}
		Hashes: {}

		Chapters: {}
		""".format(self.id, self.title, self.profile, self.path, self.artist,
			 self.info, self.fav, self.type, self.language, self.status, self.tags,
			 self.pub_date, self.date_added, self.exed, len(self.hashes), self.chapters)
		return string

class Bridge(QObject):
	DONE = pyqtSignal(bool)
	def __init__(self, parent=None):
		super().__init__(parent)

	def rebuild_galleries(self):
		if GalleryDB.rebuild_galleries():
			self.DONE.emit(True)
		else:
			self.DONE.emit(False)
if __name__ == '__main__':
	#unit testing here
	date = today()
	print(date)
	#raise RuntimeError("Unit testing still not implemented")