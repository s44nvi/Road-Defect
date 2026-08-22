# Pothole and Crack Model

## Evaluation record

The repository currently contains no trained weights or evaluation manifest.
These values must be filled from a reproducible benchmark before this model is
described as production-ready.

| Field | Current value |
| --- | --- |
| Dataset source | TBD: record dataset name, URL, and version |
| Image count | TBD |
| Train / validation split | TBD |
| Current mAP@0.5 | TBD |
| Weight version | See `ml/weights_registry.md` |

## Known failure cases

No failure analysis has been run yet. The first evaluation must report errors
separately for potholes, cracks, manholes, and debris, including low light,
waterlogged roads, worn paint, and partially occluded defects.

Model artifacts belong in `weights/` as GitHub Release assets or Git LFS files;
raw binaries must never be committed to the repository.