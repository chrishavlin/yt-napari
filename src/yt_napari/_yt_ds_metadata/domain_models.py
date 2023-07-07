from typing import Tuple

from pydantic import BaseModel
from yt.geometry.grid_geometry_handler import GridIndex
from yt.geometry.particle_geometry_handler import ParticleIndex


class GenericDataset:
    ds_attrs: Tuple[str] = (
        "domain_left_edge",
        "domain_right_edge",
        "current_time",
        "domain_dimensions",
        "coordinates.name",
        "parameters",  # big and ugly, long dict of scalar/array vals
    )

    def __init__(self, ds):
        if GridIndex in ds._index_class.__bases__:
            self.index = GridIndex
        elif ParticleIndex in ds._index_class.__bases__:
            self.index = ParticleIndex
        else:
            self.index = None


class CosmologicalDataset(GenericDataset):
    extra_ds_attrs: Tuple[str] = ("cosmological_simulation",)  # add the others


class PhysicalDomain(BaseModel):
    domain_left_edge = None
    domain_right_edge = None
    domain_dimensions = None


class ytDomain(BaseModel):
    current_time = None
    domain: PhysicalDomain
