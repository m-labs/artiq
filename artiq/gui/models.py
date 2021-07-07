from PyQt5 import QtCore

from sipyco.sync_struct import Subscriber, process_mod


class ModelManager:
    def __init__(self, model_factory):
        self.model = None
        self._model_factory = model_factory
        self._setmodel_callbacks = []

    def _create_model(self, init):
        self.model = self._model_factory(init)
        for cb in self._setmodel_callbacks:
            cb(self.model)
        return self.model

    def add_setmodel_callback(self, cb):
        self._setmodel_callbacks.append(cb)
        if self.model is not None:
            cb(self.model)


class ModelSubscriber(ModelManager, Subscriber):
    def __init__(self, notifier_name, model_factory,
                 disconnect_cb=None):
        ModelManager.__init__(self, model_factory)
        Subscriber.__init__(self, notifier_name, self._create_model,
                            disconnect_cb=disconnect_cb)


class LocalModelManager(ModelManager):
    def __init__(self, model_factory):
        ModelManager.__init__(self, model_factory)
        self.notify_cbs = []

    def update(self, mod):
        process_mod(self.model, mod)
        for notify_cb in self.notify_cbs:
            notify_cb(mod)

    def init(self, struct):
        self._create_model(struct)
        mod = {"action": "init", "struct": struct}
        for notify_cb in self.notify_cbs:
            notify_cb(mod)


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
    def __init__(self, headers, init):
        self.headers = headers
        self.backing_store = init
        self.row_to_key = sorted(
            self.backing_store.keys(),
            key=lambda k: self.sort_key(k, self.backing_store[k]))
        QtCore.QAbstractTableModel.__init__(self)

    def rowCount(self, parent):
        return len(self.backing_store)

    def columnCount(self, parent):
        return len(self.headers)

    def data(self, index, role):
        if not index.isValid() or role != QtCore.Qt.DisplayRole:
            return None
        else:
            k = self.row_to_key[index.row()]
            return self.convert(k, self.backing_store[k], index.column())

    def headerData(self, col, orientation, role):
        if (orientation == QtCore.Qt.Horizontal and
                role == QtCore.Qt.DisplayRole):
            return self.headers[col]
        return None

    def _find_row(self, k, v):
        lo = 0
        hi = len(self.row_to_key)
        while lo < hi:
            mid = (lo + hi)//2
            if (self.sort_key(self.row_to_key[mid],
                              self.backing_store[self.row_to_key[mid]]) <
                    self.sort_key(k, v)):
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
                                      self.index(old_row, len(self.headers)-1))
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
    def __init__(self, headers, init):
        self.headers = headers
        self.backing_store = init
        QtCore.QAbstractTableModel.__init__(self)

    def rowCount(self, parent):
        return len(self.backing_store)

    def columnCount(self, parent):
        return len(self.headers)

    def data(self, index, role):
        if not index.isValid() or role != QtCore.Qt.DisplayRole:
            return None
        else:
            return self.convert(self.backing_store[index.row()],
                                index.column())

    def headerData(self, col, orientation, role):
        if (orientation == QtCore.Qt.Horizontal and
                role == QtCore.Qt.DisplayRole):
            return self.headers[col]
        return None

    def __setitem__(self, k, v):
        self.dataChanged.emit(self.index(k, 0),
                              self.index(k, len(self.headers)-1))
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


# An item is a node if it has children, a leaf if it does not.
# There can be a node and a leaf with the same name and different
# rows, e.g. foo/bar and foo.
class _DictSyncTreeSepItem:
    def __init__(self, parent, row, name):
        self.parent = parent
        self.row = row
        self.name = name
        self.children_by_row = []
        self.children_nodes_by_name = dict()
        self.children_leaves_by_name = dict()
        # is_node is permanently set when a child is added.
        # This must be done instead of checking for the emptiness of
        # children_by_row: in the middle of deletion operations, we remove
        # items from children_by_row, and briefly turn nodes into leaves
        # before they are removed.
        # Of course, Qt sometimes happily calls data() on those invalid leaves,
        # resulting in convert() being called for an invalid key if we hadn't
        # permanently marked those items as nodes.
        self.is_node = False

    def __repr__(self):
        return ("<DictSyncTreeSepItem {}, row={}, nchildren={}>".
                format(self.name, self.row, len(self.children_by_row)))


def _bisect_item(a, name):
    lo = 0
    hi = len(a)
    while lo < hi:
        mid = (lo + hi)//2
        if name < a[mid].name:
            hi = mid
        else:
            lo = mid + 1
    return lo


class DictSyncTreeSepModel(QtCore.QAbstractItemModel):
    def __init__(self, separator, headers, init):
        QtCore.QAbstractItemModel.__init__(self)

        self.separator = separator
        self.headers = headers

        self.backing_store = dict()
        self.children_by_row = []
        self.children_nodes_by_name = dict()
        self.children_leaves_by_name = dict()

        for k, v in init.items():
            self[k] = v

    def rowCount(self, parent):
        if parent.isValid():
            item = parent.internalPointer()
            return len(item.children_by_row)
        else:
            return len(self.children_by_row)

    def columnCount(self, parent):
        return len(self.headers)

    def headerData(self, col, orientation, role):
        if (orientation == QtCore.Qt.Horizontal and
                role == QtCore.Qt.DisplayRole):
            return self.headers[col]
        return None

    def index(self, row, column, parent):
        if column >= len(self.headers):
            return QtCore.QModelIndex()
        if parent.isValid():
            parent_item = parent.internalPointer()
            try:
                child = parent_item.children_by_row[row]
            except IndexError:
                # This can happen when the last row is selected
                # and then deleted; Qt will attempt to select
                # the non-existent next one.
                return QtCore.QModelIndex()
            return self.createIndex(row, column, child)
        else:
            try:
                child = self.children_by_row[row]
            except IndexError:
                return QtCore.QModelIndex()
            return self.createIndex(row, column, child)

    def _index_item(self, item):
        if item is self:
            return QtCore.QModelIndex()
        else:
            return self.createIndex(item.row, 0, item)

    def parent(self, index):
        if index.isValid():
            return self._index_item(index.internalPointer().parent)
        else:
            return QtCore.QModelIndex()

    def _add_item(self, parent, name, leaf):
        if leaf:
            name_dict = parent.children_leaves_by_name
        else:
            name_dict = parent.children_nodes_by_name

        if name in name_dict:
            return name_dict[name]
        row = _bisect_item(parent.children_by_row, name)
        item = _DictSyncTreeSepItem(parent, row, name)

        self.beginInsertRows(self._index_item(parent), row, row)
        parent.is_node = True
        parent.children_by_row.insert(row, item)
        for next_item in parent.children_by_row[row+1:]:
            next_item.row += 1
        name_dict[name] = item
        self.endInsertRows()

        return item

    def __setitem__(self, k, v):
        *node_names, leaf_name = k.split(self.separator)
        if k in self.backing_store:
            parent = self
            for node_name in node_names:
                parent = parent.children_nodes_by_name[node_name]
            item = parent.children_leaves_by_name[leaf_name]
            index0 = self.createIndex(item.row, 0, item)
            index1 = self.createIndex(item.row, len(self.headers)-1, item)
            self.backing_store[k] = v
            self.dataChanged.emit(index0, index1)
        else:
            self.backing_store[k] = v
            parent = self
            for node_name in node_names:
                parent = self._add_item(parent, node_name, False)
            self._add_item(parent, leaf_name, True)

    def _del_item(self, parent, path):
        if len(path) == 1:
            # leaf
            name = path[0]
            item = parent.children_leaves_by_name[name]
            row = item.row
            self.beginRemoveRows(self._index_item(parent), row, row)
            del parent.children_leaves_by_name[name]
            del parent.children_by_row[row]
            for next_item in parent.children_by_row[row:]:
                next_item.row -= 1
            self.endRemoveRows()
        else:
            # node
            name, *rest = path
            item = parent.children_nodes_by_name[name]
            self._del_item(item, rest)
            if not item.children_by_row:
                row = item.row
                self.beginRemoveRows(self._index_item(parent), row, row)
                del parent.children_nodes_by_name[name]
                del parent.children_by_row[row]
                for next_item in parent.children_by_row[row:]:
                    next_item.row -= 1
                self.endRemoveRows()

    def __delitem__(self, k):
        self._del_item(self, k.split(self.separator))
        del self.backing_store[k]

    def __getitem__(self, k):
        def update():
            self[k] = self.backing_store[k]
        return _SyncSubstruct(update, self.backing_store[k])

    def index_to_key(self, index):
        item = index.internalPointer()
        if item.is_node:
            return None
        key = item.name
        item = item.parent
        while item is not self:
            key = item.name + self.separator + key
            item = item.parent
        return key

    def data(self, index, role):
        if not index.isValid() or (role != QtCore.Qt.DisplayRole
                                   and role != QtCore.Qt.ToolTipRole):
            return None
        else:
            column = index.column()
            if column == 0 and role == QtCore.Qt.DisplayRole:
                return index.internalPointer().name
            else:
                key = self.index_to_key(index)
                if key is None:
                    return None
                else:
                    if role == QtCore.Qt.DisplayRole:
                        convert = self.convert
                    else:
                        convert = self.convert_tooltip
                    return convert(key, self.backing_store[key],
                                   column)

    def convert(self, k, v, column):
        raise NotImplementedError

    def convert_tooltip(self, k, v, column):
        return None
