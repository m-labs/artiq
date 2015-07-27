from quamash import QtCore


def force_spinbox_value(spinbox, value):
    if spinbox.minimum() > value:
        spinbox.setMinimum(value)
    if spinbox.maximum() < value:
        spinbox.setMaximum(value)
    spinbox.setValue(value)


def short_format(v):
    t = type(v)
    if t is int or t is float:
        return str(v)
    elif t is str:
        if len(v) < 15:
            return "\"" + v + "\""
        else:
            return "\"" + v[:12] + "\"..."
    else:
        r = t.__name__
        if t is list or t is dict or t is set:
            r += " ({})".format(len(v))
        return r


class _SyncSubstruct:
    def __init__(self, update_cb, ref):
        self.update_cb = update_cb
        self.ref = ref

    def append(self, x):
        self.ref.append(x)
        self.update_cb()

    def insert(self, i, x):
        self.ref.insert(i, x)
        self.update_cb()

    def pop(self, i=-1):
        self.ref.pop(i)
        self.update_cb()

    def __setitem__(self, key, value):
        self.ref[key] = value
        self.update_cb()

    def __delitem__(self, key):
        self.ref.__delitem__(key)
        self.update_cb()

    def __getitem__(self, key):
        return _SyncSubstruct(self.update_cb, self.ref[key])


class DictSyncModel(QtCore.QAbstractTableModel):
    def __init__(self, headers, parent, init):
        self.headers = headers
        self.backing_store = init
        self.row_to_key = sorted(self.backing_store.keys(),
                                 key=lambda k: self.sort_key(k, self.backing_store[k]))
        QtCore.QAbstractTableModel.__init__(self, parent)

    def rowCount(self, parent):
        return len(self.backing_store)

    def columnCount(self, parent):
        return len(self.headers)

    def data(self, index, role):
        if not index.isValid():
            return None
        elif role != QtCore.Qt.DisplayRole:
            return None
        k = self.row_to_key[index.row()]
        return self.convert(k, self.backing_store[k], index.column())

    def headerData(self, col, orientation, role):
        if (orientation == QtCore.Qt.Horizontal
                and role == QtCore.Qt.DisplayRole):
            return self.headers[col]
        return None

    def _find_row(self, k, v):
        lo = 0
        hi = len(self.row_to_key)
        while lo < hi:
            mid = (lo + hi)//2
            if (self.sort_key(self.row_to_key[mid],
                              self.backing_store[self.row_to_key[mid]])
                    < self.sort_key(k, v)):
                lo = mid + 1
            else:
                hi = mid
        return lo

    def __setitem__(self, k, v):
        if k in self.backing_store:
            old_row = self.row_to_key.index(k)
            new_row = self._find_row(k, v)
            if old_row == new_row:
                self.dataChanged.emit(self.index(old_row, 0),
                                      self.index(old_row, len(self.headers)))
            else:
                self.beginMoveRows(QtCore.QModelIndex(), old_row, old_row,
                                   QtCore.QModelIndex(), new_row)
            self.backing_store[k] = v
            self.row_to_key[old_row], self.row_to_key[new_row] = \
                self.row_to_key[new_row], self.row_to_key[old_row]
            if old_row != new_row:
                self.endMoveRows()
        else:
            row = self._find_row(k, v)
            self.beginInsertRows(QtCore.QModelIndex(), row, row)
            self.backing_store[k] = v
            self.row_to_key.insert(row, k)
            self.endInsertRows()

    def __delitem__(self, k):
        row = self.row_to_key.index(k)
        self.beginRemoveRows(QtCore.QModelIndex(), row, row)
        del self.row_to_key[row]
        del self.backing_store[k]
        self.endRemoveRows()

    def __getitem__(self, k):
        def update():
            self[k] = self.backing_store[k]
        return _SyncSubstruct(update, self.backing_store[k])

    def sort_key(self, k, v):
        raise NotImplementedError

    def convert(self, k, v, column):
        raise NotImplementedError


class ListSyncModel(QtCore.QAbstractTableModel):
    def __init__(self, headers, parent, init):
        self.headers = headers
        self.backing_store = init
        QtCore.QAbstractTableModel.__init__(self, parent)

    def rowCount(self, parent):
        return len(self.backing_store)

    def columnCount(self, parent):
        return len(self.headers)

    def data(self, index, role):
        if not index.isValid():
            return None
        elif role != QtCore.Qt.DisplayRole:
            return None
        return self.convert(self.backing_store[index.row()], index.column())

    def headerData(self, col, orientation, role):
        if (orientation == QtCore.Qt.Horizontal
                and role == QtCore.Qt.DisplayRole):
            return self.headers[col]
        return None

    def __setitem__(self, k, v):
        self.dataChanged.emit(self.index(k, 0),
                              self.index(k, len(self.headers)))
        self.backing_store[k] = v

    def __delitem__(self, k):
        self.beginRemoveRows(QtCore.QModelIndex(), k, k)
        del self.backing_store[k]
        self.endRemoveRows()

    def __getitem__(self, k):
        def update():
            self[k] = self.backing_store[k]
        return _SyncSubstruct(update, self.backing_store[k])

    def append(self, v):
        row = len(self.backing_store)
        self.beginInsertRows(QtCore.QModelIndex(), row, row)
        self.backing_store.append(v)
        self.endInsertRows()

    def convert(self, v, column):
        raise NotImplementedError
