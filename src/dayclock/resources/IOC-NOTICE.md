# IOC English common-name data

`ioc-en.json` is derived from **IOC World Bird List v15.2**, edited by
Frank Gill, David Donsker and Pamela Rasmussen. The checklist is published by
the **International Ornithologists' Union (IOU)** through GBIF.

- IOC version DOI: https://doi.org/10.14344/IOC.ML.15.2
- GBIF dataset DOI: https://doi.org/10.15468/anfqn6
- Publisher's dataset and licence declaration:
  https://www.gbif.org/dataset/c696e5ee-9088-4d11-bdae-ab88daffab78
- Source archive: https://hosted-datasets.gbif.org/datasets/ioc.zip
- IOC master lists: https://www.worldbirdnames.org/new/ioc-lists/master-list-2/
- Licence: **Creative Commons Attribution 4.0 International (CC BY 4.0)**
  https://creativecommons.org/licenses/by/4.0/
- Full terms: https://creativecommons.org/licenses/by/4.0/legalcode.en

The GBIF publisher record explicitly declares CC BY 4.0. The downloaded
archive's `metadata.yaml` identifies version 15.2, issued 25 October 2026, and
declares `license: CC-BY`. Downloaded and verified on 31 October 2026.

Source archive SHA-256:
`852b91a7b8ed2c66d86ea12896ea67be1b6b9d4d9bc5afe1c9f8a6b52d7c5495`

Changes made by Day clock: joined the archive's `NameUsage.tsv` and
`VernacularName.tsv` by taxon ID; kept accepted species and English (`eng`)
names only; removed other fields and converted to a sorted JSON mapping.
The bundled mapping has 11,250 entries. Scientific and English name strings
are preserved as supplied, including IOC spelling conventions. No images,
descriptions, recordings or detection data are included.

To reproduce with the same archive, run:

```sh
python scripts/build_common_names.py ioc.zip src/dayclock/resources/ioc-en.json
```

The short search alias `Robin` for `Erithacus rubecula` is a Day clock addition
in Python code. It does not replace IOC's preferred name, `European Robin`.
Names recorded in an input file take priority for display and exact common-name
matching. Scientific names absent from the lookup remain usable unchanged.

The data remains under CC BY 4.0; it is not relicensed under MIT. Day clock's
code, documentation and synthetic examples are under MIT. Redistribution of
this data must retain appropriate credit, the licence link and the indication
of changes. No endorsement by IOC, IOU, the editors or GBIF is implied.
