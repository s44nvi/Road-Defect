# Fallen Trees Model

## Evaluation record

This is a planned extension model. No dataset, trained weights, or benchmark
results are currently present in the repository.

| Field | Current value |
| --- | --- |
| Dataset source | TBD: record dataset name, URL, and version |
| Image count | TBD |
| Train / validation split | TBD |
| Current mAP@0.5 | TBD |
| Weight version | See `ml/weights_registry.md` |

## Known failure cases

The model has not been evaluated yet. The first benchmark must check partial
occlusion by vehicles, branches blending into foliage, nighttime imagery,
storm debris, and trees lying outside the road boundary.

Model artifacts belong in `weights/` as GitHub Release assets or Git LFS files;
raw binaries must never be committed to the repository.