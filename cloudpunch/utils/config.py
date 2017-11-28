import collections


def merge_configs(default, new):
    for key, value in new.items():
        if (key in default and isinstance(default[key], dict) and
                isinstance(new[key], collections.Mapping)):
            merge_configs(default[key], new[key])
        else:
            default[key] = new[key]
    return default
