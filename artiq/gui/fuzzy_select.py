import re

from functools import partial
from typing import List, Tuple
from PyQt5 import QtCore, QtWidgets

from artiq.gui.tools import LayoutWidget


class FuzzySelectWidget(LayoutWidget):
    """Widget to select from a list of pre-defined choices by typing in a
    substring match (cf. Ctrl+P "Quick Open"/"Goto anything" functions in
    editors/IDEs).
    """

    #: Raised when the selection process is aborted by the user (Esc, loss of
    #: focus, etc.).
    aborted = QtCore.pyqtSignal()

    #: Raised when an entry has been selected, giving the label of the user
    #: choice and any additional QEvent.modifiers() (e.g. Ctrl key pressed).
    finished = QtCore.pyqtSignal(str, int)

    def __init__(self,
                 choices: List[Tuple[str, int]] = [],
                 entry_count_limit: int = 10,
                 *args):
        """
        :param choices: The choices the user can select from, given as tuples
            of labels to display and an additional weight added to the
            fuzzy-matching score.
        :param entry_count_limit: Maximum number of entries to show.
        """
        super().__init__(*args)
        self.entry_count_limit = entry_count_limit
        assert entry_count_limit >= 2, ("Need to allow at least two entries " +
                                        "to show the '<n> not shown' hint")

        self.line_edit = QtWidgets.QLineEdit(self)
        self.layout.addWidget(self.line_edit)

        line_edit_focus_filter = _FocusEventFilter(self.line_edit)
        line_edit_focus_filter.focus_gained.connect(self._activate)
        line_edit_focus_filter.focus_lost.connect(self._line_edit_focus_lost)
        self.line_edit.installEventFilter(line_edit_focus_filter)
        self.line_edit.textChanged.connect(self._update_menu)

        escape_filter = _EscapeKeyFilter(self)
        escape_filter.escape_pressed.connect(self.abort)
        self.line_edit.installEventFilter(escape_filter)

        self.menu = None

        self.update_when_text_changed = True
        self.menu_typing_filter = None
        self.line_edit_up_down_filter = None
        self.abort_when_menu_hidden = False
        self.abort_when_line_edit_unfocussed = True

        self.set_choices(choices)

    def set_choices(self, choices: List[Tuple[str, int]]) -> None:
        """Update the list of choices available to the user."""
        # Keep sorted in the right order for when the query is empty.
        self.choices = sorted(choices, key=lambda a: (a[1], a[0]))
        if self.menu:
            self._update_menu()

    def resizeEvent(self, ev):
        # Reposition menu once widget position and layout are known. Qt triggers a
        # resizeEvent then. (This is relevant for the Quick Open dialog on KDE/Linux,
        # which sometimes shows at (0, 0) instead because the layout wasn't ready yet.)
        if self.menu:
            self._popup_menu()
        return super().resizeEvent(ev)

    def _activate(self):
        self.update_when_text_changed = True
        if not self.menu:
            self._update_menu()

    def _popup_menu(self):
        # Display menu with search results beneath line edit.
        menu_pos = self.line_edit.mapToGlobal(self.line_edit.pos())
        menu_pos.setY(menu_pos.y() + self.line_edit.height())
        self.menu.popup(menu_pos)

    def _ensure_menu(self):
        if self.menu:
            return
        self.menu = QtWidgets.QMenu(self)
        self._popup_menu()
        self.menu.aboutToHide.connect(self._menu_hidden)

    def _menu_hidden(self):
        if self.abort_when_menu_hidden:
            self.abort_when_menu_hidden = False
            self.abort()

    def _line_edit_focus_lost(self):
        if self.abort_when_line_edit_unfocussed:
            self.abort()

    def _update_menu(self):
        if not self.update_when_text_changed:
            return

        filtered_choices = self._filter_choices()

        if not filtered_choices:
            # No matches, don't display menu at all.
            if self.menu:
                self.abort_when_menu_hidden = False
                self.menu.close()
            self.menu = None
            self.abort_when_line_edit_unfocussed = True
            self.line_edit.setFocus()
            return

        # Truncate the list, leaving room for the "<n> not shown" entry.
        num_omitted = 0
        if len(filtered_choices) > self.entry_count_limit:
            num_omitted = len(filtered_choices) - (self.entry_count_limit - 1)
            filtered_choices = filtered_choices[:self.entry_count_limit - 1]

        # We are going to end up with a menu shown and the line edit losing
        # focus.
        self.abort_when_line_edit_unfocussed = False

        if self.menu:
            # Hide menu temporarily to avoid re-layouting on every added item.
            self.abort_when_menu_hidden = False
            self.menu.hide()
            self.menu.clear()

        self._ensure_menu()

        first_action = None
        last_action = None
        for choice in filtered_choices:
            action = QtWidgets.QAction(choice, self.menu)
            action.triggered.connect(partial(self._finish, action, choice))
            action.modifiers = 0
            self.menu.addAction(action)
            if not first_action:
                first_action = action
            last_action = action

        if num_omitted > 0:
            action = QtWidgets.QAction("<{} not shown>".format(num_omitted),
                                       self.menu)
            action.setEnabled(False)
            self.menu.addAction(action)

        if self.menu_typing_filter:
            self.menu.removeEventFilter(self.menu_typing_filter)
        self.menu_typing_filter = _NonUpDownKeyFilter(self.menu,
                                                      self.line_edit)
        self.menu.installEventFilter(self.menu_typing_filter)

        if self.line_edit_up_down_filter:
            self.line_edit.removeEventFilter(self.line_edit_up_down_filter)
        self.line_edit_up_down_filter = _UpDownKeyFilter(
            self.line_edit, self.menu, first_action, last_action)
        self.line_edit.installEventFilter(self.line_edit_up_down_filter)

        self.abort_when_menu_hidden = True
        self.menu.show()
        if first_action:
            self.menu.setActiveAction(first_action)
            self.menu.setFocus()
        else:
            self.line_edit.setFocus()

    def _filter_choices(self):
        """Return a filtered and ranked list of choices based on the current
        user input.
        
        For a choice not to be filtered out, it needs to contain the entered
        characters in order. Entries are further sorted by the length of the
        match (i.e. preferring matches where the entered string occurrs
        without interruptions), then the position of the match, and finally
        lexicographically.
        """
        query = self.line_edit.text()
        if not query:
            return [label for label, _ in self.choices]

        # Find all "substring" matches of the given query in the labels,
        # allowing any number of characters between each query character.
        # Sort first by length of match (short matches preferred), to which the
        # set weight is also applied, then by location (early in the label
        # preferred), and at last alphabetically.

        # TODO: More SublimeText-like heuristics taking capital letters and
        # punctuation into account. Also, requiring the matches to be in order
        # seems to be a bit annoying in practice.

        # `re` seems to be the fastest way of doing this in CPython, even with
        # all the (non-greedy) wildcards.
        suggestions = []
        pattern_str = ".*?".join(map(re.escape, query))
        pattern = re.compile(pattern_str, flags=re.IGNORECASE)
        for label, weight in self.choices:
            matches = []
            # Manually loop over shortest matches at each position;
            # re.finditer() only returns non-overlapping matches.
            pos = 0
            while True:
                r = pattern.search(label, pos=pos)
                if not r:
                    break
                start, stop = r.span()
                matches.append((stop - start - weight, start, label))
                pos = start + 1
            if matches:
                suggestions.append(min(matches))
        return [x for _, _, x in sorted(suggestions)]

    def _close(self):
        if self.menu:
            self.menu.close()
            self.menu = None
        self.update_when_text_changed = False
        self.line_edit.clear()

    def abort(self):
        self._close()
        self.aborted.emit()

    def _finish(self, action, name):
        self._close()
        self.finished.emit(name, action.modifiers)


class _FocusEventFilter(QtCore.QObject):
    """Emits signals when focus is gained/lost."""
    focus_gained = QtCore.pyqtSignal()
    focus_lost = QtCore.pyqtSignal()

    def eventFilter(self, obj, event):
        if event.type() == QtCore.QEvent.FocusIn:
            self.focus_gained.emit()
        elif event.type() == QtCore.QEvent.FocusOut:
            self.focus_lost.emit()
        return False


class _EscapeKeyFilter(QtCore.QObject):
    """Emits a signal if the Escape key is pressed."""
    escape_pressed = QtCore.pyqtSignal()

    def eventFilter(self, obj, event):
        if event.type() == QtCore.QEvent.KeyPress:
            if event.key() == QtCore.Qt.Key_Escape:
                self.escape_pressed.emit()
        return False


class _UpDownKeyFilter(QtCore.QObject):
    """Handles focussing the menu when pressing up/down in the line edit."""
    def __init__(self, parent, menu, first_item, last_item):
        super().__init__(parent)
        self.menu = menu
        self.first_item = first_item
        self.last_item = last_item

    def eventFilter(self, obj, event):
        if event.type() == QtCore.QEvent.KeyPress:
            if event.key() == QtCore.Qt.Key_Down:
                self.menu.setActiveAction(self.first_item)
                self.menu.setFocus()
                return True

            if event.key() == QtCore.Qt.Key_Up:
                self.menu.setActiveAction(self.last_item)
                self.menu.setFocus()
                return True
        return False


class _NonUpDownKeyFilter(QtCore.QObject):
    """Forwards input while the menu is focussed to the line edit."""
    def __init__(self, parent, target):
        super().__init__(parent)
        self.target = target

    def eventFilter(self, obj, event):
        if event.type() == QtCore.QEvent.KeyPress:
            k = event.key()
            if k in (QtCore.Qt.Key_Return, QtCore.Qt.Key_Enter):
                action = obj.activeAction()
                if action is not None:
                    action.modifiers = event.modifiers()
                    return False
            if (k != QtCore.Qt.Key_Down and k != QtCore.Qt.Key_Up
                    and k != QtCore.Qt.Key_Enter
                    and k != QtCore.Qt.Key_Return):
                QtWidgets.QApplication.sendEvent(self.target, event)
                return True
        return False
