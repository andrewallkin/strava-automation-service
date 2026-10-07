# External Strava API

Read-only JSON for one athlete. Authenticate every route except this document.

```http
Authorization: Bearer sva_YOUR_KEY
```

Base path: `/api/external`

| Method | Path | Purpose |
|---|---|---|
| GET | `/health` | Activity count and last ingest time |
| GET | `/athlete` | Profile, heart-rate zones, power zones, gear |
| GET | `/activities` | Paginated summaries |
| GET | `/activities/{id}` | Summary plus laps, splits, zones, best efforts, same-day activities |
| GET | `/activities/{id}/laps` | Laps |
| GET | `/activities/{id}/splits` | Kilometre and mile splits |
| GET | `/activities/{id}/zones` | Heart-rate, pace, and power time-in-zone |
| GET | `/activities/{id}/best-efforts` | Best efforts |
| GET | `/stats/weekly?weeks=8` | Monday weeks in Africa/Johannesburg |
| GET | `/stats/range?from=YYYY-MM-DD&to=YYYY-MM-DD&groupBy=week` | `groupBy` is `day`, `week`, or `month` |
| GET | `/stats/consistency` | Last 28 local days |

Activity list filters: `after`, `before`, `sport` (exact Strava `sport_type`, e.g. `Run`, `Walk`, `Golf`, `Padel`, `Workout`, `WeightTraining`), `typeGroup` (`run`, `strength`, `other`), `minDistanceM`, `maxDistanceM`, `minMovingTimeSec`, `maxMovingTimeSec`, `hasHeartrate`, `gearId`, `trainer`, `page`, `perPage` (max 100), `sort` (`start_date_desc` or `start_date_asc`).

Each `/stats/weekly` week and `/stats/range` period includes `bySportType`: an object keyed by Strava `sport_type` exactly as stored. Each value has `activityCount`, `distanceM`, `movingTimeSec`, `elapsedTimeSec`, `elevationGainM`, and `days` (sorted local dates). Activities without a `sport_type` are counted under `Unknown`. A period with no activities has `"bySportType": {}`. The `run`, `strength`, and `other` blocks are unchanged.

`/stats/consistency` includes `activitiesBySportType28d`: the activity count per `sport_type` over the same 28 local days.

Missing stored values are JSON `null`. Streams and Garmin running dynamics are not included.

Errors:

```json
{ "error": { "code": "unauthorized", "message": "Invalid or missing API key" } }
```

`401` unauthorized, `404` not_found, `422` invalid_query.
