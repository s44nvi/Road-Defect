# Processing Worker

Background processing boundary for jobs that should not block API requests.

Suggested job types:

```text
screen_observation
track_trip_events
fuse_sensor_evidence
consolidate_defects
calculate_segment_health
calculate_priority
validate_repair
```

Model inference is accessed through an adapter so the demo mock, a local YOLO model, and a future on-device producer share the same output contract.