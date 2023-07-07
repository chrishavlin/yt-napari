class DatasetSummary:
    def __init__(self, ds):
        self.dataset_type = type(ds)

        cosmo_atts = (
            "cosmological_dataset",
            "current_redshift",
            "omega_lambda",
            "omega_matter",
            "omega_radiation",
            "hubble_constant",
        )
        if ds.cosmological_dataset:
            for ca in cosmo_atts:
                setattr(self, ca, getattr(ds, ca))

        self.coordinate_system = ds.coordinates.name
