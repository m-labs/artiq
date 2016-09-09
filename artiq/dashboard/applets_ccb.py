import logging

from PyQt5 import QtCore, QtWidgets

from artiq.gui import applets


logger = logging.getLogger(__name__)


class AppletsCCBDock(applets.AppletsDock):
    def __init__(self, *args, **kwargs):
        applets.AppletsDock.__init__(self, *args, **kwargs)

        sep = QtWidgets.QAction(self.table)
        sep.setSeparator(True)
        self.table.addAction(sep)

        ccbp_group_menu = QtWidgets.QMenu()
        actiongroup = QtWidgets.QActionGroup(self.table)
        actiongroup.setExclusive(True)
        self.ccbp_group_none = QtWidgets.QAction("No policy", self.table)
        self.ccbp_group_none.setCheckable(True)
        self.ccbp_group_none.triggered.connect(lambda: self.set_ccbp(""))
        ccbp_group_menu.addAction(self.ccbp_group_none)
        actiongroup.addAction(self.ccbp_group_none)
        self.ccbp_group_ignore = QtWidgets.QAction("Ignore requests", self.table)
        self.ccbp_group_ignore.setCheckable(True)
        self.ccbp_group_ignore.triggered.connect(lambda: self.set_ccbp("ignore"))
        ccbp_group_menu.addAction(self.ccbp_group_ignore)
        actiongroup.addAction(self.ccbp_group_ignore)
        self.ccbp_group_create = QtWidgets.QAction("Create applets", self.table)
        self.ccbp_group_create.setCheckable(True)
        self.ccbp_group_create.triggered.connect(lambda: self.set_ccbp("create"))
        ccbp_group_menu.addAction(self.ccbp_group_create)
        actiongroup.addAction(self.ccbp_group_create)
        self.ccbp_group_enable = QtWidgets.QAction("Create and enable applets",
                                                    self.table)
        self.ccbp_group_enable.setCheckable(True)
        self.ccbp_group_enable.triggered.connect(lambda: self.set_ccbp("enable"))
        ccbp_group_menu.addAction(self.ccbp_group_enable)
        actiongroup.addAction(self.ccbp_group_enable)
        self.ccbp_group_action = QtWidgets.QAction("Group CCB policy", self.table)
        self.ccbp_group_action.setMenu(ccbp_group_menu)
        self.table.addAction(self.ccbp_group_action)
        self.table.itemSelectionChanged.connect(self.update_group_ccbp_menu)

        ccbp_global_menu = QtWidgets.QMenu()
        actiongroup = QtWidgets.QActionGroup(self.table)
        actiongroup.setExclusive(True)
        self.ccbp_global_ignore = QtWidgets.QAction("Ignore requests", self.table)
        self.ccbp_global_ignore.setCheckable(True)
        ccbp_global_menu.addAction(self.ccbp_global_ignore)
        actiongroup.addAction(self.ccbp_global_ignore)
        self.ccbp_global_create = QtWidgets.QAction("Create applets", self.table)
        self.ccbp_global_create.setCheckable(True)
        self.ccbp_global_create.setChecked(True)
        ccbp_global_menu.addAction(self.ccbp_global_create)
        actiongroup.addAction(self.ccbp_global_create)
        self.ccbp_global_enable = QtWidgets.QAction("Create and enable applets",
                                                    self.table)
        self.ccbp_global_enable.setCheckable(True)
        ccbp_global_menu.addAction(self.ccbp_global_enable)
        actiongroup.addAction(self.ccbp_global_enable)
        ccbp_global_action = QtWidgets.QAction("Global CCB policy", self.table)
        ccbp_global_action.setMenu(ccbp_global_menu)
        self.table.addAction(ccbp_global_action)

    def update_group_ccbp_menu(self):
        selection = self.table.selectedItems()
        if selection:
            item = selection[0]
            if item.ty == "applet":
                item = item.parent()
            if item is None:
                self.ccbp_group_action.setEnabled(False)
            else:
                self.ccbp_group_action.setEnabled(True)
                print(item, item.ty)
                ccbp = self.table.itemWidget(item, 1).text()
                if ccbp == "":
                    self.ccbp_group_none.setChecked(True)
                else:
                    getattr(self, "ccbp_group_" + ccbp).setChecked(True)
        else:
            self.ccbp_group_action.setEnabled(False)

    def set_ccbp(self, ccbp):
        item = self.table.selectedItems()[0]
        if item.ty == "applet":
            item = item.parent()
        self.table.itemWidget(item, 1).setText(ccbp)

    def get_ccpb_global(self):
        if self.ccbp_global_ignore.isChecked():
            return "ignore"
        if self.ccbp_global_create.isChecked():
            return "create"
        if self.ccbp_global_enable.isChecked():
            return "enable"

    def get_ccpb(self, group):
        if group is None:
            group = []
        elif isinstance(group, str):
            group = [group]
        ccbp = self.get_ccpb_global()
        parent = self.table.invisibleRootItem()
        for g in group:
            new_parent = None
            for i in range(parent.childCount()):
                child = parent.child(i)
                if child.ty == "group" and child.text(0) == g:
                    c_ccbp = self.table.itemWidget(child, 1).text()
                    if c_ccbp:
                        ccbp = c_ccbp
                    new_parent = child
                    break
            if new_parent is None:
                return ccbp
            else:
                parent = new_parent
        return ccbp

    def locate_applet(self, name, group, create_groups):
        if group is None:
            group = []
        elif isinstance(group, str):
            group = [group]

        parent = self.table.invisibleRootItem()
        for g in group:
            new_parent = None
            for i in range(parent.childCount()):
                child = parent.child(i)
                if child.ty == "group" and child.text(0) == g:
                    new_parent = child
                    break
            if new_parent is None:
                if create_groups:
                    new_parent = self.new_group(g, parent)
                else:
                    return None, None
            parent = new_parent

        applet = None
        for i in range(parent.childCount()):
            child = parent.child(i)
            if child.ty == "applet" and child.text(0) == name:
                applet = child
                break
        return parent, applet

    def ccb_create_applet(self, name, command, group=None, code=None):
        ccbp = self.get_ccpb(group)
        if ccbp == "ignore":
            return
        parent, applet = self.locate_applet(name, group, True)
        if code is None:
            spec = {"ty": "command", "command": command}
        else:
            spec = {"ty": "code", "code": code, "command": command}
        if applet is None:
            applet = self.new(name=name, spec=spec, parent=parent)
        else:
            self.set_spec(applet, spec)
        if ccbp == "enable":
            applet.setCheckState(0, QtCore.Qt.Checked)

    def ccb_disable_applet(self, name, group=None):
        ccbp = self.get_ccpb(group)
        if ccbp != "create":
            return
        parent, applet = self.locate_applet(name, group, False)
        if applet is not None:
            applet.setCheckState(0, QtCore.Qt.Unchecked)

    def ccb_notify(self, message):
        try:
            service = message["service"]
            args = message["args"]
            kwargs = message["kwargs"]
            if service == "create_applet":
                self.ccb_create_applet(*args, **kwargs)
            elif service == "disable_applet":
                self.ccb_disable_applet(*args, **kwargs)
        except:
            logger.error("failed to process CCB", exc_info=True)

    def save_state(self):
        return {
            "applets": applets.AppletsDock.save_state(self),
            "ccbp_global": self.get_ccpb_global()
        }

    def restore_state(self, state):
        applets.AppletsDock.restore_state(self, state["applets"])
        getattr(self, "ccbp_global_" + state["ccbp_global"]).setChecked(True)
