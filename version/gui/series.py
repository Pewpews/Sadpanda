from PyQt5.QtCore import (Qt, QAbstractListModel, QModelIndex, QVariant,
						  QSize, QRect, QEvent, pyqtSignal, QThread,
						  QTimer, QPointF)
from PyQt5.QtGui import (QPixmap, QBrush, QColor, QPainter,
						 QFont, QPen, QTextDocument,
						 QMouseEvent, QHelpEvent,
						 QPixmapCache)
from PyQt5.QtWidgets import (QListView, QFrame, QLabel,
							 QStyledItemDelegate, QStyle,
							 QMenu, QAction, QToolTip,
							 QHBoxLayout, QVBoxLayout,
							 QWidget, QPushButton,
							 QSizePolicy, QTableWidget,
							 QTableWidgetItem, QDialog,
							 QGridLayout, QMessageBox,
							 QFileDialog)
from ..database import fetch, seriesdb
from . import gui_constants, misc

# TODO: Improve this so that it adds to the series dialog,
# so user can edit data before inserting
def populate():
	"Populates the database with series from local drive'"
	msgbox = QMessageBox()
	msgbox.setText("<font color='red'><b>Use with care.</b></font> Choose a folder containing all your series'.")
	msgbox.setInformativeText("Oniichan, are you sure you want to do this?")
	msgbox.setStandardButtons(QMessageBox.Yes | QMessageBox.No)
	msgbox.setDefaultButton(QMessageBox.No)
	if msgbox.exec() == QMessageBox.Yes:
		path = QFileDialog.getExistingDirectory(None, "Choose a folder containing your series'")
		if len(path) is not 0:
			data_thread = QThread()
			loading_thread = QThread()
			loading = misc.Loading()

			if not loading.ON:
				misc.Loading.ON = True
				fetch_instance = fetch.Fetch()
				fetch_instance.series_path = path
				loading.show()

				def finished(status):
					if status:
						SeriesModel.update_data()
						# TODO: make it spawn a dialog instead (from utils.py or misc.py)
						if loading.progress.maximum() == loading.progress.value():
							misc.Loading.ON = False
							loading.hide()
						data_thread.quit
					else:
						loading.setText("<font color=red>An error occured. Try restarting..</font>")
						loading.progress.setStyleSheet("background-color:red")
						data_thread.quit

				def fetch_deleteLater():
					try:
						fetch_instance.deleteLater
					except NameError:
						pass

				def thread_deleteLater(): #NOTE: Isn't this bad?
					data_thread.deleteLater

				def a_progress(prog):
					loading.progress.setValue(prog)
					loading.setText("Searching on local disk...\n(Will take a while on first time)")

				fetch_instance.moveToThread(data_thread)
				fetch_instance.DATA_COUNT.connect(loading.progress.setMaximum)
				fetch_instance.PROGRESS.connect(a_progress)
				data_thread.started.connect(fetch_instance.local)
				fetch_instance.FINISHED.connect(finished)
				fetch_instance.FINISHED.connect(fetch_deleteLater)
				fetch_instance.FINISHED.connect(thread_deleteLater)
				data_thread.start()


class SeriesModel(QAbstractListModel):
	"""Model for Model/View/Delegate framework
	"""
	_data = [] #a list for the data

	ROWCOUNT_CHANGE = pyqtSignal()
	STATUSBAR_MSG = pyqtSignal(str)
	CUSTOM_STATUS_MSG = pyqtSignal(str)

	def __init__(self, parent=None):
		super().__init__(parent)
		self._data_count = 0 # number of items added to model
		self.update_data()
		#self._data_container = []
		self.layoutChanged.connect(lambda: self.status_b_msg("Refreshed")) # quite a hack
		self.dataChanged.connect(lambda: self.status_b_msg("Edited"))
		self.CUSTOM_STATUS_MSG.connect(self.status_b_msg)

	@classmethod
	def update_data(self):
		"Populates the model with data from database"
		self._data = seriesdb.SeriesDB.get_all_series()

	def status_b_msg(self, msg):
		print(msg)
		self.STATUSBAR_MSG.emit(msg)

	def data(self, index, role):
		if not index.isValid():
			return QVariant()
		if index.row() >= len(self._data) or \
			index.row() < 0:
			return QVariant()

		current_row = index.row() 
		current_series = self._data[current_row]

		# TODO: remove this.. not needed anymore, since i use custom role now
		if role == Qt.DisplayRole:
			title = current_series.title
			artist = current_series.artist
			text = {'title':title, 'artist':artist}
			return text
		if role == Qt.DecorationRole:
			pixmap = current_series.profile
			return pixmap
		if role == Qt.BackgroundRole:
			bg_color = QColor(70, 67, 70)
			bg_brush = QBrush(bg_color)
			return bg_brush
		#if role == Qt.ToolTipRole:
		#	return "Example popup!!"
		if role == Qt.UserRole+1:
			return current_series

		return None

	def rowCount(self, index = QModelIndex()):
		return self._data_count

	def flags(self, index):
		if not index.isValid():
			return Qt.ItemIsEnabled
		return Qt.ItemFlags(QAbstractListModel.flags(self, index) |
					  Qt.ItemIsEditable)

	def setData(self, index, value, role = Qt.EditRole):
		"""Takes the new data and appends it to old
		Note: Might want to make make it replace instead"""
		super().setData(self)
		#NOTE: Things are more complicated than this
		#if index.isValid() and 0 <= index.row() < len(self._data):
		#	current_row = index.row()
		#	current_data = self._data[current_row]
		#	self._data.append(value)
		#	self.dataChanged.emit(index, index, ()) # emit a tuple of roles that have changed in 3rd arg
		#	return True
		#return False

	def addRows(self, list_of_series, position=len(_data)-1,
				rows=1, index = QModelIndex()):
		"Adds new series data to model and DB"
		self.beginInsertRows(QModelIndex(), position, position + rows - 1)
		for series in list_of_series:
			n_series = seriesdb.SeriesDB.add_series_return(series)
			self._data.append(n_series)
		self.endInsertRows()
		self.CUSTOM_STATUS_MSG.emit("Added row(s)")
		return True

	def insertRows(self, list_of_series, position=len(_data)-1,
				rows=1, index = QModelIndex()):
		"Inserts new series data to the data list WITHOUT adding to DB"
		self.beginInsertRows(QModelIndex(), position, position + rows - 1)
		for pos, series in enumerate(list_of_series, 1):
			self._data.insert(position+pos, n_series)
		self.endInsertRows()
		self.CUSTOM_STATUS_MSG.emit("Added row(s)")
		return True

	def replaceRows(self, list_of_series, position=len(_data)-1, rows=1, index=QModelIndex()):
		"replaces series data to the data list WITHOUT adding to DB"
		for pos, series in enumerate(list_of_series):
			del self._data[position+pos]
			self._data.insert(position+pos, series)
		self.dataChanged.emit(index, index, [Qt.UserRole+1])

	#def removeRows(self, int, int2, parent = QModelIndex()):
	#	pass

	#def sortBy(self, str):
	#	"""takes on of the following string as param
	#	str <- 'title', 'metadata', 'artist', 'last read', 'newest'"""
	#	pass


	def canFetchMore(self, index):
		if self._data_count < len(self._data):
			return True
		else: 
			return False

	def fetchMore(self, index):
		diff = len(self._data) - self._data_count
		item_to_fetch = min(gui_constants.PREFETCH_ITEM_AMOUNT, diff)

		self.beginInsertRows(index, self._data_count,
					   self._data_count+item_to_fetch-1)
		self._data_count += item_to_fetch
		self.endInsertRows()
		self.ROWCOUNT_CHANGE.emit()

class ChapterModel(SeriesModel):
	pass

class CustomDelegate(QStyledItemDelegate):
	"A custom delegate for the model/view framework"

	BUTTON_CLICKED = pyqtSignal(int, QModelIndex)

	def __init__(self):
		super().__init__()
		self.W = gui_constants.THUMB_W_SIZE
		self.H = gui_constants.THUMB_H_SIZE
		self._state = None
		QPixmapCache.setCacheLimit(gui_constants.THUMBNAIL_CACHE_SIZE)
		self._painted_indexes = {}

	def key(self, index):
		"Assigns an unique key to indexes"
		if index in self._painted_indexes:
			return self._painted_indexes[index]
		else:
			id = str(len(self._painted_indexes))
			self._painted_indexes[index] = id
			return self._painted_indexes[index]

	def paint(self, painter, option, index):
		self.initStyleOption(option, index)

		assert isinstance(painter, QPainter)

		series = index.data(Qt.UserRole+1)
		popup = index.data(Qt.ToolTipRole)
		title = series.title
		artist = series.artist

		# Enable this to see the defining box
		#painter.drawRect(option.rect)

		# define font size
		if 30 > len(title) > 20:
			title_size = "font-size:12px;"
		elif 40 > len(title) >= 30:
			title_size = "font-size:11px;"
		elif 50 > len(title) >= 40:
			title_size = "font-size:10px;"
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
		r = option.rect.adjusted(1, 0, -1, -1)
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

		painter.setRenderHint(QPainter.SmoothPixmapTransform)

		# if we can't find a cached image
		if not isinstance(QPixmapCache.find(self.key(index)), QPixmap):
			self.image = QPixmap(index.data(Qt.DecorationRole))
			id = self.key(index)
			QPixmapCache.insert(id, self.image)
			if self.image.height() < self.image.width(): #to keep aspect ratio
				painter.drawPixmap(QRect(x, y, w, self.image.height()),
						self.image)
			else:
				painter.drawPixmap(QRect(x, y, w, h),
						self.image)
		else:
			self.image = QPixmapCache.find(self.key(index))
			if self.image.height() < self.image.width(): #to keep aspect ratio
				painter.drawPixmap(QRect(x, y, w, self.image.height()),
						self.image)
			else:
				painter.drawPixmap(QRect(x, y, w, h),
						self.image)
		
		# draw star if it's favourited
		if series.fav == 1:
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
		painter.restore()

		if option.state & QStyle.State_MouseOver:
			painter.fillRect(option.rect, QColor(225,225,225,90)) #70

		if option.state & QStyle.State_Selected:
			painter.fillRect(option.rect, QColor(164,164,164,120)) #option.palette.highlight()

		if option.state & QStyle.State_Selected:
			painter.setPen(QPen(option.palette.highlightedText().color()))

	def sizeHint(self, QStyleOptionViewItem, QModelIndex):
		return QSize(self.W, self.H)


	def editorEvent(self, event, model, option, index):
		"Mouse events for each item in the view are defined here"
		assert isinstance(index, QModelIndex)
		if event.type() == QEvent.MouseButtonPress:
			mouseEvent = QMouseEvent(event)
			if mouseEvent.buttons() == Qt.LeftButton:
				self._state = (index.row(), index.column())
				self.BUTTON_CLICKED.emit(1, index)#self._state)
				print("Clicked")
				return True
			else: return super().editorEvent(event, model, option, index)
		else:
			return super().editorEvent(event, model, option, index)



class MangaView(QListView):
	"""
	TODO: (zoom-in/zoom-out) mousekeys
	"""

	SERIES_DIALOG = pyqtSignal()

	def __init__(self, parent=None):
		super().__init__(parent)
		self.setViewMode(self.IconMode)
		self.H = gui_constants.GRIDBOX_H_SIZE
		self.W = gui_constants.GRIDBOX_W_SIZE
		self.setGridSize(QSize(self.W, self.H))
		self.setSpacing(10)
		self.setResizeMode(self.Adjust)
		# all items have the same size (perfomance)
		self.setUniformItemSizes(True)
		# improve scrolling
		self.setVerticalScrollMode(self.ScrollPerPixel)
		self.setHorizontalScrollBarPolicy(Qt.ScrollBarAlwaysOff)
		# prevent all items being loaded at the same time
		#self.setLayoutMode(self.Batched)
		#self.setBatchSize(15) #Only loads 20 images at a time
		self.setMouseTracking(True)
		self.series_model = SeriesModel()
		self.setModel(self.series_model)
		self.SERIES_DIALOG.connect(self.spawn_dialog)

	def foo(self):
		pass

	def favourite(self, index):
		assert isinstance(index, QModelIndex)
		series = index.data(Qt.UserRole+1)
		if series.fav == 1:
			n_series = seriesdb.SeriesDB.fav_series_set(series.id, 0)
			self.series_model.replaceRows([n_series], index.row(), 1, index)
			self.series_model.CUSTOM_STATUS_MSG.emit("Unfavourited")
		else:
			n_series = seriesdb.SeriesDB.fav_series_set(series.id, 1)
			self.series_model.replaceRows([n_series], index.row(), 1, index)
			self.series_model.CUSTOM_STATUS_MSG.emit("Favourited")

	def contextMenuEvent(self, event):
		handled = False
		custom = False
		index = self.indexAt(event.pos())

		menu = QMenu()
		all_1 = QAction("Open in external viewer", menu, triggered = self.foo)
		all_2 = QAction("Edit...", menu, triggered = lambda: self.spawn_dialog(index))
		all_3 = QAction("Remove", menu, triggered = self.foo)
		def fav():
			self.favourite(index)

		if index.isValid():
			if index.data(Qt.UserRole+1).fav==1: # here you can limit which items to show these actions for
				action_1 = QAction("Favourite", menu, triggered = fav)
				action_1.setCheckable(True)
				action_1.setChecked(True)
				menu.addAction(action_1)
				handled = True
				custom = True
			if index.data(Qt.UserRole+1).fav==0: # here you can limit which items to show these actions for
				action_1 = QAction("Favourite", menu, triggered = fav)
				action_1.setCheckable(True)
				action_1.setChecked(False)
				menu.addAction(action_1)
				handled = True
				custom = True
		else:
			add_series = QAction("&Add new Series...", menu,
						triggered = self.SERIES_DIALOG.emit)
			menu.addAction(add_series)
			sort_main = QAction("&Sort by", menu)
			menu.addAction(sort_main)
			sort_menu = QMenu()
			sort_main.setMenu(sort_menu)
			asc_desc = QAction("Asc/Desc", menu, triggered = self.foo)
			s_title = QAction("Title", menu, triggered = self.foo)
			s_artist = QAction("Author", menu, triggered = self.foo)
			sort_menu.addAction(asc_desc)
			sort_menu.addSeparator()
			sort_menu.addAction(s_title)
			sort_menu.addAction(s_artist)
			refresh = QAction("&Refresh", menu,
					 triggered = self.series_model.layoutChanged.emit)
			menu.addAction(refresh)
			handled = True

		if handled and custom:
			menu.addSeparator()
			menu.addAction(all_1)
			menu.addAction(all_2)
			menu.addAction(all_3)
			menu.exec_(event.globalPos())
			event.accept()
		elif handled:
			menu.exec_(event.globalPos())
			event.accept()
		else:
			event.ignore()

	#need this for debugging purposes
	def resizeEvent(self, resizeevent):
		super().resizeEvent(resizeevent)
		#print(resizeevent.size())

	def replace_edit_series(self, list_of_series, pos):
		"Replaces the view and DB with given list of series, at given position"
		assert isinstance(list_of_series, list), "Please pass a series to replace with"
		assert isinstance(pos, int)
		for series in list_of_series:
			seriesdb.SeriesDB.modify_series(series.id, series.title, series.artist,
									  series.info, series.type, series.language,
									  series.status, series.pub_date)
		self.series_model.replaceRows([series], pos, len(list_of_series))

	def spawn_dialog(self, index=False):
		if not index:
			dialog = misc.SeriesDialog()
			dialog.SERIES.connect(self.series_model.addRows)
			dialog.trigger() # TODO: implement mass series' adding
		else:
			dialog = misc.SeriesDialog()
			dialog.SERIES_EDIT.connect(self.replace_edit_series)
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

class ChapterView(QListView):
	"A view for chapters"
	def __init__(self, parent=None):
		super().__init__()
		self.setViewMode(self.IconMode)
		self.H = gui_constants.GRIDBOX_H_SIZE
		self.W = gui_constants.GRIDBOX_W_SIZE
		self.setGridSize(QSize(self.W, self.H))
		self.setSpacing(10)
		self.setResizeMode(self.Adjust)
		# all items have the same size (perfomance)
		self.setUniformItemSizes(True)
		# improve scrolling
		self.setVerticalScrollMode(self.ScrollPerPixel)
		self.setHorizontalScrollBarPolicy(Qt.ScrollBarAlwaysOff)
		# prevent all items being loaded at the same time
		#self.setLayoutMode(self.Batched)
		#self.setBatchSize(15) #Only loads 20 images at a time
		self.setMouseTracking(True)


class ChapterInfo(QFrame):
	"A view for chapter data"
	def __init__(self, parent=None):
		super().__init__(parent)
		self.H = gui_constants.CHAP_IMAGE_H
		self.W = self.H//1.6
		self.setFrameStyle(1)
		self.setLineWidth(1)
		self.setMaximumWidth(self.W*1.2)
		#self.data = []
		self.initUI()

	def display_manga(self, index):
		"""Receives a QModelIndex and updates the
		viewport with specific manga data"""
		series = index.data(Qt.UserRole+1)
		self.drawContents(series)

	def initUI(self):
		"Constructs UI for the chapter info view"
		background_layout = QVBoxLayout()
		self.setLayout(background_layout)
		

		# The image
		self.image_icon_size = QSize(self.W, self.H)
		self.image_box = QLabel()
		background_layout.addWidget(self.image_box, 0, Qt.AlignHCenter)

		# the metadata
		self.metadata = QTableWidget()
		self.metadata.setRowCount(10)
		self.metadata.setColumnCount(2)
		#self.metadata.setColumnWidth(2,70)
		#self.metadata.resizeColumnsToContents()
		self.metadata.setSizePolicy(QSizePolicy.Expanding, QSizePolicy.Expanding)
		self.metadata.setShowGrid(False)
		self.metadata.horizontalHeader().setVisible(False)
		self.metadata.verticalHeader().setVisible(False)
		self.metadata.setFrameShape(QFrame.NoFrame)
		self.metadata.setFocusPolicy(Qt.NoFocus)
		self.metadata.setWordWrap(True)
		background_layout.addWidget(self.metadata, 2)

		def t_props(obj):
			obj.setWordWrap(True)

		self.title = QLabel()
		t_props(self.title)
		self.title.setAlignment(Qt.AlignHCenter)
		self.metadata.setCellWidget(0,0,self.title)
		self.metadata.setSpan(0,0,1,2)

		self.artist = QLabel()
		self.artist.setAlignment(Qt.AlignLeft)
		self.metadata.setCellWidget(1,0, self.artist)

		self.chapter_count = QLabel()
		self.chapter_count.setAlignment(Qt.AlignRight)
		self.metadata.setCellWidget(1, 1, self.chapter_count)

		self.info = QLabel()
		self.info.setAlignment(Qt.AlignLeft)
		t_props(self.info)
		self.metadata.setCellWidget(2,0, self.info)
		self.metadata.setSpan(2,0,1,2)

		#self.last_read = QLabel("None")
		#self.last_update = QLabel("None")

		self.date_added = QLabel()
		self.date_added.setAlignment(Qt.AlignLeft)
		self.metadata.setCellWidget(3,0, self.date_added)

		self.pub_date = QLabel()
		self.pub_date.setAlignment(Qt.AlignRight)
		self.metadata.setCellWidget(3,1, self.pub_date)

		self.tags = QLabel()
		t_props(self.tags)
		self.tags.setAlignment(Qt.AlignLeft)
		self.metadata.setCellWidget(4,0, self.tags)
		self.metadata.setSpan(4, 0, 1, 2)

		self.path = QLabel()
		t_props(self.path)
		self.path.setAlignment(Qt.AlignLeft)
		self.metadata.setCellWidget(5,0, self.path)
		self.metadata.setSpan(5,0,1,2)


	def drawContents(self, series):
		assert isinstance(series, seriesdb.Series), "Please provide a series of Series class from SeriesDB"
		
		new_image = QPixmap(series.profile).scaled(self.image_icon_size, Qt.KeepAspectRatio,
					Qt.SmoothTransformation)
		self.image_box.setPixmap(new_image)
		self.title.setText("<font size='4' color='#585858'><b>"+series.title+"</b></font>")
		self.artist.setText("<font size='3' color='#585858'>"+series.artist+"</font>")
		self.chapter_count.setText("<font size='2' color='#B7153E'><i>Chapters:</i></font>"+"{}".format(len(series.chapters)))
		self.info.setText("<font size='2' color='#B7153E'><i>Description:</i></font><br>"+series.info)
		self.date_added.setText("<font size='2' color='#B7153E'><i>Date Added:</i></font><br>"+series.date_added)
		self.pub_date.setText("<font size='2' color='#B7153E'><i>Date Published:</i></font><br>"+series.pub_date)
		self.tags.setText("<font size='2' color='#B7153E'><i>Tags:</i></font><br>"+"TODO")
		self.path.setText("<font size='2' color='#B7153E'><i>Path:</i></font><br><font size='2'><i>"+series.path+"</i></font><br>")
		#self.path.setText("Path:\n"+series.path)
		self.metadata.resizeRowsToContents()

	#def resizeEvent(self, resizeevent):
	#	"""This method basically need to make sure
	#	the image in chapter view gets resized when moving
	#	splitter"""
	#	super().resizeEvent(resizeevent)
	#	self.MAIN_SIZE = resizeevent.size()


if __name__ == '__main__':
	raise NotImplementedError("Unit testing not yet implemented")
