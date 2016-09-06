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
        self.listen_action = QtWidgets.QAction(
            "Listen to client control broadcasts", self.table)
        self.listen_action.setCheckable(True)
        self.table.addAction(self.listen_action)

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
                if child.ty == "group" and child.text(1) == g:
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
            if child.ty == "applet" and child.text(1) == name:
                applet = child
                break
        return parent, applet

    def ccb_create_applet(self, name, command_or_code, group=None, is_code=False):
        if not self.listen_action.isChecked():
            return
        parent, applet = self.locate_applet(name, group, True)
        if is_code:
            spec = {"ty": "code", "code": command_or_code}
        else:
            spec = {"ty": "command", "command": command_or_code}
        if applet is None:
            applet = self.new(name=name, spec=spec, parent=parent)
        else:
            self.set_spec(applet, spec)
        applet.setCheckState(0, QtCore.Qt.Checked)

    def ccb_disable_applet(self, name, group=None):
        if not self.listen_action.isChecked():
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
            "listen": self.listen_action.isChecked()
        }

    def restore_state(self, state):
        applets.AppletsDock.restore_state(self, state["applets"])
        self.listen_action.setChecked(state["listen"])
