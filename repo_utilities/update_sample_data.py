import json
import os
from collections import defaultdict

import yaml

# requirements: cartesian, 3D, grid-based
enabled = [
    "DeeplyNestedZoom",
    "Enzo_64",
    "HiresIsolatedGalaxy",
    "IsolatedGalaxy",
    "PopIII_mini",
    # 'MHDSloshing',
    "GaussianCloud",
    "SmartStars",
    # 'ENZOE_orszag-tang_0.5', # cant handle -, .
    "GalaxyClusterMerger",  # big but neat
    # 'InteractingJets',
    "cm1_tornado_lofs",
]
enabled.sort()

# default field to load, whether or not to log
sample_field = defaultdict(lambda: ("gas", "density"))
log_field = defaultdict(lambda: True)


# over-ride the default for some
sample_field["cm1_tornado_lofs"] = ("cm1", "dbz")
log_field["cm1_tornado_lofs"] = False


def get_sample_func_name(sample: str):
    return f"sample_{sample.lower()}"


def pop_a_command(command: str, napari_config: dict):

    popid = None
    for icmd, cmd in enumerate(napari_config["contributions"]["commands"]):
        if cmd["id"] == command:
            popid = icmd

    if popid is not None:
        napari_config["contributions"]["commands"].pop(popid)


def get_command_name(sample_name: str):
    return f"yt-napari.data.{sample_name.lower()}"


def get_command_entry(sample_name: str):
    cmmnd = {}
    cmmnd["id"] = get_command_name(sample_name)
    cmmnd["title"] = f"Load {sample_name}"
    funcname = get_sample_func_name(sample_name)
    cmmnd["python_name"] = f"yt_napari.sample_data._sample_data:{funcname}"
    return cmmnd


def get_sample_table_entry(sample_name: str):
    entry = {}
    entry["key"] = sample_name.lower()
    entry["display_name"] = sample_name
    entry["command"] = get_command_name(sample_name)
    return entry


def update_napari_hooks(napari_yaml):

    with open(napari_yaml, "r") as file:
        napari_config = yaml.safe_load(file)

    existing = []
    if "sample_data" in napari_config["contributions"]:
        existing = napari_config["contributions"]["sample_data"]

    # first remove existing commands
    for sample in existing:
        pop_a_command(sample["command"], napari_config)

    # now remove the sample data entries
    napari_config["contributions"]["sample_data"] = []

    # now repopulate
    for sample in enabled:
        entry = get_sample_table_entry(sample)
        napari_config["contributions"]["sample_data"].append(entry)

        new_command = get_command_entry(sample)
        napari_config["contributions"]["commands"].append(new_command)

    with open(napari_yaml, "w") as file:
        yaml.dump(napari_config, file)


def get_load_dict(sample_name):
    load_dict = {"datasets": []}

    field_type, field_name = sample_field[sample_name]
    ds_entry = {
        "filename": sample_name,
        "selections": {
            "regions": [
                {
                    "fields": [
                        {
                            "field_name": field_name,
                            "field_type": field_type,
                            "take_log": log_field[sample_name],
                        }
                    ]
                }
            ]
        },
    }
    load_dict["datasets"].append(ds_entry)
    return load_dict


def write_sample_jsons(json_dir):

    # first clear out
    for fname in os.listdir(json_dir):
        if fname.endswith(".json"):
            os.remove(os.path.join(json_dir, fname))

    # and add back
    for sample in enabled:
        json_name = os.path.join(json_dir, f"sample_{sample.lower()}.json")
        load_dict = get_load_dict(sample)
        with open(json_name, "w") as fi:
            json.dump(load_dict, fi, indent=4)
        # add newline at end of file to satisfy linting
        with open(json_name, "a") as fi:
            fi.write("\n")
        print(f"    {json_name}")

    enabled_j = {"enabled": enabled}
    enabled_file = os.path.join(json_dir, "sample_registry.json")
    with open(enabled_file, "w") as fi:
        json.dump(enabled_j, fi, indent=4)
    with open(enabled_file, "a") as fi:
        fi.write("\n")
    print(f"    {enabled_file}")


def single_sample_loader(sample: str):
    code = []
    code.append(f"def {get_sample_func_name(sample)}() -> List[Layer]:")
    loadstr = '    return gl.load_sample_data("'
    loadstr += sample
    loadstr += '")'
    code.append(loadstr)
    code.append("")
    code.append("")
    return code


def write_sample_data_python_loaders(sample_data_dir):
    sd_py = []
    sd_py.append("# this file is autogenerated byt the taskipy update_sample data task")
    sd_py.append("# to re-generate it, along with all the json files in this dir, run:")
    sd_py.append("#     task update_sample_data")
    sd_py.append("# (requires taskipy: pip install taskipy)")
    sd_py.append("from typing import List")
    sd_py.append("")
    sd_py.append("from yt_napari._types import Layer")
    sd_py.append("from yt_napari.sample_data import _generic_loader as gl")
    sd_py.append("")
    sd_py.append("")

    for sample in enabled:
        sample_code = single_sample_loader(sample)
        sd_py += sample_code

    sd_py.pop(-1)  # only want one blank line at the end

    loader_file = os.path.join(sample_data_dir, "_sample_data.py")
    with open(loader_file, "w") as fi:
        fi.write("\n".join(sd_py))


if __name__ == "__main__":

    print("updating src/yt_napari/napari.yaml")
    update_napari_hooks("src/yt_napari/napari.yaml")
    print("writing out sample jsons to src/yt_napari/sample_data/")
    write_sample_jsons("src/yt_napari/sample_data/")
    print("writing src/yt_napari/sample_data/_sample_data.py")
    write_sample_data_python_loaders("src/yt_napari/sample_data/")
