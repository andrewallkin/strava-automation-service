# Strava Analytics Data Granularity

This document recommends the Strava data that should be pulled and stored for MCP-based training analysis.

The goal is not to mirror every Strava API surface. The goal is to store enough structure for an LLM to answer the kinds of questions a runner, cyclist, or gym athlete would ask: what happened in this workout, whether the workout matched the intent, how intensity changed over time, how recent training compares with prior blocks, and what caveats exist because of missing data.

## Recommendation

Use `DetailedActivity` as the canonical source payload, then promote the nested workout structure into first-class queryable tables.

Required first-pass data:

- Detailed activity from `GET /api/v3/activities/{id}?include_all_efforts=true`.
- Activity laps from the detailed activity response, with `GET /api/v3/activities/{id}/laps` as a fallback or verification call.
- Segment efforts from `segment_efforts` in the detailed activity response.
- Run splits from `splits_metric` and `splits_standard` when present.
- Best efforts from `best_efforts` when present.

Recommended optional data:

- Activity zones from `GET /api/v3/activities/{id}/zones` when the token and Strava account expose them.
- Stream availability metadata so the app knows whether raw streams can be fetched later.

Deferred data:

- Raw activity streams from `GET /api/v3/activities/{id}/streams`. Streams are useful for second-by-second reconstruction, but they are not required for the first MCP version if laps, splits, segment efforts, heart rate, cadence, and power summaries are stored well.

## Endpoint Plan

### Backfill Discovery

```text
GET /api/v3/athlete/activities
  ?after={epoch_seconds}
  &before={epoch_seconds}
  &page={page}
  &per_page=200
```

Use this endpoint only to discover candidate activity IDs and summary metadata during backfill. Do not treat the summary response as the complete analytics record.

Requires `activity:read`. Activities marked "Only Me" require `activity:read_all`.

### Detailed Activity

```text
GET /api/v3/activities/{id}
  ?include_all_efforts=true
```

This is the primary ingestion endpoint. Store the raw detailed payload and promote important scalar fields into columns.

The `include_all_efforts=true` flag matters because segment efforts are useful for repeated climb, sprint, route, and trail comparisons over time.

Requires `activity:read`. Activities marked "Only Me" require `activity:read_all`.

### Activity Laps

```text
GET /api/v3/activities/{id}/laps
```

Use this when the detailed activity payload has missing or incomplete `laps`, or if you want a dedicated refresh path for interval analysis.

Laps are critical for workouts because they are the best Strava-native representation of interval structure without fetching raw streams.

Requires `activity:read`. Activities marked "Only Me" require `activity:read_all`.

### Activity Zones

```text
GET /api/v3/activities/{id}/zones
```

Use this as optional enrichment. Zones can help summarize time in heart-rate or power ranges without storing raw streams, but Strava documents this as a Summit feature, so ingestion must tolerate missing or unauthorized responses.

Requires `activity:read`. Activities marked "Only Me" require `activity:read_all`.

### Deferred Activity Streams

```text
GET /api/v3/activities/{id}/streams
  ?keys=time,distance,altitude,velocity_smooth,heartrate,cadence,watts
  &key_by_type=true
```

Do not make this required for the first analytics version.

Fetch streams later only when the MCP server needs answers that cannot be produced from activity, lap, split, best-effort, segment-effort, and zone data. Examples include second-by-second pacing charts, precise cardiac drift inside a long steady-state section, or reconstructing custom intervals that were not marked as laps.

Location streams are intentionally excluded from the first deferred key set. Add `latlng` later only if route shape, terrain matching, heatmap analysis, or map display becomes a real requirement.

## Data To Store

### Activity Core

Store one row per Strava activity in `strava_activities`.

Promote these fields to scalar columns because MCP tools will filter, group, and sort by them often:

- `id` as `activity_id`.
- `athlete.id` as `athlete_id`.
- `name`.
- `description`.
- `type` and `sport_type`.
- `start_date`, `start_date_local`, and `timezone`.
- `distance`.
- `moving_time` and `elapsed_time`.
- `total_elevation_gain`, `elev_high`, and `elev_low`.
- `average_speed` and `max_speed`.
- `has_heartrate`, `average_heartrate`, and `max_heartrate` when present.
- `average_cadence` when present.
- `average_watts`, `max_watts`, `weighted_average_watts`, `kilojoules`, and `device_watts` when present.
- `calories`.
- `suffer_score` when present.
- `gear_id`.
- `trainer`, `commute`, `manual`, `private`, `flagged`, and `hide_from_home`.
- `workout_type`.
- `achievement_count`, `pr_count`, `kudos_count`, and `athlete_count` if present.
- `device_name`.

Keep the complete detailed payload in a JSONB column such as `summary_data` or `detail_data`. Strava adds and changes fields over time, and raw JSON preservation prevents analysis dead ends later.

### Low-Priority Map Metadata

Store map and location summary fields, but do not optimize around them in the first version:

- `map.id`.
- `map.summary_polyline`.
- `start_latlng`.
- `end_latlng`.

This keeps future route and terrain analysis possible without making latitude/longitude central to the initial schema.

### Laps

Store one row per lap in `strava_activity_laps`.

Promote these fields:

- `id` as `lap_id`.
- `activity.id` as `activity_id`.
- `athlete.id` as `athlete_id`.
- `lap_index`.
- `name`.
- `split`.
- `start_date` and `start_date_local`.
- `distance`.
- `moving_time` and `elapsed_time`.
- `average_speed` and `max_speed`.
- `average_heartrate` and `max_heartrate` when present.
- `average_cadence` when present.
- `average_watts` and `device_watts` when present.
- `total_elevation_gain`.
- `pace_zone`.
- `start_index` and `end_index` when present.
- Raw lap JSON.

Why laps matter:

- Runners use laps for interval repeats, recoveries, warmups, cooldowns, strides, and races.
- Cyclists use laps for climbs, efforts, intervals, and structured workouts.
- Gym and HIIT activities may use laps for rounds or blocks if the recording device emits them.
- MCP tools can analyze workout intent without reading raw streams: "Were the 6 x 800m repeats consistent?", "Did heart rate recover between intervals?", or "Was the cooldown truly easy?"

For analysis, derive these lap-level values in metadata or views:

- Pace per lap for runs and walks.
- Speed per lap for rides.
- Work/rest classification when lap names or alternating intensity suggest intervals.
- Lap-to-lap pace, heart-rate, cadence, or power drift.
- Recovery ratio, such as hard-lap time compared with following easy-lap time.

### Segment Efforts

Store one row per segment effort in `strava_activity_segment_efforts`.

Promote these fields:

- `id` as `segment_effort_id`.
- `activity_id`.
- `name`.
- `segment.id` as `segment_id`.
- `segment.name` as `segment_name`.
- `start_date` and `start_date_local`.
- `distance`.
- `moving_time` and `elapsed_time`.
- `start_index` and `end_index` when present.
- `average_heartrate` and `max_heartrate` when present.
- `average_cadence` when present.
- `average_watts` and `device_watts` when present.
- `is_kom`, `kom_rank`, `pr_rank`, and `hidden`.
- Raw effort JSON, including the nested `segment` summary.

Why segment efforts matter:

- They allow repeated-course comparisons without needing GPS streams.
- They help explain performance on hills, routes, and common sections.
- They give cyclists power and cadence context for meaningful efforts.
- They let MCP tools answer: "Am I getting faster on this climb?", "Was this PR driven by higher power or better pacing?", or "How did heart rate compare on the same segment last month?"

### Splits

Store run splits in `strava_activity_splits`, or keep them as JSONB if implementation scope needs to stay smaller. First-class rows are better for MCP queries.

Promote these fields:

- `activity_id`.
- Split source: `metric` or `standard`.
- `split`.
- `distance`.
- `moving_time` and `elapsed_time`.
- `average_speed`.
- `elevation_difference`.
- `pace_zone`.
- Raw split JSON.

Why splits matter:

- They are the simplest way to answer pacing questions for runs.
- They support race analysis without streams.
- They allow quick MCP summaries like positive split, negative split, fastest kilometer or mile, and pacing consistency.

### Best Efforts

Store `best_efforts` in `strava_activity_best_efforts`, or combine them with segment-effort storage if the schema clearly distinguishes effort type.

Promote these fields:

- `id` as `best_effort_id` when present.
- `activity_id`.
- `name`.
- `distance`.
- `moving_time` and `elapsed_time`.
- `start_date` and `start_date_local`.
- `start_index` and `end_index` when present.
- `pr_rank` when present.
- Raw effort JSON.

Why best efforts matter:

- They are especially useful for runners because Strava commonly reports benchmark efforts such as 400m, 1/2 mile, 1k, 1 mile, 5k, 10k, half marathon, and similar distances.
- They let MCP tools detect performance signals even when a workout was not explicitly structured.

### Activity Zones

If fetched, store zones in `strava_activity_zones` or in activity metadata with enough structure to query later.

Promote or preserve:

- Zone type, such as `heartrate` or `power`.
- Zone ranges.
- Time in each range.
- Whether the zone data came from Strava or was derived locally.
- Raw zone JSON.

Zones are useful for training-load summaries, but they should not be a hard dependency because availability varies.

### Streams

Keep streams out of the required first-pass ingestion path.

When streams are eventually added, keep them in a separate `strava_activity_streams` table so activity list queries and MCP searches do not accidentally load large JSON payloads.

Useful stream keys by future use case:

- `time`: aligns all other stream values.
- `distance`: reconstructs pace by section.
- `velocity_smooth`: speed and pace over time.
- `heartrate`: cardiac drift and recovery analysis.
- `cadence`: run form and cycling cadence changes.
- `watts`: cycling intensity and power-based intervals.
- `altitude`: climb and terrain context.
- `latlng`: route analysis only when location becomes important.

## Suggested Storage Shape

Recommended tables for the analytics-first model:

- `strava_activities`: one row per activity, scalar fields for common filters, and raw detailed activity JSON.
- `strava_activity_laps`: one row per lap for interval and workout-structure analysis.
- `strava_activity_segment_efforts`: one row per segment effort for repeated-course analysis.
- `strava_activity_splits`: one row per metric or standard split, especially useful for running.
- `strava_activity_best_efforts`: one row per best effort, especially useful for benchmarks and PR analysis.
- `strava_activity_zones`: optional one row per activity and zone type, or JSONB if implementation should stay small.
- `strava_activity_streams`: deferred one row per activity containing raw streams and stream metadata.

Each child table should include:

- `activity_id` foreign key.
- A stable Strava identifier when one exists.
- An ordinal/index column when ordering matters.
- Promoted scalar fields used by MCP queries.
- Raw JSONB for the original nested object.
- Ingestion timestamps for debugging refresh behavior.

Keep `strava_ingestion_jobs` and `strava_backfill_runs` as operational tables, not analytics tables.

This extends the model in `docs/STRAVA-DATA-MODEL.md`: keep `strava_activities` as the primary activity table, keep `strava_activity_streams` available for later high-volume stream storage, and add the lap, segment-effort, split, best-effort, and zone tables when the implementation moves from whole-activity summaries to workout analysis.

## Sport-Specific Analysis Needs

### Running

High-value questions:

- Was the workout executed as planned?
- Were intervals consistent?
- Did pace fade while heart rate increased?
- Was the easy running actually easy?
- How did this compare with prior efforts at similar distances?

Most important data:

- Activity distance, moving time, elapsed time, elevation, average and max heart rate.
- Laps for interval structure.
- Metric splits for pacing.
- Best efforts for benchmark distances.
- Gear for shoe mileage and injury context.
- Segment efforts for repeated hills or routes.

### Cycling

High-value questions:

- How hard was the ride?
- Was power steady?
- Did performance improve on repeated climbs or segments?
- Was the effort indoors, outdoors, commute, or training?
- Was power measured or estimated?

Most important data:

- Activity distance, moving time, elevation, speed, power, weighted average watts, kilojoules, heart rate, cadence.
- Segment efforts for climbs and repeated route sections.
- Laps for structured intervals.
- `device_watts` to distinguish power-meter data from estimates.
- Trainer and commute flags.
- Gear for bike usage.

### Gym, HIIT, Weight Training, Yoga, And Workout

High-value questions:

- What kind of session was this?
- How long was the session?
- Was it easy, moderate, or hard?
- Is there enough data to analyze beyond duration?
- How does it affect weekly training load?

Most important data:

- `sport_type`, `name`, `description`, start time, moving time, elapsed time, calories, average and max heart rate.
- Laps if the device records rounds, intervals, or blocks.
- Activity zones if available.
- Perceived exertion fields if Strava includes them in the detailed payload.

For gym-style activities, the LLM should be explicit when data is thin. Duration plus heart rate can support training-load context, but it cannot infer sets, reps, or exercises unless those details are in the name or description.

### Walking, Hiking, And Trail Running

High-value questions:

- How much aerobic volume did this add?
- How much climbing was involved?
- Was the effort easy or strenuous?
- Was pace affected by terrain?

Most important data:

- Distance, elapsed time, moving time, elevation gain, high and low elevation, heart rate, splits, and segment efforts.
- Map summary metadata can be retained for future route context, but raw `latlng` streams are not required initially.

### Virtual And Trainer Activities

High-value questions:

- Was this an indoor training session?
- Was power available?
- Were intervals executed correctly?
- How does it compare with outdoor work?

Most important data:

- `sport_type`, `trainer`, distance, moving time, elapsed time, heart rate, cadence, watts, weighted average watts, kilojoules, laps, and zones.

## MCP Tool Support

This data should let MCP tools answer common questions without calling Strava:

- `search_activities`: filter by sport, date, distance, duration, elevation, gear, trainer, commute, and data availability.
- `get_activity_summary`: summarize activity-level metrics, splits, laps, segment efforts, gear, and caveats.
- `get_workout_analysis`: use laps first, then splits, best efforts, zones, and segment efforts.
- `get_weekly_training_summary`: aggregate volume, intensity, elevation, sport mix, long runs/rides, and hard sessions.
- `compare_periods`: compare volume, long activity progression, intensity distribution, and repeated segments.
- `compare_segment_efforts`: compare a segment across activities by time, heart rate, cadence, and power.
- `analyze_intervals`: inspect lap consistency, recoveries, and intensity drift.

MCP responses should include data caveats. Examples:

- "No heart-rate data was present, so intensity is based on pace only."
- "This activity has laps, but no power data."
- "Zone data was unavailable from Strava; using configured local heart-rate zones would be a separate derived metric."
- "Streams were not ingested, so this analysis uses lap and split summaries rather than second-by-second data."

## Derived Metrics Worth Computing

Store these in metadata or materialized views when they become useful:

- Pace per kilometer or mile for runs.
- Lap pace/speed, lap HR, lap cadence, and lap power summaries.
- Lap consistency score.
- Positive or negative split indicator.
- Hard/easy lap classification.
- Recovery heart-rate drop between work and rest laps.
- Segment PR and rank markers.
- Weekly volume by sport.
- Weekly elevation gain.
- Longest run and ride per week.
- Time in zones when zone data exists.
- Data quality flags such as `has_heartrate`, `has_power`, `has_cadence`, `has_laps`, `has_segments`, `has_splits`, and `has_streams`.

Keep derived metrics reproducible. If a value depends on configurable heart-rate zones, pace zones, FTP, threshold pace, or athlete weight, store the assumptions or model version.

## Data Quality And Caveats

Ingestion should preserve the difference between missing data and zero values.

Important caveats:

- Many runs have no power data.
- Many gym activities have little structure beyond duration and heart rate.
- Estimated cycling power should not be treated like power-meter data.
- Elapsed time and moving time can differ significantly for trail runs, hikes, commutes, and group rides.
- Laps may represent automatic splits, manual laps, or workout steps depending on the recording device.
- Segment efforts are public-route oriented and may be absent or hidden.
- Activity zones may be unavailable even when heart-rate samples exist.
- Streams can answer more precise questions, but they increase storage and rate-limit cost.

## First Implementation Boundary

For the first MCP-ready implementation, fetch:

1. Activity IDs from `GET /api/v3/athlete/activities` during backfill.
2. Full details from `GET /api/v3/activities/{id}?include_all_efforts=true`.
3. Laps from `GET /api/v3/activities/{id}/laps` only when the detailed activity lacks usable laps or when validating lap completeness.
4. Zones from `GET /api/v3/activities/{id}/zones` only if the added request cost and possible authorization failures are acceptable.

Do not fetch streams by default. Add stream ingestion as a later capability once there is a specific MCP tool or analysis question that cannot be answered from detailed activity, laps, splits, best efforts, segment efforts, and zones.
