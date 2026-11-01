"""Extract the English species lookup from an IOC CoLDP archive (no downloads).

Usage: python scripts/build_common_names.py ioc.zip src/dayclock/resources/ioc-en.json
Source, version, checksum and licence: src/dayclock/resources/IOC-NOTICE.md.
"""

import argparse
import csv
from io import TextIOWrapper
import json
from pathlib import Path
from zipfile import ZipFile


def extract(archive):
    with ZipFile(archive) as source:
        with TextIOWrapper(source.open("NameUsage.tsv"), encoding="utf-8") as handle:
            species = {r["col:ID"]: r["col:scientificName"]
                       for r in csv.DictReader(handle, delimiter="\t")
                       if r["col:rank"] == "species" and r["col:status"] == "accepted"}
        names = {}
        with TextIOWrapper(source.open("VernacularName.tsv"), encoding="utf-8") as handle:
            for row in csv.DictReader(handle, delimiter="\t"):
                if row["col:language"] != "eng" or row["col:taxonID"] not in species:
                    continue
                scientific = species[row["col:taxonID"]]
                common = row["col:name"]
                if scientific in names and names[scientific] != common:
                    raise ValueError(f"Conflicting English names for {scientific}")
                names[scientific] = common
    return names


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("archive", type=Path)
    parser.add_argument("output", type=Path)
    args = parser.parse_args()
    names = extract(args.archive)
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(json.dumps(names, ensure_ascii=False, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    print(f"Extracted {len(names)} English species names")
