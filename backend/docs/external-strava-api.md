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

Activity list filters: `after`, `before`, `sport`, `typeGroup` (`run`, `strength`, `other`), `minDistanceM`, `maxDistanceM`, `minMovingTimeSec`, `maxMovingTimeSec`, `hasHeartrate`, `gearId`, `trainer`, `page`, `perPage` (max 100), `sort` (`start_date_desc` or `start_date_asc`).

Missing stored values are JSON `null`. Streams and Garmin running dynamics are not included.

Errors:

```json
{ "error": { "code": "unauthorized", "message": "Invalid or missing API key" } }
```

`401` unauthorized, `404` not_found, `422` invalid_query.
