# Hawkers Model

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

The model has not been evaluated yet. Crowded frames, occlusion by vehicles or
pedestrians, unusual stall layouts, and low-light scenes are required failure
categories for the first benchmark. In particular, occlusion in crowded frames
is an anticipated risk, not a measured result.

Model artifacts belong in `weights/` as GitHub Release assets or Git LFS files;
raw binaries must never be committed to the repository.