# Machine Learning

Independent hazard models share one `DetectionResult` output contract.

```text
ml/
  training/          Dataset preparation and training entry points
  models/            Pothole, crack, manhole, debris, and future obstruction adapters
  inference/         Unified inference pipeline
  tracking/          Per-trip temporal consolidation
  sensor_fusion/     Accelerometer and visual corroboration
  clustering/        Cross-vehicle spatial and temporal merging
  severity/          Estimated severity classes and normalized scores
  configs/           Versioned inference configuration
```

Model weights are external artifacts and must not be committed directly to Git.