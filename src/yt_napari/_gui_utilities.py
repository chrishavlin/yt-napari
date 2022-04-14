import warnings
from collections import defaultdict
from typing import Callable, Optional, Tuple, Union

import pydantic
from magicgui import type_map, widgets

from yt_napari import _data_model


def add_pydantic_to_container(
    py_model: Union[pydantic.BaseModel, pydantic.main.ModelMetaclass],
    container: widgets.Container,
):
    # recursively traverse a pydantic model adding widgets to a container. When a nested
    # pydantic model is encountered, add a new nested container
    for field, field_def in py_model.__fields__.items():
        ftype = field_def.type_
        if isinstance(ftype, pydantic.BaseModel) or isinstance(
            ftype, pydantic.main.ModelMetaclass
        ):
            # the field is a pydantic class, add a container for it and fill it
            new_widget_cls = widgets.Container
            new_widget = new_widget_cls(name=field_def.name)
            add_pydantic_to_container(ftype, new_widget)
        elif translator.is_registered(py_model, field):
            new_widget = translator.get_widget_instance(py_model, field)
        else:
            # use a magicgui default
            new_widget_cls, ops = type_map.get_widget_class(
                None, ftype, dict(name=field_def.name, value=field_def.default)
            )
            new_widget = new_widget_cls(**ops)
            if isinstance(new_widget, widgets.EmptyWidget):
                msg = "magicgui could not identify a widget for "
                msg += f" {py_model}.{field}, which has type {ftype}"
                warnings.warn(message=msg)
        container.append(new_widget)


def get_pydantic_kwargs(container: widgets.Container, py_model, pydantic_kwargs: dict):
    # given a container that was instantiated from a pydantic model, get the arguments
    # needed to instantiate that pydantic model from the container.

    # traverse model fields, pull out values from container
    for field, field_def in py_model.__fields__.items():
        ftype = field_def.type_
        if isinstance(ftype, pydantic.BaseModel) or isinstance(
            ftype, pydantic.main.ModelMetaclass
        ):
            new_kwargs = {}  # new dictionary for the new nest level
            # any pydantic class will be a container, so pull that out to pass
            # to the recursive call
            sub_container = getattr(container, field_def.name)
            get_pydantic_kwargs(sub_container, ftype, new_kwargs)
            if "typing.List" in str(field_def.outer_type_):
                new_kwargs = [
                    new_kwargs,
                ]
            pydantic_kwargs[field] = new_kwargs

        elif translator.is_registered(py_model, field):
            widget_instance = getattr(container, field_def.name)  # pull from container
            pydantic_kwargs[field] = translator.get_pydantic_attr(
                py_model, field, widget_instance
            )
        else:
            # not a pydantic class, just pull the field value from the container
            if hasattr(container, field_def.name):
                value = getattr(container, field_def.name).value
                pydantic_kwargs[field] = value


def set_default(variable, default):
    if variable is None:
        return default
    return variable


class MagicPydanticRegistry:

    registry = defaultdict(dict)

    def register(
        self,
        pydantic_model: Union[pydantic.BaseModel, pydantic.main.ModelMetaclass],
        field: str,
        magicgui_factory: Callable = None,
        magicgui_args: Optional[tuple] = None,
        magicgui_kwargs: Optional[dict] = None,
        pydantic_attr_factory: Callable = None,
        pydantic_attr_args: Optional[tuple] = None,
        pydantic_attr_kwargs: Optional[dict] = None,
    ):
        """

        Parameters
        ----------
        pydantic_model :
            the pydantic model to register
        field :
            the attribute from the pydantic model to register
        magicgui_factory :
            a callable function that must return a magicgui widget
        magicgui_args :
            a tuple containing arguments to magicgui_factory
        magicgui_kwargs :
            a dict containing keyword arguments to magicgui_factory
        pydantic_attr_factory :
            a function that takes a magicgui widget instance and returns the
            arguments for a pydantic attribute
        pydantic_attr_args :
            a tuple containing arguments to pydantic_attr_factory
        pydantic_attr_kwargs :
            a dict containing keyword arguments to pydantic_attr_factory
        """
        magicgui_args = set_default(magicgui_args, ())
        magicgui_kwargs = set_default(magicgui_kwargs, {})
        pydantic_attr_args = set_default(pydantic_attr_args, ())
        pydantic_attr_kwargs = set_default(pydantic_attr_kwargs, {})

        self.registry[pydantic_model][field] = {}
        new_entry = {
            "magicgui": (magicgui_factory, magicgui_args, magicgui_kwargs),
            "pydantic": (
                pydantic_attr_factory,
                pydantic_attr_args,
                pydantic_attr_kwargs,
            ),
        }

        self.registry[pydantic_model][field] = new_entry

    def is_registered(self, pydantic_model, field: str, required: bool = False):
        # check if a pydantic model and field is registered, will error if required=True

        in_registry = False
        model_exists = False
        if pydantic_model in self.registry:
            model_exists = True
            in_registry = field in self.registry[pydantic_model]

        if required:
            if model_exists is False:
                raise KeyError(f"registry does not contain {pydantic_model}.")
            elif in_registry is False:
                raise KeyError(f"{pydantic_model} registry does not contain {field}.")

        return in_registry

    def get_widget_instance(self, pydantic_model, field: str):
        # return a widget instance for a given pydantic model and field
        if self.is_registered(pydantic_model, field, required=True):
            func, args, kwargs = self.registry[pydantic_model][field]["magicgui"]
            return func(*args, **kwargs)

    def get_pydantic_attr(self, pydantic_model, field: str, widget_instance):
        # given a widget instance, return an object that can be used to set a
        # pydantic field
        if self.is_registered(pydantic_model, field, required=True):
            func, args, kwargs = self.registry[pydantic_model][field]["pydantic"]
            return func(widget_instance, *args, **kwargs)


translator = MagicPydanticRegistry()

# register some data model fields:


def get_file_widget(*args, **kwargs):
    return widgets.FileEdit(*args, **kwargs)


def get_filename(file_widget: widgets.FileEdit):
    return str(file_widget.value)


translator.register(
    _data_model.DataContainer,
    "filename",
    magicgui_factory=get_file_widget,
    magicgui_kwargs={"name": "filename"},
    pydantic_attr_factory=get_filename,
)


def create_vector_widget(
    *args,
    length: int = 3,
    box_type=float,
    default_values: Optional[Tuple] = None,
    **kwargs,
):
    if box_type is float:
        BoxType = widgets.FloatSpinBox
    else:
        BoxType = widgets.SpinBox
    if default_values is None:
        default_values = [
            0,
        ] * length
    widg_list = [
        BoxType(label=" ", name=f"x_{i}", value=default_values[i])
        for i in range(length)
    ]
    return widgets.Container(*args, layout="horizontal", widgets=widg_list, **kwargs)


def get_vector_kwargs(vector_widget_instance):
    return tuple(i.value for i in vector_widget_instance)


for edge, box_type in zip(
    ("left_edge", "right_edge", "resolution"), (float, float, int)
):
    defs = _data_model.SelectionObject.__fields__[edge].default
    translator.register(
        _data_model.SelectionObject,
        edge,
        magicgui_factory=create_vector_widget,
        magicgui_kwargs={
            "length": 3,
            "name": edge,
            "default_values": defs,
            "box_type": box_type,
        },
        pydantic_attr_factory=get_vector_kwargs,
    )


def get_magicguidefault(field_def: pydantic.fields.ModelField):
    ftype = field_def.type_
    new_widget_cls, ops = type_map.get_widget_class(
        None, ftype, dict(name=field_def.name, value=field_def.default)
    )
    return new_widget_cls(**ops)


def embed_in_list(default_widget_instance):
    returnval = [
        default_widget_instance.value,
    ]
    return returnval


py_model, field = _data_model.SelectionObject, "fields"
translator.register(
    py_model,
    field,
    magicgui_factory=get_magicguidefault,
    magicgui_args=(py_model.__fields__[field]),
    pydantic_attr_factory=embed_in_list,
)

py_model, field = _data_model.DataContainer, "selections"
translator.register(
    py_model,
    field,
    magicgui_factory=get_magicguidefault,
    magicgui_args=(py_model.__fields__[field]),
    pydantic_attr_factory=embed_in_list,
)


data_container = widgets.Container()
add_pydantic_to_container(_data_model.DataContainer, data_container)
