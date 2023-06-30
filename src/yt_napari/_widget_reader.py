from typing import Callable, Optional

import napari
from magicgui import widgets
from qtpy import QtCore
from qtpy.QtWidgets import QComboBox, QHBoxLayout, QPushButton, QVBoxLayout, QWidget

from yt_napari import _data_model, _gui_utilities, _model_ingestor
from yt_napari._ds_cache import dataset_cache
from yt_napari.viewer import Scene


class ReaderWidget(QWidget):
    def __init__(self, napari_viewer: "napari.viewer.Viewer", parent=None):
        super().__init__(parent)
        self.setLayout(QVBoxLayout())
        self.viewer = napari_viewer

        ds_container = _gui_utilities.get_yt_data_container(ignore_attrs="selections")
        self.layout().addWidget(ds_container.native)

        # click button to add layer
        addition_group_layout = QHBoxLayout()
        add_new_button = widgets.PushButton(text="Click to add new selection")
        add_new_button.clicked.connect(self.add_a_selection)
        addition_group_layout.addWidget(add_new_button.native)

        new_selection_type = QComboBox()
        new_selection_type.insertItems(0, _gui_utilities._valid_selections)
        self.new_selection_type = new_selection_type
        addition_group_layout.addWidget(self.new_selection_type)
        self.layout().addLayout(addition_group_layout)

        # the active selections, populated by add_a_selection
        self.active_selections = {}
        self.active_selection_layout = QVBoxLayout()
        self.layout().addLayout(self.active_selection_layout)

        # removing selections
        removal_group_layout = QHBoxLayout()

        rm_sel = widgets.PushButton(text="Delete Selection")
        rm_sel.clicked.connect(self.remove_selection)
        removal_group_layout.addWidget(rm_sel.native)

        active_sel_list = QComboBox()
        active_sel_list.insertItems(0, list(self.active_selections.keys()))
        self.active_sel_list = active_sel_list
        removal_group_layout.addWidget(active_sel_list)

        self.layout().addLayout(removal_group_layout)

        # the load and clear buttons
        load_group = QHBoxLayout()
        self._post_load_function: Optional[Callable] = None
        pb = widgets.PushButton(text="Load Selections")
        pb.clicked.connect(self.load_data)
        load_group.addWidget(pb.native)

        cc = widgets.PushButton(text="Clear cache")
        cc.clicked.connect(self.clear_cache)
        load_group.addWidget(cc.native)
        self.layout().addLayout(load_group)

    def add_a_selection(self):
        selection_type = self.new_selection_type.currentText()
        widg_id = len(self.active_selections) + 1
        widget_name = f"Selection {widg_id}, {selection_type}"
        widg_key = f"{selection_type}_{widg_id}"
        new_selection_widget = SelectionEntry(widget_name, selection_type)
        self.active_selections[widg_key] = new_selection_widget
        self.active_selection_layout.addWidget(self.active_selections[widg_key])
        self.active_sel_list.insertItem(widg_id - 1, widg_key.replace("_", " "))

    def remove_selection(self):
        widget_to_rm = self.active_sel_list.currentText().replace(" ", "_")
        if widget_to_rm is not None and widget_to_rm in self.active_selections:
            self.layout().removeWidget(self.active_selections[widget_to_rm])
            self.active_selections.pop(widget_to_rm)
            self.active_sel_list.clear()
            self.active_sel_list.insertItems(0, list(self.active_selections.keys()))

    _yt_scene: Scene = None  # will persist across widget calls

    @property
    def yt_scene(self):
        if self._yt_scene is None:
            self._yt_scene = Scene()
        return self._yt_scene

    def clear_cache(self):
        dataset_cache.rm_all()

    def load_data(self):
        # first extract all the pydantic arguments from the container
        py_kwargs = {}
        _gui_utilities.translator.get_pydantic_kwargs(
            self.data_container, _data_model.DataContainer, py_kwargs
        )
        # instantiate the base model
        py_kwargs = {
            "data": [
                py_kwargs,
            ]
        }
        model = _data_model.InputModel.parse_obj(py_kwargs)
        # process it!
        layer_list = _model_ingestor._process_validated_model(model)

        # get the reference layer, align the current new layer
        layer_domain = layer_list[0][3]
        ref_layer = self.yt_scene._get_reference_layer(
            self.viewer.layers, default_if_missing=layer_domain
        )
        data, im_kwargs, _ = ref_layer.align_sanitize_layer(layer_list[0])

        if self._post_load_function is not None:
            data = self._post_load_function(data)

        # set the metadata
        take_log = model.data[0].selections.regions[0].fields[0].take_log
        md = _model_ingestor.create_metadata_dict(
            data, layer_domain, take_log, reference_layer=ref_layer
        )
        im_kwargs["metadata"] = md

        # add the new layer
        self.viewer.add_image(data, **im_kwargs)


class SelectionEntry(QWidget):
    """
    LayerList class which acts as collapsable list.
    """

    def __init__(self, name, selection_type: str, expand: bool = True):
        super().__init__()
        self.currently_expanded = True
        self.main_layout = QVBoxLayout()
        self.main_layout.setSpacing(0)
        self.main_layout.setContentsMargins(0, 0, 0, 0)

        self.expand_button = QPushButton(f"Selection {name}")
        self.expand_button.setToolTip(f"show/hide {name}")

        self.selection_container = _gui_utilities.get_yt_selection_container(
            selection_type, return_native=True
        )

        # self.container_model = QStandardItemModel()
        # self.layer_list.setModel(self.container_model)
        # self.layer_list.setEditTriggers(QAbstractItemView.NoEditTriggers)

        self.main_layout.addWidget(self.expand_button)
        self.main_layout.addWidget(self.selection_container)
        self.expand_button.clicked.connect(self.expand)
        self.setLayout(self.main_layout)
        self.resized_size = 16.5 * 1
        if not expand:
            self.expand()

    @QtCore.Slot()
    def expand(self):
        if self.currently_expanded:
            self.selection_container.hide()
            self.currently_expanded = False
        else:
            self.selection_container.show()
            self.currently_expanded = True
