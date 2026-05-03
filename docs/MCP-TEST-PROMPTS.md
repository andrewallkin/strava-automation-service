# MCP Tool Test Prompts

Prompts to manually test every MCP tool. Each section targets one specific tool. Where an `activity_id` is needed, first run a discovery prompt (e.g. `list_recent_runs`) to get a real ID, then substitute it in.

Use `[ACTIVITY_ID]`, `[ACTIVITY_ID_A]`, `[ACTIVITY_ID_B]` as placeholders — replace with real IDs from your data before running.

---

## Category A — Athlete & Configuration

### A1. `get_athlete_profile`
> What's my athlete profile? Tell me my name, weight, and give me a summary of my shoes.

### A2. `get_heart_rate_zones`
> What are my current heart rate zones? Show me the bpm boundaries for each zone.

---

## Category B — Activity Discovery

### B1. `search_activities`
**Basic search:**
> Search for my runs in April 2026.

**With filters:**
> Find all my runs between 8 and 15 km that had heart rate data recorded.

**Race filter:**
> Search my activities for any races I've done in the last year (workout_type = 1).

**Treadmill filter:**
> Show me all my treadmill runs from the last 3 months.

**Long runs:**
> Find runs over 18 km from the last 6 months.

### B2. `list_recent_runs`
> Show me my last 10 runs.

> List my most recent 5 runs.

### B3. `find_activity_by_date`
> Did I run today?

> What did I run yesterday?

> Find my activity from 2026-04-15.

### B4. `find_similar_runs`
> Find runs similar to activity [ACTIVITY_ID] from the past 90 days.

> What historical runs are comparable to [ACTIVITY_ID] in terms of distance and elevation?

---

## Category C — Single Activity Detail

### C1. `get_activity_summary`
> Give me a summary of activity [ACTIVITY_ID].

> What were the key stats for my run [ACTIVITY_ID]?

### C2. `get_activity_full_details`
> Give me the full details of activity [ACTIVITY_ID], including description, device, and temperature.

### C3. `classify_workout_type`
> What type of workout was activity [ACTIVITY_ID]? Was it an easy run, intervals, tempo, or something else?

> Classify the workout type for [ACTIVITY_ID].

---

## Category D — Laps & Interval Analysis

### D1. `get_activity_laps`
> Show me the lap breakdown for activity [ACTIVITY_ID].

> What were my lap times and heart rates for [ACTIVITY_ID]?

### D2. `analyze_intervals`
> Analyze the interval structure of activity [ACTIVITY_ID]. How consistent were my reps?

> Break down my interval session [ACTIVITY_ID] — show me fade, recovery HR drops, and work:rest ratio.

### D3. `compare_laps_within_activity`
> Compare the laps within activity [ACTIVITY_ID] and show me how each one changed relative to the previous.

### D4. `get_warmup_cooldown_quality`
> How was my warmup and cooldown in activity [ACTIVITY_ID]? Did I warm up properly before the hard effort?

---

## Category E — Splits & Pacing

### E1. `get_activity_splits`
> Show me the per-km splits for activity [ACTIVITY_ID].

> Give me the splits for [ACTIVITY_ID] in standard (miles) units.

### E2. `analyze_pacing`
> Analyze the pacing of activity [ACTIVITY_ID]. Did I positive split or negative split?

> How was my pacing consistency in [ACTIVITY_ID]? What was my pace variability?

### E3. `analyze_grade_adjusted_pace`
> Show me the grade-adjusted pace analysis for [ACTIVITY_ID]. How much did the terrain affect my pace?

> Compare my actual pace to my effort-adjusted pace for [ACTIVITY_ID].

---

## Category F — Heart Rate & Zones

### F1. `get_activity_hr_zone_distribution`
> How much time did I spend in each heart rate zone during activity [ACTIVITY_ID]?

> Show me the HR zone distribution for run [ACTIVITY_ID].

### F2. `analyze_hr_decoupling`
> Analyze aerobic decoupling for activity [ACTIVITY_ID]. Did my heart rate drift at the same pace?

> How was my aerobic efficiency in [ACTIVITY_ID]? Was there significant HR decoupling?

### F3. `get_period_hr_zone_distribution`
> Show me my total time in each HR zone across all runs in April 2026.

> What was my HR zone distribution for the last 4 weeks? How much quality time vs easy time did I log?

### F4. `validate_hr_zones`
> Are my heart rate zones well-calibrated based on my recent runs? Do the zones look correct?

> Diagnose my HR zones — do they reflect where I'm actually training?

---

## Category G — Cadence

### G1. `analyze_cadence`
> Analyze my cadence in activity [ACTIVITY_ID]. How did it compare to my baseline?

> Show me the per-lap cadence for [ACTIVITY_ID] and tell me if my form held up.

### G2. `get_cadence_trend`
> How has my average cadence trended over the last 3 months?

> Show me my cadence trend from 2026-01-01 to 2026-04-30.

---

## Category H — Elevation & Terrain

### H1. `get_elevation_profile_summary`
> Give me the elevation profile summary for activity [ACTIVITY_ID]. How hilly was it?

> What was the total elevation gain and hilliness index for [ACTIVITY_ID]?

---

## Category I — Best Efforts & PRs

### I1. `get_activity_best_efforts`
> What best efforts did I record in activity [ACTIVITY_ID]? Did I set any PRs?

> Show me all the benchmark distances recorded in run [ACTIVITY_ID].

### I2. `track_best_effort_progression`
> Track my 5K best effort progression over the last year. Am I improving?

> Show me my 1K best effort trend for the past 6 months.

> How has my half marathon best effort progressed over the last year?

### I3. `find_pr_activities`
> Which of my recent runs set a Strava PR? Show me activities where I set personal records.

> Find any PR activities from the last 6 months.

---

## Category J — Aggregations

### J1. `get_weekly_summary`
> Give me a weekly training summary for the last 8 weeks.

> Show me my per-week stats for the last 4 weeks including distance, time, and quality minutes.

### J2. `get_monthly_summary`
> Show me my monthly training totals for the last 6 months.

> Summarize my training month by month for the past year.

### J3. `get_period_summary`
> Give me a training summary for April 2026.

> Summarize all my running from 2026-03-01 to 2026-04-30.

---

## Category K — Trends & Progression

### K1. `get_volume_trend`
> Show me my weekly mileage trend for the last 12 weeks. Are there any sharp ramp-up flags?

> How has my weekly volume trended over the last 6 months?

### K2. `get_intensity_distribution`
> What's my intensity distribution for April 2026? Am I training polarized or threshold-heavy?

> Show me the polarization of my training from 2026-01-01 to 2026-04-30.

### K3. `get_long_run_progression`
> How has my long run progressed over the last 12 weeks?

> Show me the trend in my longest run each week for the past 3 months.

### K4. `get_pace_at_distance_progression`
> How has my pace evolved for runs between 8 and 12 km over the last 6 months?

> Show me my pace progression for half-marathon-distance runs (18–22 km) over the past year.

---

## Category L — Comparisons

### L1. `compare_activities`
> Compare activity [ACTIVITY_ID_A] and activity [ACTIVITY_ID_B] side by side.

### L2. `compare_periods`
> Compare my training in the last 4 weeks to the 4 weeks before that.

> Compare March 2026 vs April 2026 training — distance, quality minutes, and HR zones.

### L3. `compare_to_similar_recent_runs`
> How did activity [ACTIVITY_ID] compare to similar runs from the past 90 days?

> Was my run [ACTIVITY_ID] better or worse than comparable past runs in terms of pace and HR?

---

## Category M — Training Load & Recovery

### M1. `get_recovery_status`
> How recovered am I right now? When was my last hard run?

> Give me a recovery snapshot as of today.

### M2. `compute_acute_chronic_ratio`
> What's my acute:chronic workload ratio right now? Am I at injury risk?

> Compute my ACWR based on distance. Am I in the sweet spot?

### M3. `detect_training_red_flags`
> Scan my last 4 weeks of training for any red flags. Is anything concerning?

> Are there any warning signs in my recent training — volume ramps, no rest days, HR drift?

---

## Category N — Gear & Data Meta

### N1. `get_shoe_mileage`
> How many kilometers are on each of my shoes? Do any need replacing?

> Show me my shoe mileage including retired shoes.

### N2. `get_athlete_stats`
> Show me my overall Strava stats — all-time totals and recent year totals.

### N3. `check_data_availability`

**Per activity:**
> What data is available for activity [ACTIVITY_ID]? Does it have laps, zones, and splits?

**Per date range:**
> What data do I have for April 2026? Are there any gaps or missing HR activities?

---

## Multi-Tool Workflow Prompts

These prompts should chain several tools together — good for testing tool orchestration.

### Full activity breakdown
> How was my run on 2026-04-15? Give me a complete analysis.

### Post-interval session review
> Analyze my most recent interval workout in detail — classify it, break down the reps, check my warmup and cooldown, and tell me if my HR zones were appropriate.

### Fitness check
> How is my fitness trending? Look at volume, long run progression, 5K best effort trend, and intensity distribution over the last 3 months.

### Training health check
> Run a full training health check: recovery status, ACWR, red flags, and HR zone validation.

### Pre-race readiness
> Am I ready to race? Check my recent training load, long run progression, and compare the last 4 weeks to the prior 4 weeks.

### Shoe audit
> Audit my gear. Which shoes am I using most, and are any due for replacement?
