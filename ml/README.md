# Machine Learning

Independent hazard models share one `DetectionResult` output contract.

```text
ml/
  models/            Model-specific training entry points and weights
  inference/          Unified inference pipeline and output contract
  fusion/             Sensor fusion, tracking, and cross-vehicle clustering
  evaluation/         Benchmark reports and confusion matrices
```

Model weights are external artifacts and must not be committed directly to Git.