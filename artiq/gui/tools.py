from quamash import QtCore


class _DictSyncSubstruct:
    def __init__(self, update_cb, ref):
        self.update_cb = update_cb
        self.ref = ref

    def __getitem__(self, key):
        return _DictSyncSubstruct(self.update_cb, self.ref[key])

    def __setitem__(self, key, value):
        self.ref[key] = value
        self.update_cb()


class DictSyncModel(QtCore.QAbstractTableModel):
    def __init__(self, headers, parent, init):
        self.headers = headers
        self.data = init
        self.row_to_key = sorted(self.data.keys(),
                                 key=lambda k: self.sort_key(k, self.data[k]))
        QtCore.QAbstractTableModel.__init__(self, parent)

    def rowCount(self, parent):
        return len(self.data)

    def columnCount(self, parent):
        return len(self.headers)

    def data(self, index, role):
        if not index.isValid():
            return None
        elif role != QtCore.Qt.DisplayRole:
            return None
        k = self.row_to_key[index.row()]
        return self.convert(k, self.data[k], index.column())

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
                              self.data[self.row_to_key[mid]])
                    < self.sort_key(k, v)):
                lo = mid + 1
            else:
                hi = mid
        return lo

    def __setitem__(self, k, v):
        if k in self.data:
            old_row = self.row_to_key.index(k)
            new_row = self._find_row(k, v)
            if old_row == new_row:
                self.dataChanged.emit(self.index(old_row, 0),
                                      self.index(old_row, len(self.headers)))
            else:
                self.beginMoveRows(QtCore.QModelIndex(), old_row, old_row,
                                   QtCore.QModelIndex(), new_row)
            self.data[k] = v
            self.row_to_key[old_row], self.row_to_key[new_row] = \
                self.row_to_key[new_row], self.row_to_key[old_row]
            if old_row != new_row:
                self.endMoveRows()
        else:
            row = self._find_row(k, v)
            self.beginInsertRows(QtCore.QModelIndex(), row, row)
            self.data[k] = v
            self.row_to_key.insert(row, k)
            self.endInsertRows()

    def __delitem__(self, k):
        row = self.row_to_key.index(k)
        self.beginRemoveRows(QtCore.QModelIndex(), row, row)
        del self.row_to_key[row]
        del self.data[k]
        self.endRemoveRows()

    def __getitem__(self, key):
        def update():
            self[key] = self.data[key]
        return _DictSyncSubstruct(update, self.data[key])

    def sort_key(self, k, v):
        raise NotImplementedError

    def convert(self, k, v, column):
        raise NotImplementedError
