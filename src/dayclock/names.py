"""Offline English names, with recorded names taking priority over IOC data."""

from collections import Counter, defaultdict
from functools import lru_cache
from importlib.resources import files
import json


# A familiar British short name; this alias is ours, not an IOC name change.
ALIASES = {"Erithacus rubecula": ("Robin",)}


@lru_cache(maxsize=1)
def _lookup():
    resource = files("dayclock").joinpath("resources").joinpath("ioc-en.json")
    return {name.casefold(): common for name, common in json.loads(resource.read_text(encoding="utf-8")).items()}


def common_name(scientific_name, recorded_name=""):
    """Return a recorded name, IOC English name, or the scientific name."""
    if recorded_name and recorded_name.strip():
        return recorded_name
    return _lookup().get(scientific_name.casefold(), scientific_name)


def preferred_names(rows):
    """Choose recorded names before the bundled lookup, across all stations."""
    recorded = defaultdict(Counter)
    species = set()
    for row in rows:
        species.add(row.scientific_name)
        if row.common_name and row.common_name.strip():
            recorded[row.scientific_name][row.common_name] += 1
    return {name: common_name(name, recorded[name].most_common(1)[0][0] if recorded[name] else "")
            for name in species}
