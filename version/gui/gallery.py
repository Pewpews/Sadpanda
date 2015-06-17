"""
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

from PyQt5.QtCore import (Qt, QAbstractListModel, QModelIndex, QVariant,
						  QSize, QRect, QEvent, pyqtSignal, QThread,
						  QTimer, QPointF, QSortFilterProxyModel,
						  QAbstractTableModel, QItemSelectionModel,
						  QPoint)
from PyQt5.QtGui import (QPixmap, QBrush, QColor, QPainter, 
						 QPen, QTextDocument,
						 QMouseEvent, QHelpEvent,
						 QPixmapCache, QCursor, QPalette, QKeyEvent)
from PyQt5.QtWidgets import (QListView, QFrame, QLabel,
							 QStyledItemDelegate, QStyle,
							 QMenu, QAction, QToolTip, QVBoxLayout,
							 QSizePolicy, QTableWidget, QScrollArea,
							 QHBoxLayout, QFormLayout, QDesktopWidget,
							 QWidget, QHeaderView, QTableView, QApplication,
							 QMessageBox)
import threading, logging, os
import re as regex

from ..database import gallerydb
from . import gui_constants, misc
from .. import utils

log = logging.getLogger(__name__)
log_i = log.info
log_d = log.debug
log_w = log.warning
log_e = log.error
log_c = log.critical

class Popup(QWidget):
	def __init__(self):
		super().__init__(None, Qt.FramelessWindowHint | Qt.WindowStaysOnTopHint)
		self.setAttribute(Qt.WA_ShowWithoutActivating)
		self.initUI()
		self.setWindowModality(Qt.WindowModal)
		#self.resize(gui_constants.POPUP_WIDTH,gui_constants.POPUP_HEIGHT)
		self.setFixedWidth(gui_constants.POPUP_WIDTH)
		self.setMaximumHeight(gui_constants.POPUP_HEIGHT)
	
	def initUI(self):
		main_layout = QVBoxLayout()
		self.setLayout(main_layout)
		form_l = QFormLayout()
		main_layout.addLayout(form_l)
		self.title = QLabel()
		self.title.setWordWrap(True)
		self.title_lbl = QLabel("Title:")
		self.artist = QLabel()
		self.artist.setWordWrap(True)
		self.artist_lbl = QLabel("Author:")
		self.chapters = QLabel()
		self.chapters_lbl = QLabel("Chapters:")
		self.info = QLabel()
		self.info_lbl = QLabel("Description:")
		self.info.setWordWrap(True)

		self.lang = QLabel()
		lang_lbl = QLabel("Language:")

		type_status_l = QHBoxLayout()
		self.type = QLabel()
		type_status_l.addWidget(self.type, 0, Qt.AlignLeft)
		self.status = QLabel()
		type_status_l.addWidget(self.status, 0, Qt.AlignRight)

		self.tags = QLabel()
		self.tags.setTextFormat(Qt.RichText)
		self.tags.setWordWrap(True)
		self.tags_lbl = QLabel("Tags:")

		self.pub_date = QLabel()
		self.date_added = QLabel()

		link_lbl = QLabel("Link:")
		self.link = QLabel()
		self.link.setWordWrap(True)

		form_l.addRow(self.title_lbl, self.title)
		form_l.addRow(self.artist_lbl, self.artist)
		form_l.addRow(self.chapters_lbl, self.chapters)
		form_l.addRow(self.info_lbl, self.info)
		form_l.addRow(lang_lbl, self.lang)
		form_l.addRow(self.tags_lbl, self.tags)
		form_l.addRow(link_lbl, self.link)

	def set_gallery(self, gallery):
		def tags_parser(tags):
			string = ""
			try:
				if len(tags['default']) > 0:
					has_default = True
				else:
					has_default = False
			except KeyError:
				has_default = False

			for namespace in tags:
				if namespace == 'default':
					for n, tag in enumerate(tags[namespace], 1):
						if n == 1:
							string = tag + string
						else:
							string = tag + ', ' + string
				else:
					if not has_default:
						string += '<b>'+namespace + ':</b> '
						has_default = True
					else:
						string += '<br><b>' + namespace + ':</b> '
					for n, tag in enumerate(tags[namespace], 1):
						if n != len(tags[namespace]):
							string += tag + ', '
						else:
							string += tag

			return string
		self.title.setText(gallery.title)
		self.artist.setText(gallery.artist)
		self.chapters.setText("{}".format(len(gallery.chapters)))
		self.info.setText(gallery.info)
		self.lang.setText(gallery.language)
		self.type.setText(gallery.type)
		self.status.setText(gallery.status)
		self.tags.setText(tags_parser(gallery.tags))
		self.link.setText(gallery.link)

class SortFilterModel(QSortFilterProxyModel):
	def __init__(self, parent=None):
		super().__init__(parent)
		self._data = []

		# filtering
		self.fav = False
		self.tags = {}
		self.title = ""
		self.artist = ""

	def fav_view(self):
		self.fav = True
		self.invalidateFilter()

	def catalog_view(self):
		self.fav = False
		self.invalidateFilter()
	
	def change_model(self, model):
		self.setSourceModel(model)
		self._data = self.sourceModel()._data

	def populate_data(self):
		self.sourceModel().populate_data()

	def status_b_msg(self, msg):
		self.sourceModel().status_b_msg(msg)

	def addRows(self, list_of_gallery, position=None,
				rows=1, index = QModelIndex()):
		self.sourceModel().addRows(list_of_gallery, position, rows, index)

	def replaceRows(self, list_of_gallery, position, rows=1, index=QModelIndex()):
		self.sourceModel().replaceRows(list_of_gallery, position, rows, index)

	def search(self, term, title=True, artist=True, tags=True):
		"""
		Receives a search term.
		If title/artist/tags True: searches in it
		"""

		def f_tags():
			self.tags = utils.tag_to_dict(term)

		def f_title():
			self.title = term

		def f_artist():
			self.artist = term

		if title and artist and tags:
			f_tags()
			f_title()
			f_artist()

		self.invalidateFilter()

	def filterAcceptsRow(self, source_row, index_parent):
		allow = False
		gallery = None

		def do_search():
			l = {'title':False, 'artist':False, 'tags':False}
			if self.title:
				l['title'] = True
			if self.artist:
				l['artist'] = True
			if self.tags:
				try:
					a = self.tags['default']
					if a:
						l['tags'] = True
				except IndexError:
					l['tags'] = True
			
			for x in l:
				if l[x]:
					return l
			return None

		def return_searched(where):
			allow = False

			def re_search(a, b):
				"searches for a in b"
				m = regex.search("({})".format(a), b, regex.IGNORECASE)
				return m

			if where['title']:
				if re_search(self.title, gallery.title):
					allow = True
			if where['artist']:
				if re_search(self.artist, gallery.artist):
					allow = True
			if where['tags']:
				#print(self.tags)
				ser_tags = utils.tag_to_string(gallery.tags)
				for ns in self.tags:
					if ns == 'default':
						for tag in self.tags[ns]:
							if re_search(tag, ser_tags):
								#print(ser_tags)
								allow = True
					else:
						t = {ns:[]}
						for tag in self.tags[ns]:
							t[ns].append(tag)
						tags_string = utils.tag_to_string(t)
						#print(tags_string)
						if re_search(tags_string, ser_tags):
							allow = True

			return allow

		if self.sourceModel():
			index = self.sourceModel().index(source_row, 0, index_parent)
			if index.isValid():
				gallery = index.data(Qt.UserRole+1)
				if self.fav:
					if gallery.fav == 1:
						s = do_search()
						if s:
							allow = return_searched(s)
						else: allow = True
				else:
					s = do_search()
					if s:
						allow = return_searched(s)
					else: allow = True

		return allow

class GalleryModel(QAbstractTableModel):
	"""Model for Model/View/Delegate framework
	"""

	ROWCOUNT_CHANGE = pyqtSignal()
	STATUSBAR_MSG = pyqtSignal(str)
	CUSTOM_STATUS_MSG = pyqtSignal(str)
	_data = []

	def __init__(self, parent=None):
		super().__init__(parent)
		self._data_count = 0 # number of items added to model
		self.populate_data()
		#self._data_container = []
		self.dataChanged.connect(lambda: self.status_b_msg("Edited"))
		self.dataChanged.connect(lambda: self.ROWCOUNT_CHANGE.emit())
		self.layoutChanged.connect(lambda: self.ROWCOUNT_CHANGE.emit())
		self.CUSTOM_STATUS_MSG.connect(self.status_b_msg)
		self._TITLE = gui_constants.TITLE
		self._ARTIST = gui_constants.ARTIST
		self._TAGS = gui_constants.TAGS
		self._TYPE = gui_constants.TYPE
		self._FAV = gui_constants.FAV
		self._CHAPTERS = gui_constants.CHAPTERS
		self._LANGUAGE = gui_constants.LANGUAGE
		self._LINK = gui_constants.LINK

	def populate_data(self):
		"Populates the model with data from database"
		self._data = gallerydb.GalleryDB.get_all_gallery()
		self.layoutChanged.emit()
		self.ROWCOUNT_CHANGE.emit()
		self._data_count = len(self._data)

	def status_b_msg(self, msg):
		self.STATUSBAR_MSG.emit(msg)

	def data(self, index, role=Qt.DisplayRole):
		if not index.isValid():
			return QVariant()
		if index.row() >= len(self._data) or \
			index.row() < 0:
			return QVariant()

		current_row = index.row() 
		current_gallery = self._data[current_row]
		current_column = index.column()

		def column_checker():
			if current_column == self._TITLE:
				title = current_gallery.title
				return title
			elif current_column == self._ARTIST:
				artist = current_gallery.artist
				return artist
			elif current_column == self._TAGS:
				tags = utils.tag_to_string(current_gallery.tags)
				return tags
			elif current_column == self._TYPE:
				type = current_gallery.type
				return type
			elif current_column == self._FAV:
				if current_gallery.fav == 1:
					return u'\u2605'
				else:
					return ''
			elif current_column == self._CHAPTERS:
				return len(current_gallery.chapters)
			elif current_column == self._LANGUAGE:
				return current_gallery.language
			elif current_column == self._LINK:
				return current_gallery.link

		if role == Qt.DisplayRole:
			return column_checker()
		# for artist searching
		if role == Qt.UserRole+2:
			artist = current_gallery.artist
			return artist

		if role == Qt.DecorationRole:
			pixmap = current_gallery.profile
			return pixmap
		
		if role == Qt.BackgroundRole:
			bg_color = QColor(242, 242, 242)
			bg_brush = QBrush(bg_color)
			return bg_brush

		if role == Qt.ToolTipRole:
			return column_checker()

		#if role == Qt.ToolTipRole:
		#	return "Example popup!!"
		if role == Qt.UserRole+1:
			return current_gallery

		# favorite satus
		if role == Qt.UserRole+3:
			return current_gallery.fav


		return None

	def rowCount(self, index = QModelIndex()):
		return self._data_count

	def columnCount(self, parent = QModelIndex()):
		return len(gui_constants.COLUMNS)

	def headerData(self, section, orientation, role = Qt.DisplayRole):
		if role == Qt.TextAlignmentRole:
			return Qt.AlignLeft
		if role != Qt.DisplayRole:
			return None
		if orientation == Qt.Horizontal:
			if section == self._TITLE:
				return 'Title'
			elif section == self._ARTIST:
				return 'Author'
			elif section == self._TAGS:
				return 'Tags'
			elif section == self._TYPE:
				return 'Type'
			elif section == self._FAV:
				return u'\u2605'
			elif section == self._CHAPTERS:
				return 'Chapters'
			elif section == self._LANGUAGE:
				return 'Language'
			elif section == self._LINK:
				return 'Link'
		return section + 1
	#def flags(self, index):
	#	if not index.isValid():
	#		return Qt.ItemIsEnabled
	#	return Qt.ItemFlags(QAbstractListModel.flags(self, index) |
	#				  Qt.ItemIsEditable)

	def addRows(self, list_of_gallery, position=None,
				rows=1, index = QModelIndex()):
		"Adds new gallery data to model and to DB"
		loading = misc.Loading(self.parent())
		loading.setText('Adding...')
		loading.progress.setMinimum(0)
		loading.progress.setMaximum(0)
		loading.show()
		from ..database.gallerydb import PROFILE_TO_MODEL
		if not position:
			position = len(self._data)
		self.beginInsertRows(QModelIndex(), position, position + rows - 1)
		for gallery in list_of_gallery:
			threading.Thread(target=gallerydb.GalleryDB.add_gallery_return, args=(gallery,)).start()
			gallery.profile = PROFILE_TO_MODEL.get()
			self._data.insert(0, gallery)
		self.endInsertRows()
		self.CUSTOM_STATUS_MSG.emit("Added item(s)")
		self.ROWCOUNT_CHANGE.emit()
		loading.close()
		return True

	def insertRows(self, list_of_gallery, position,
				rows=1, index = QModelIndex()):
		"Inserts new gallery data to the data list WITHOUT adding to DB"
		self.beginInsertRows(QModelIndex(), position, position + rows - 1)
		for pos, gallery in enumerate(list_of_gallery, 1):
			self._data.append(gallery)
		self.endInsertRows()
		self.CUSTOM_STATUS_MSG.emit("Added item(s)")
		self.ROWCOUNT_CHANGE.emit()
		return True

	def replaceRows(self, list_of_gallery, position, rows=1, index=QModelIndex()):
		"replaces gallery data to the data list WITHOUT adding to DB"
		for pos, gallery in enumerate(list_of_gallery):
			del self._data[position+pos]
			self._data.insert(position+pos, gallery)
		self.dataChanged.emit(index, index, [Qt.UserRole+1])

	def removeRows(self, position, rows=1, index=QModelIndex()):
		"Deletes gallery data from the model data list. OBS: doesn't touch DB!"
		self.beginRemoveRows(QModelIndex(), position, position + rows - 1)
		self._data = self._data[:position] + self._data[position + rows:]
		self._data_count -= rows
		self.endRemoveRows()
		self.ROWCOUNT_CHANGE.emit()
		return True

	#def canFetchMore(self, index):
	#	if self._data_count < len(self._data):
	#		return True
	#	else: 
	#		return False

	#def fetchMore(self, index):
	#	print('Fetching more')
	#	diff = len(self._data) - self._data_count
	#	item_to_fetch = min(gui_constants.PREFETCH_ITEM_AMOUNT, diff)

	#	self.beginInsertRows(index, self._data_count,
	#				   self._data_count+item_to_fetch-1)
	#	self._data_count += item_to_fetch
	#	self.endInsertRows()
	#	self.ROWCOUNT_CHANGE.emit()

class CustomDelegate(QStyledItemDelegate):
	"A custom delegate for the model/view framework"

	POPUP = pyqtSignal()
	CONTEXT_ON = False

	def __init__(self):
		super().__init__()
		self.W = gui_constants.THUMB_W_SIZE
		self.H = gui_constants.THUMB_H_SIZE
		QPixmapCache.setCacheLimit(gui_constants.THUMBNAIL_CACHE_SIZE)
		self.popup_window = Popup()
		self.popup_timer = QTimer()
		self._painted_indexes = {}
		#self.popup_timer.timeout.connect(self.POPUP.emit)

	def key(self, key):
		"Assigns an unique key to indexes"
		if key:
			return self._painted_indexes[key]
		else:
			k = len(self._painted_indexes)
			self._painted_indexes[str(k)] = str(k)
			return str(k)

	def paint(self, painter, option, index):
		#self.initStyleOption(option, index)

		assert isinstance(painter, QPainter)
		if index.data(Qt.UserRole+1):
			if gui_constants.HIGH_QUALITY_THUMBS:
				painter.setRenderHint(QPainter.SmoothPixmapTransform)
			gallery = index.data(Qt.UserRole+1)
			title = gallery.title
			artist = gallery.artist
			# Enable this to see the defining box
			#painter.drawRect(option.rect)
			# define font size
			if 20 > len(title) > 15:
				title_size = "font-size:12px;"
			elif 30 > len(title) > 20:
				title_size = "font-size:11px;"
			elif 40 > len(title) >= 30:
				title_size = "font-size:10px;"
			elif 50 > len(title) >= 40:
				title_size = "font-size:9px;"
			elif len(title) >= 50:
				title_size = "font-size:8px;"
			else:
				title_size = ""

			if 30 > len(artist) > 20:
				artist_size = "font-size:11px;"
			elif 40 > len(artist) >= 30:
				artist_size = "font-size:9px;"
			elif len(artist) >= 40:
				artist_size = "font-size:8px;"
			else:
				artist_size = ""

			#painter.setPen(QPen(Qt.NoPen))
			r = option.rect.adjusted(1, -2, -1, 0)
			rec = r.getRect()
			x = rec[0]
			y = rec[1] + 3
			w = rec[2]
			h = rec[3] - 5


			text_area = QTextDocument()
			text_area.setDefaultFont(option.font)
			text_area.setHtml("""
			<head>
			<style>
			#area
			{{
				display:flex;
				width:140px;
				height:10px
			}}
			#title {{
			position:absolute;
			color: white;
			font-weight:bold;
			{}
			}}
			#artist {{
			position:absolute;
			color:white;
			top:20px;
			right:0;
			{}
			}}
			</style>
			</head>
			<body>
			<div id="area">
			<center>
			<div id="title">{}
			</div>
			<div id="artist">{}
			</div>
			</div>
			</center>
			</body>
			""".format(title_size, artist_size, title, artist, "Chapters"))
			text_area.setTextWidth(w)

			#chapter_area = QTextDocument()
			#chapter_area.setDefaultFont(option.font)
			#chapter_area.setHtml("""
			#<font color="black">{}</font>
			#""".format("chapter"))
			#chapter_area.setTextWidth(w)

			# if we can't find a cached image
			if not gallery._cache_id:
				gallery._cache_id = self.key(gallery._cache_id)
			pix_cache = QPixmapCache.find(gallery._cache_id)
			if not isinstance(pix_cache, QPixmap):
				self.image = QPixmap(index.data(Qt.DecorationRole))
				QPixmapCache.insert(gallery._cache_id, self.image)
				if self.image.height() < self.image.width(): #to keep aspect ratio
					painter.drawPixmap(QPoint(x,y),
							self.image)
				else:
					painter.drawPixmap(QPoint(x,y),
							self.image)
			else:
				self.image = pix_cache
				if self.image.height() < self.image.width(): #to keep aspect ratio
					painter.drawPixmap(QPoint(x,y),
							self.image)
				else:
					painter.drawPixmap(QPoint(x,y),
							self.image)
		
			# draw star if it's favorited
			if gallery.fav == 1:
				painter.drawPixmap(QPointF(x,y), QPixmap(gui_constants.STAR_PATH))

			#draw the label for text
			painter.save()
			painter.translate(option.rect.x(), option.rect.y()+140)
			box_color = QBrush(QColor(0,0,0,123))
			painter.setBrush(box_color)
			rect = QRect(0, 0, w+2, 60) #x, y, width, height
			painter.fillRect(rect, box_color)
			painter.restore()
			painter.save()
			# draw text
			painter.translate(option.rect.x(), option.rect.y()+142)
			text_area.drawContents(painter)
			#painter.resetTransform()
			painter.restore()

			if option.state & QStyle.State_MouseOver:
				painter.fillRect(option.rect, QColor(225,225,225,90)) #70
			else:
				self.popup_window.hide()
			if option.state & QStyle.State_Selected:
				painter.fillRect(option.rect, QColor(164,164,164,120))

			#if option.state & QStyle.State_Selected:
			#	painter.setPen(QPen(option.palette.highlightedText().color()))
		else:
			super().paint(painter, option, index)

	def sizeHint(self, QStyleOptionViewItem, QModelIndex):
		return QSize(self.W, self.H)

# TODO: Redo this part to avoid duplicated code
class MangaView(QListView):
	"""
	TODO: (zoom-in/zoom-out) mousekeys
	"""

	STATUS_BAR_MSG = pyqtSignal(str)
	SERIES_DIALOG = pyqtSignal()

	def __init__(self, parent=None):
		super().__init__(parent)
		self.setViewMode(self.IconMode)
		self.H = gui_constants.GRIDBOX_H_SIZE
		self.W = gui_constants.GRIDBOX_W_SIZE
		self.setGridSize(QSize(self.W, self.H))
		self.setResizeMode(self.Adjust)
		# all items have the same size (perfomance)
		self.setUniformItemSizes(True)
		self.setSelectionBehavior(self.SelectItems)
		self.setSelectionMode(self.ExtendedSelection)
		# improve scrolling
		self.setVerticalScrollMode(self.ScrollPerPixel)
		self.setHorizontalScrollBarPolicy(Qt.ScrollBarAlwaysOff)
		self.setLayoutMode(self.SinglePass)
		self.setBatchSize(1)#gui_constants.PREFETCH_ITEM_AMOUNT)
		self.setMouseTracking(True)
		self.sort_model = SortFilterModel()
		self.sort_model.setDynamicSortFilter(True)
		self.sort_model.setFilterCaseSensitivity(Qt.CaseInsensitive)
		self.sort_model.setSortLocaleAware(True)
		self.sort_model.setSortCaseSensitivity(Qt.CaseInsensitive)
		self.manga_delegate = CustomDelegate()
		self.setItemDelegate(self.manga_delegate)
		self.gallery_model = GalleryModel(parent)
		self.sort_model.change_model(self.gallery_model)
		self.sort_model.sort(0)
		self.setModel(self.sort_model)
		self.SERIES_DIALOG.connect(self.spawn_dialog)
		self.doubleClicked.connect(self.open_chapter)
	#	self.ti = QTimer()
	#	self.ti.timeout.connect(self.test_)
	#	self.ti.start(5000)

	#def test_(self):
	#	"find all galleries in viewport"
	#	def col_next_prepare(index):
	#		"Calculates where the next index is"
	#		rect = self.visualRect(index)
	#		new_col = QPoint(rect.x() + rect.width() + rect.width(),
	#					   rect.y())
	#		return new_col

	#	#find first index locatiion. A wild guess!!
	#	f_indx = self.indexAt(QPoint(87,130))
	#	found = 1
	#	f_rect = self.visualRect(f_indx) # need the first index's rect
	#	row = 1 # which row are we on
	#	while row: # while row is is valid
	#		rect = self.visualRect(f_indx) # rect of current index
	#		next_col_point = col_next_prepare(f_indx)
	#		#calculate the next row
	#		next_row_point = QPoint(f_rect.x()+10,
	#					   rect.y()+rect.height()+(rect.height()//2))
	#		found += 1
	#		# while there are stil more colums
	#		while self.viewport().rect().contains(next_col_point,
	#								  proper=True):
	#			next_indx = self.indexAt(next_col_point) # find the next index
	#			if not next_indx:
	#				break
	#			found += 1
	#			# time to prepare the next iteration
	#			next_col_point = col_next_prepare(next_indx)
	#			print('Moving to next col')
			
	#		if self.viewport().rect().contains(next_row_point, proper=True):
	#			f_indx = self.indexAt(next_row_point)
	#			if f_indx.isValid():
	#				row += 1
	#				print('Moving to next row')
	#		row = None

	#	print('Found ', found)

	def remove_gallery(self, index_list, local=False):
		msgbox = QMessageBox()
		msgbox.setIcon(msgbox.Question)
		msgbox.setStandardButtons(msgbox.Yes | msgbox.No)
		if len(index_list) > 1:
			if not local:
				msg = 'Are you sure you want to remove {} selected galleries?'.format(
				len(index_list))
			else:
				msg = 'Are you sure you want to remove {} selected galleries and their files/directories?'.format(
				len(index_list))

			msgbox.setText(msg)
		else:
			if not local:
				msg = 'Are you sure you want to remove this gallery?'
			else:
				msg = 'Are you sure you want to remove this gallery and it\'s file/diriectory?'
			msgbox.setText(msg)

		if msgbox.exec() == msgbox.Yes:
			gallery_list = []
			for index in index_list:
				gallery = index.data(Qt.UserRole+1)
				if index.isValid() and gallery:
					self.rowsAboutToBeRemoved(index.parent(), index.row(), index.row())
					self.gallery_model.removeRows(index.row(), 1)
					gallery_list.append(gallery)
			log_i('Removing {} galleries'.format(len(gallery_list)))
			threading.Thread(target=gallerydb.GalleryDB.del_gallery,
						args=(gallery_list, local), daemon=True).start()

	def favorite(self, index):
		assert isinstance(index, QModelIndex)
		gallery = index.data(Qt.UserRole+1)
		if gallery.fav == 1:
			gallery.fav = 0
			self.model().replaceRows([gallery], index.row(), 1, index)
			gallerydb.GalleryDB.fav_gallery_set(gallery.id, 0)
			self.gallery_model.CUSTOM_STATUS_MSG.emit("Unfavorited")
		else:
			gallery.fav = 1
			self.model().replaceRows([gallery], index.row(), 1, index)
			gallerydb.GalleryDB.fav_gallery_set(gallery.id, 1)
			self.gallery_model.CUSTOM_STATUS_MSG.emit("Favorited")

	def open_chapter(self, index, chap_numb=0):
		if isinstance(index, list):
			for x in index:
				gallery = x.data(Qt.UserRole+1)
				self.STATUS_BAR_MSG.emit("Opening chapters of selected galleries")
				try:
					threading.Thread(target=utils.open,
							   args=(gallery.chapters[chap_numb],)).start()
				except IndexError:
					pass
		else:
			gallery = index.data(Qt.UserRole+1)
			self.STATUS_BAR_MSG.emit("Opening chapter {} of {}".format(chap_numb+1,
																 gallery.title))
			try:
				threading.Thread(target=utils.open,
						   args=(gallery.chapters[chap_numb],)).start()
			except IndexError:
				pass

	def del_chapter(self, index, chap_numb):
		gallery = index.data(Qt.UserRole+1)
		if len(gallery.chapters) < 2:
			self.remove_gallery([index])
		else:
			msgbox = QMessageBox(self)
			msgbox.setText('Are you sure you want to delete:')
			msgbox.setIcon(msgbox.Question)
			msgbox.setInformativeText('Chapter {} of {}'.format(chap_numb+1,
														  gallery.title))
			msgbox.setStandardButtons(msgbox.Yes | msgbox.No)
			if msgbox.exec() == msgbox.Yes:
				gallery.chapters.pop(chap_numb, None)
				self.gallery_model.replaceRows([gallery], index.row())
				gallerydb.ChapterDB.del_chapter(gallery.id, chap_numb)

	def refresh(self):
		self.gallery_model.layoutChanged.emit() # TODO: CAUSE OF CRASH! FIX ASAP
		self.STATUS_BAR_MSG.emit("Refreshed")

	def contextMenuEvent(self, event):
		handled = False
		custom = False
		index = self.indexAt(event.pos())
		index = self.sort_model.mapToSource(index)

		selected = False
		select_indexes = self.selectedIndexes()
		if len(select_indexes) > 1:
			selected = True

		def remove_selection(local=False):
			select = self.selectionModel().selection()
			s_select = self.model().mapSelectionToSource(select)
			indexes = s_select.indexes()
			for indx in indexes:
				if not indx.isValid():
					del indexes[indx]
			self.remove_gallery(indexes, local)

		menu = QMenu()
		remove_act = QAction('Remove', menu)
		remove_menu = QMenu()
		remove_act.setMenu(remove_menu)
		remove_gallery_act = QAction('Remove gallery', remove_menu,
							   triggered=lambda: self.remove_gallery([index]))
		remove_menu.addAction(remove_gallery_act)
		remove_local_gallery_act = QAction('Remove gallery and files', remove_menu,
							   triggered=lambda: self.remove_gallery([index], True))
		remove_menu.addAction(remove_local_gallery_act)

		if selected:
			remove_menu.addSeparator()
			#remove_selected_act = QAction("Remove selected", remove_menu,
			#	   triggered = remove_selection)
			#remove_menu.addAction(remove_selected_act)
			#remove_local_selected_act = QAction('Remove selected and their files', remove_menu,
			#	   triggered = lambda: remove_selection(True))
			#remove_menu.addAction(remove_local_selected_act)

			all_0 = QAction("Open first chapters", menu,
					  triggered = lambda: self.open_chapter(select_indexes, 0))

		all_1 = QAction("Open first chapter", menu,
					triggered = lambda: self.open_chapter(index, 0))
		all_2 = QAction("Edit...", menu, triggered = lambda: self.spawn_dialog(index))
		def fav():
			self.favorite(index)


		# add the chapter menus
		def chapters():
			menu.addSeparator()
			chapters_menu = QAction("Chapters", menu)
			menu.addAction(chapters_menu)
			open_chapters = QMenu()
			chapters_menu.setMenu(open_chapters)
			for number, chap_number in enumerate(range(len(
				index.data(Qt.UserRole+1).chapters)), 1):
				chap_action = QAction("Open chapter {}".format(
					number), open_chapters, triggered = lambda: self.open_chapter(index, chap_number))
				open_chapters.addAction(chap_action)

		def open_link():
			link = index.data(Qt.UserRole+1).link
			utils.open_web_link(link)

		def sort_title():
			self.sort_model.setSortRole(Qt.DisplayRole)
			self.sort_model.sort(0, Qt.AscendingOrder)

		def sort_artist():
			self.sort_model.setSortRole(Qt.UserRole+2)
			self.sort_model.sort(0, Qt.AscendingOrder)

		def asc_desc():
			if self.sort_model.sortOrder() == Qt.AscendingOrder:
				self.sort_model.sort(0, Qt.DescendingOrder)
			else:
				self.sort_model.sort(0, Qt.AscendingOrder)

		def op_folder(selected=False):
			if selected:
				self.STATUS_BAR_MSG.emit('Opening folders')
				for x in select_indexes:
					ser = x.data(Qt.UserRole+1)
					utils.open_path(os.path.split(ser.path)[0])
			else:
				self.STATUS_BAR_MSG.emit('Opening folder')
				ser = index.data(Qt.UserRole+1)
				utils.open_path(os.path.split(ser.path)[0])

		def add_chapters():
			def add_chdb(chaps):
				gallery = index.data(Qt.UserRole+1)
				log_d('Adding new chapter for {}'.format(gallery.title))
				gallerydb.ChapterDB.add_chapters_raw(gallery.id, chaps)
				gallery = gallerydb.GalleryDB.get_gallery_by_id(gallery.id)
				self.gallery_model.replaceRows([gallery], index.row())

			ch_widget = misc.ChapterAddWidget(index.data(Qt.UserRole+1),
								   self.parentWidget())
			ch_widget.CHAPTERS.connect(add_chdb)
			ch_widget.show()

		if index.isValid():
			self.manga_delegate.CONTEXT_ON = True

			if index.data(Qt.UserRole+1).link != "":
				ext_action = QAction("Open link", menu, triggered = open_link)

			action_1 = QAction("Favorite", menu, triggered = fav)
			action_1.setCheckable(True)
			if index.data(Qt.UserRole+1).fav==1: # here you can limit which items to show these actions for
				action_1.setChecked(True)
			else:
				action_1.setChecked(False)
			menu.addAction(action_1)
			chapters()
			handled = True
			custom = True
		else:
			add_gallery = QAction("&Add new Gallery...", menu,
						triggered = self.SERIES_DIALOG.emit)
			menu.addAction(add_gallery)
			sort_main = QAction("&Sort by", menu)
			menu.addAction(sort_main)
			sort_menu = QMenu()
			sort_main.setMenu(sort_menu)
			asc_desc = QAction("Asc/Desc", menu,
					  triggered = asc_desc)
			s_title = QAction("Title", menu,
					 triggered = sort_title)
			s_artist = QAction("Author", menu,
					  triggered = sort_artist)
			s_date = QAction("Date Added", menu)
			sort_menu.addAction(asc_desc)
			sort_menu.addSeparator()
			sort_menu.addAction(s_title)
			sort_menu.addAction(s_artist)
			sort_menu.addAction(s_date)
			refresh = QAction("&Refresh", menu,
					 triggered = self.refresh)
			menu.addAction(refresh)
			handled = True

		if handled and custom:
			# chapters
			try:
				menu.addAction(all_0)
			except:
				pass
			menu.addAction(all_1)
			if not selected:
				add_chap_act = QAction('Add chapters', menu,
						   triggered=add_chapters)
				menu.addAction(add_chap_act)
				remo_chap_act = QAction('Remove chapter', menu)
				remove_menu.addAction(remo_chap_act)
				remove_chap_menu = QMenu()
				remo_chap_act.setMenu(remove_chap_menu)
				for number, chap_number in enumerate(range(len(
					index.data(Qt.UserRole+1).chapters)), 1):
					chap_action = QAction("Remove chapter {}".format(
						number), remove_chap_menu, triggered = lambda: self.del_chapter(index, chap_number))
					remove_chap_menu.addAction(chap_action)
			menu.addSeparator()
			# folders
			if selected:
				folder_select_act = QAction('Open folders', menu, triggered = lambda: op_folder(True))
				menu.addAction(folder_select_act)
			folder_act = QAction('Open folder', menu, triggered = op_folder)
			menu.addAction(folder_act)
			menu.addAction(all_2)
			# link
			try:
				menu.addAction(ext_action)
			except:
				pass
			menu.addSeparator()
			# remove
			menu.addAction(remove_act)
			menu.exec_(event.globalPos())
			self.manga_delegate.CONTEXT_ON = False
			event.accept()
		elif handled:
			menu.exec_(event.globalPos())
			self.manga_delegate.CONTEXT_ON = False
			event.accept()
		else:
			event.ignore()

	#need this for debugging purposes
	def resizeEvent(self, resizeevent):
		super().resizeEvent(resizeevent)
		#print(resizeevent.size())

	def replace_edit_gallery(self, list_of_gallery, pos):
		"Replaces the view and DB with given list of gallery, at given position"
		assert isinstance(list_of_gallery, list), "Please pass a gallery to replace with"
		assert isinstance(pos, int)
		for gallery in list_of_gallery:

			kwdict = {'title':gallery.title,
			 'artist':gallery.artist,
			 'info':gallery.info,
			 'type':gallery.type,
			 'language':gallery.language,
			 'status':gallery.status,
			 'pub_date':gallery.pub_date,
			 'tags':gallery.tags,
			 'link':gallery.link}

			threading.Thread(target=gallerydb.GalleryDB.modify_gallery,
							 args=(gallery.id,), kwargs=kwdict).start()
		self.gallery_model.replaceRows([gallery], pos, len(list_of_gallery))

	def spawn_dialog(self, index=False):
		if not index:
			dialog = misc.GalleryDialog()
			dialog.SERIES.connect(self.gallery_model.addRows)
			dialog.trigger() # TODO: implement mass galleries adding
		else:
			dialog = misc.GalleryDialog()
			dialog.SERIES_EDIT.connect(self.replace_edit_gallery)
			dialog.trigger([index])

	def updateGeometries(self):
		super().updateGeometries()
		self.verticalScrollBar().setSingleStep(gui_constants.SCROLL_SPEED)

	#unusable code
	#def event(self, event):
	#	#if event.type() == QEvent.ToolTip:
	#	#	help_event = QHelpEvent(event)
	#	#	index = self.indexAt(help_event.globalPos())
	#	#	if index is not -1:
	#	#		QToolTip.showText(help_event.globalPos(), "Tooltip!")
	#	#	else:
	#	#		QToolTip().hideText()
	#	#		event.ignore()
	#	#	return True
	#	if event.type() == QEvent.Enter:
	#		print("hovered")
	#	else:
	#		return super().event(event)

	def entered(*args, **kwargs):
		return super().entered(**kwargs)

class MangaTableView(QTableView):
	STATUS_BAR_MSG = pyqtSignal(str)
	SERIES_DIALOG = pyqtSignal()

	def __init__(self, parent=None):
		super().__init__(parent)
		# options
		self.setHorizontalScrollBarPolicy(Qt.ScrollBarAsNeeded)
		self.setSelectionBehavior(self.SelectRows)
		self.setSelectionMode(self.ExtendedSelection)
		self.setShowGrid(True)
		self.setSortingEnabled(True)
		v_header = self.verticalHeader()
		v_header.sectionResizeMode(QHeaderView.Fixed)
		v_header.setDefaultSectionSize(24)
		v_header.hide()
		palette = self.palette()
		palette.setColor(palette.Highlight, QColor(88, 88, 88, 70))
		palette.setColor(palette.HighlightedText, QColor('black'))
		self.setPalette(palette)
		self.setIconSize(QSize(0,0))
		self.doubleClicked.connect(self.open_chapter)

	def viewportEvent(self, event):
		if event.type() == QEvent.ToolTip:
			h_event = QHelpEvent(event)
			index = self.indexAt(h_event.pos())
			if index.isValid():
				size_hint = self.itemDelegate(index).sizeHint(self.viewOptions(),
												  index)
				rect = QRect(0, 0, size_hint.width(), size_hint.height())
				rect_visual = self.visualRect(index)
				if rect.width() <= rect_visual.width():
					QToolTip.hideText()
					return True
		return super().viewportEvent(event)

	def remove_gallery(self, index_list):
		msgbox = QMessageBox()
		msgbox.setIcon(msgbox.Question)
		msgbox.setStandardButtons(msgbox.Yes | msgbox.No)
		if len(index_list) > 1:
			msgbox.setText('Are you sure you want to remove {} selected?'.format(
				len(index_list)))
		else:
			msgbox.setText('Are you sure you want to remove?')

		if msgbox.exec() == msgbox.Yes:
			gallery_list = []
			for index in index_list:
				gallery = index.data(Qt.UserRole+1)
				if index.isValid() and gallery:
					self.rowsAboutToBeRemoved(index.parent(), index.row(), index.row())
					self.gallery_model.removeRows(index.row(), 1)
					gallery_list.append(gallery)
			log_i('Removed {} galleries'.format(len(gallery_list)))
			threading.Thread(target=gallerydb.GalleryDB.del_gallery,
						args=(gallery_list,), daemon=True).start()

	def favorite(self, index):
		assert isinstance(index, QModelIndex)
		gallery = index.data(Qt.UserRole+1)
		# TODO: don't need to fetch from DB here... 
		if gallery.fav == 1:
			gallery.fav = 0
			self.gallery_model.replaceRows([gallery], index.row(), 1, index)
			gallerydb.GalleryDB.fav_gallery_set(gallery.id, 0)
			self.gallery_model.CUSTOM_STATUS_MSG.emit("Unfavorited")
		else:
			gallery.fav = 1
			self.gallery_model.replaceRows([gallery], index.row(), 1, index)
			gallerydb.GalleryDB.fav_gallery_set(gallery.id, 1)
			self.gallery_model.CUSTOM_STATUS_MSG.emit("Favorited")

	def open_chapter(self, index, chap_numb=0):
		if isinstance(index, list):
			for x in index:
				gallery = x.data(Qt.UserRole+1)
				self.STATUS_BAR_MSG.emit("Opening chapters of selected galleries")
				try:
					threading.Thread(target=utils.open,
							   args=(gallery.chapters[chap_numb],)).start()
				except IndexError:
					pass
		else:
			gallery = index.data(Qt.UserRole+1)
			self.STATUS_BAR_MSG.emit("Opening chapter {} of {}".format(chap_numb+1,
																 gallery.title))
			try:
				threading.Thread(target=utils.open,
						   args=(gallery.chapters[chap_numb],)).start()
			except IndexError:
				pass

	def del_chapter(self, index, chap_numb):
		gallery = index.data(Qt.UserRole+1)
		if len(gallery.chapters) < 2:
			self.remove_gallery([index])
		else:
			msgbox = QMessageBox(self)
			msgbox.setText('Are you sure you want to delete:')
			msgbox.setIcon(msgbox.Question)
			msgbox.setInformativeText('Chapter {} of {}'.format(chap_numb+1,
														  gallery.title))
			msgbox.setStandardButtons(msgbox.Yes | msgbox.No)
			if msgbox.exec() == msgbox.Yes:
				gallery.chapters.pop(chap_numb, None)
				self.gallery_model.replaceRows([gallery], index.row())
				gallerydb.ChapterDB.del_chapter(gallery.id, chap_numb)

	def refresh(self):
		self.gallery_model.populate_data() # TODO: CAUSE OF CRASH! FIX ASAP
		self.STATUS_BAR_MSG.emit("Refreshed")

	def contextMenuEvent(self, event):
		handled = False
		custom = False
		index = self.indexAt(event.pos())
		index = self.sort_model.mapToSource(index)

		selected = False
		select_indexes = self.selectedIndexes()
		if len(select_indexes) > len(gui_constants.COLUMNS):
			selected = True

		def remove_selection():
			select = self.selectionModel().selection()
			s_select = self.model().mapSelectionToSource(select)
			indexes = s_select.indexes()
			self.remove_gallery(indexes)

		menu = QMenu()
		remove_act = QAction('Remove', menu)
		remove_menu = QMenu()
		remove_act.setMenu(remove_menu)
		remove_gallery_act = QAction('Remove gallery', remove_menu,
							   triggered=lambda: self.remove_gallery([index]))
		remove_menu.addAction(remove_gallery_act)
		remove_local_gallery_act = QAction('Remove gallery and files', remove_menu,
							   triggered=lambda: self.remove_gallery([index], True))
		remove_menu.addAction(remove_local_gallery_act)

		if selected:
			remove_menu.addSeparator()
			#remove_selected_act = QAction("Remove selected", remove_menu,
			#	   triggered = remove_selection)
			#remove_menu.addAction(remove_selected_act)
			#remove_local_selected_act = QAction('Remove selected and their files', remove_menu,
			#	   triggered = lambda: remove_selection(True))
			#remove_menu.addAction(remove_local_selected_act)

			all_0 = QAction("Open first chapters", menu,
					  triggered = lambda: self.open_chapter(select_indexes, 0))

		all_1 = QAction("Open first chapter", menu,
					triggered = lambda: self.open_chapter(index, 0))
		all_2 = QAction("Edit...", menu, triggered = lambda: self.spawn_dialog(index))
		def fav():
			self.favorite(index)


		# add the chapter menus
		def chapters():
			menu.addSeparator()
			chapters_menu = QAction("Chapters", menu)
			menu.addAction(chapters_menu)
			open_chapters = QMenu()
			chapters_menu.setMenu(open_chapters)
			for number, chap_number in enumerate(range(len(
				index.data(Qt.UserRole+1).chapters)), 1):
				chap_action = QAction("Open chapter {}".format(
					number), open_chapters, triggered = lambda: self.open_chapter(index, chap_number))
				open_chapters.addAction(chap_action)

		def open_link():
			link = index.data(Qt.UserRole+1).link
			utils.open_web_link(link)

		def sort_title():
			self.sort_model.setSortRole(Qt.DisplayRole)
			self.sort_model.sort(0, Qt.AscendingOrder)

		def sort_artist():
			self.sort_model.setSortRole(Qt.UserRole+2)
			self.sort_model.sort(0, Qt.AscendingOrder)

		def asc_desc():
			if self.sort_model.sortOrder() == Qt.AscendingOrder:
				self.sort_model.sort(0, Qt.DescendingOrder)
			else:
				self.sort_model.sort(0, Qt.AscendingOrder)

		def op_folder(selected=False):
			if selected:
				self.STATUS_BAR_MSG.emit('Opening folders')
				for x in select_indexes:
					ser = x.data(Qt.UserRole+1)
					utils.open_path(os.path.split(ser.path)[0])
			else:
				self.STATUS_BAR_MSG.emit('Opening folder')
				ser = index.data(Qt.UserRole+1)
				utils.open_path(os.path.split(ser.path)[0])

		def add_chapters():
			def add_chdb(chaps):
				gallery = index.data(Qt.UserRole+1)
				log_d('Adding new chapter for {}'.format(gallery.title))
				gallerydb.ChapterDB.add_chapters_raw(gallery.id, chaps)
				gallery = gallerydb.GalleryDB.get_gallery_by_id(gallery.id)
				self.gallery_model.replaceRows([gallery], index.row())

			ch_widget = misc.ChapterAddWidget(index.data(Qt.UserRole+1),
								   self.parentWidget())
			ch_widget.CHAPTERS.connect(add_chdb)
			ch_widget.show()

		if index.isValid():

			if index.data(Qt.UserRole+1).link != "":
				ext_action = QAction("Open link", menu, triggered = open_link)

			action_1 = QAction("Favorite", menu, triggered = fav)
			action_1.setCheckable(True)
			if index.data(Qt.UserRole+1).fav==1: # here you can limit which items to show these actions for
				action_1.setChecked(True)
			else:
				action_1.setChecked(False)
			menu.addAction(action_1)
			chapters()
			handled = True
			custom = True
		else:
			add_gallery = QAction("&Add new Gallery...", menu,
						triggered = self.SERIES_DIALOG.emit)
			menu.addAction(add_gallery)
			sort_main = QAction("&Sort by", menu)
			menu.addAction(sort_main)
			sort_menu = QMenu()
			sort_main.setMenu(sort_menu)
			asc_desc = QAction("Asc/Desc", menu,
					  triggered = asc_desc)
			s_title = QAction("Title", menu,
					 triggered = sort_title)
			s_artist = QAction("Author", menu,
					  triggered = sort_artist)
			s_date = QAction("Date Added", menu)
			sort_menu.addAction(asc_desc)
			sort_menu.addSeparator()
			sort_menu.addAction(s_title)
			sort_menu.addAction(s_artist)
			sort_menu.addAction(s_date)
			refresh = QAction("&Refresh", menu,
					 triggered = self.refresh)
			menu.addAction(refresh)
			handled = True

		if handled and custom:
			# chapters
			try:
				menu.addAction(all_0)
			except:
				pass
			menu.addAction(all_1)
			if not selected:
				add_chap_act = QAction('Add chapters', menu,
						   triggered=add_chapters)
				menu.addAction(add_chap_act)
				remo_chap_act = QAction('Remove chapter', menu)
				remove_menu.addAction(remo_chap_act)
				remove_chap_menu = QMenu()
				remo_chap_act.setMenu(remove_chap_menu)
				for number, chap_number in enumerate(range(len(
					index.data(Qt.UserRole+1).chapters)), 1):
					chap_action = QAction("Remove chapter {}".format(
						number), remove_chap_menu, triggered = lambda: self.del_chapter(index, chap_number))
					remove_chap_menu.addAction(chap_action)
			menu.addSeparator()
			# folders
			if selected:
				folder_select_act = QAction('Open folders', menu, triggered = lambda: op_folder(True))
				menu.addAction(folder_select_act)
			folder_act = QAction('Open folder', menu, triggered = op_folder)
			menu.addAction(folder_act)
			menu.addAction(all_2)
			# link
			try:
				menu.addAction(ext_action)
			except:
				pass
			menu.addSeparator()
			# remove
			menu.addAction(remove_act)
			menu.exec_(event.globalPos())
			event.accept()
		elif handled:
			menu.exec_(event.globalPos())
			event.accept()
		else:
			event.ignore()

	def replace_edit_gallery(self, list_of_gallery, pos):
		"Replaces the view and DB with given list of gallery, at given position"
		assert isinstance(list_of_gallery, list), "Please pass a gallery to replace with"
		assert isinstance(pos, int)
		for gallery in list_of_gallery:

			kwdict = {'title':gallery.title,
			 'artist':gallery.artist,
			 'info':gallery.info,
			 'type':gallery.type,
			 'language':gallery.language,
			 'status':gallery.status,
			 'pub_date':gallery.pub_date,
			 'tags':gallery.tags,
			 'link':gallery.link}

			threading.Thread(target=gallerydb.GalleryDB.modify_gallery,
							 args=(gallery.id,), kwargs=kwdict).start()
		self.gallery_model.replaceRows([gallery], pos, len(list_of_gallery))

	def spawn_dialog(self, index=False):
		if not index:
			dialog = misc.GalleryDialog()
			dialog.SERIES.connect(self.gallery_model.addRows)
			dialog.trigger() # TODO: implement mass galleries adding
		else:
			dialog = misc.GalleryDialog()
			dialog.SERIES_EDIT.connect(self.replace_edit_gallery)
			dialog.trigger([index])

if __name__ == '__main__':
	raise NotImplementedError("Unit testing not yet implemented")