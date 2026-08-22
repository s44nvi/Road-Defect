# Severity and Priority Formula

This document defines the initial scoring contract used by the road-defect
pipeline. Every input is normalized to `[0, 1]`, and every score component is
returned with the result so an officer can inspect the calculation. The weights
are an initial configuration and must be calibrated against municipal outcomes.

## Severity score

The model estimates severity from the defect class, visible extent, estimated
depth, and visual confidence:

```text
severity = 0.45 * class_severity
         + 0.30 * size
         + 0.15 * depth
         + 0.10 * vision_confidence
```

`class_severity` is a configured baseline for the detected class. `size` is the
normalized affected-area estimate, `depth` is the normalized depth estimate
when available, and `vision_confidence` is the detector confidence. Missing
depth is recorded as unknown and must not silently be treated as a measured
value; the production implementation should renormalize the available terms.

## Evidence score

Visual and sensor evidence are combined before prioritization:

```text
evidence_score = 0.50 * vision_confidence
               + 0.25 * impact_match
               + 0.25 * repeat_observation_factor
```

`impact_match` measures agreement between the accelerometer event and the
detected location. `repeat_observation_factor` increases when independent trips
observe the same issue and is capped at `1.0`.

## Priority score

```text
priority_score = 0.35 * severity
               + 0.25 * road_criticality
               + 0.20 * recurrence
               + 0.10 * evidence_score
               + 0.10 * recency
```

`road_criticality` represents road class and nearby critical points of interest.
`recurrence` represents repeated observations over the configured time window.
`recency` decays as the latest observation gets older. Priority bands are
configured operationally; the score itself remains continuous for ranking.

## Worked example

For a pothole with the following normalized inputs:

```text
class_severity       = 0.80
size                 = 0.60
depth                = 0.50
vision_confidence    = 0.90
impact_match         = 0.70
repeat_observation   = 0.80
road_criticality     = 0.90
recurrence           = 0.60
recency              = 1.00
```

The intermediate scores are:

```text
severity = 0.45*0.80 + 0.30*0.60 + 0.15*0.50 + 0.10*0.90
         = 0.725

evidence_score = 0.50*0.90 + 0.25*0.70 + 0.25*0.80
               = 0.825

priority_score = 0.35*0.725 + 0.25*0.90 + 0.20*0.60
               + 0.10*0.825 + 0.10*1.00
               = 0.788
```

The defect is therefore ranked at `0.788` before any officer adjustment. If an
officer changes the severity to `0.90`, the system replaces the model severity,
recalculates priority, and appends the decision to the audit trail.