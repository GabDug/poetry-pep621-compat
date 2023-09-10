from __future__ import annotations


def compare_dicts(dict1, dict2):
    """
    Compare two dictionaries and return the differences between them.

    # XXX Named tuple for the diff values?

    Returns:
    - A dictionary containing the differences between dict1 and dict2.
      Keys are the paths to modified elements, and values are tuples with
      the type of change ('added', 'deleted', 'modified') and the values
      from dict1 and dict2.
    """
    diff = {}

    def compare_recursive(path, d1, d2):
        for key in set(d1.keys()) | set(d2.keys()):
            new_path = path + [key]

            if key not in d1:
                diff[tuple(new_path)] = ("added", d2[key])
            elif key not in d2:
                diff[tuple(new_path)] = ("deleted", d1[key])
            elif isinstance(d1[key], dict) and isinstance(d2[key], dict):
                compare_recursive(new_path, d1[key], d2[key])
            elif d1[key] != d2[key]:
                diff[tuple(new_path)] = ("modified", (d1[key], d2[key]))

    compare_recursive([], dict1, dict2)
    return diff
