#!/usr/bin/env python3

import logging
import os

from PyQt6 import QtCore, QtGui, QtWidgets

from artiq import __artiq_dir__ as artiq_dir
from artiq.gui.tools import EditableMdiTabBar


class MdiArea(QtWidgets.QMdiArea):
    def __init__(self):
        QtWidgets.QMdiArea.__init__(self)
        self.pixmap = QtGui.QPixmap(os.path.join(
            artiq_dir, "gui", "logo_ver.svg"))

        self.setActivationOrder(
            QtWidgets.QMdiArea.WindowOrder.ActivationHistoryOrder)

        self.tile = QtGui.QShortcut(
            QtGui.QKeySequence('Ctrl+Shift+T'), self)
        self.tile.activated.connect(
            lambda: self.tileSubWindows())

        self.cascade = QtGui.QShortcut(
            QtGui.QKeySequence('Ctrl+Shift+C'), self)
        self.cascade.activated.connect(
            lambda: self.cascadeSubWindows())
        self.setHorizontalScrollBarPolicy(
                QtCore.Qt.ScrollBarPolicy.ScrollBarAsNeeded)
        self.setVerticalScrollBarPolicy(
                QtCore.Qt.ScrollBarPolicy.ScrollBarAsNeeded)

    def paintEvent(self, event):
        QtWidgets.QMdiArea.paintEvent(self, event)
        painter = QtGui.QPainter(self.viewport())
        x = (self.width() - self.pixmap.width()) // 2
        y = (self.height() - self.pixmap.height()) // 2
        painter.setOpacity(0.5)
        painter.drawPixmap(x, y, self.pixmap)

    def setTabName(self, name):
        self.tab_name = name


class MultipleTabsManagement:
    def __init__(self, main_window):
        self.tab_widget = QtWidgets.QTabWidget()
        self.tab_widget.setTabBar(EditableMdiTabBar(main_window))
        self.tab_widget.setTabsClosable(True)
        self.tab_widget.setMovable(True)
        self.tab_widget.tabCloseRequested.connect(self.close_mdi_area)
        main_window.setCentralWidget(self.tab_widget)

        plus_button = QtWidgets.QToolButton()
        plus_button.setText("+")
        plus_button.setToolTip("Add new workspace")
        plus_button.clicked.connect(self.new_mdi_area)
        self.tab_widget.setCornerWidget(plus_button,
                                        QtCore.Qt.Corner.TopLeftCorner)

        self.add_mdi_area("Workspace 1")

        self.tab_widget.currentChanged.connect(self.on_tab_changed)

    def on_tab_changed(self, index):
        # We want to refresh geometry to properly place minimized windows after
        # resizing from other MDI area.
        # It causes 2 other issues that are addressed here:
        # 1. The focus stays on the minimized window.
        # 2. If the code below executes, maximized windows get un-maximized -
        #    this is not obvious and seems to depend on MDI implementation.
        mdi_area = self.tab_widget.widget(index)
        # Check which subwindow is active
        activeSubWindow = mdi_area.activeSubWindow()
        # Check if active subwindow is maximized. If not, neither window is
        # maximized
        wasMaximized = activeSubWindow.isMaximized() if activeSubWindow else False

        for subwindow in mdi_area.subWindowList():
            # Refresh geometry to properly place minimized windows
            if subwindow.isMinimized():
                subwindow.setWindowState(QtCore.Qt.WindowState.WindowNoState)
                subwindow.setWindowState(QtCore.Qt.WindowState.WindowMinimized)
        # Restore focus and maximization
        if activeSubWindow:
            mdi_area.setActiveSubWindow(activeSubWindow)
            activeSubWindow.widget().setFocus()
            if wasMaximized:
                activeSubWindow.setWindowState(QtCore.Qt.WindowState.WindowMaximized)

    def add_mdi_area(self, title):
        # Create a new MDI area (tab) with the given title
        mdi_area = MdiArea()
        mdi_area.setTabName(title)
        index = self.tab_widget.addTab(mdi_area, title)
        self.tab_widget.setTabToolTip(index, "Double click to rename")

        self.tab_widget.setTabsClosable(self.tab_widget.count() > 1)

    def tab_name_exists(self, name, ignore_index=None):
        for i in range(self.tab_widget.count()):
            if ignore_index is not None and i == ignore_index:
                continue
            widget = self.tab_widget.widget(i)
            if hasattr(widget, "tab_name") and widget.tab_name == name:
                return True
        return False

    def new_mdi_area(self):
        # Add a new MDI area (tab) with an auto-generated unique title
        idx = 1
        title = f"Workspace {idx}"
        while self.tab_name_exists(title):
            idx = idx + 1
            title = f"Workspace {idx}"
        self.add_mdi_area(title)
        self.tab_widget.setCurrentIndex(self.tab_widget.count() - 1)

    def close_mdi_area(self, index):
        if self.tab_widget.count() == 1:
            logging.warning("Cannot close last workspace")
            return
        mdi_area = self.tab_widget.widget(index)
        for experiment in mdi_area.subWindowList():
            mdi_area.removeSubWindow(experiment)
            experiment.close()
        self.tab_widget.removeTab(index)
        mdi_area.deleteLater()

        self.tab_widget.setTabsClosable(self.tab_widget.count() > 1)

    def rename_mdi_area(self, index, title):
        if self.tab_widget.count() < index + 1:
            logging.warning("Requested workspace does not exist")
            return
        tab_bar = self.tab_widget.tabBar()
        tab_bar.set_tab_name(index, title)

    def get_mdi_areas_state(self):
        return [self.tab_widget.tabText(i) for i in range(self.tab_widget.count())]

    def restore_mdi_areas_state(self, mdi_areas_list):
        for index, title in enumerate(mdi_areas_list):
            if index == 0:
                # The first workspace is created always in init in order to
                # handle the case of no state to restore
                self.rename_mdi_area(index, title)
            else:
                self.add_mdi_area(title)
