import { describe, expect, it } from "vitest";

import type { ActivityTypeSummary, SportTypeTotals, StoredActivity } from "./api";
import {
  activityCardFacts,
  activityTypeRows,
  formatDistanceKm,
  formatHoursMinutes,
  formatPace,
  isRunSport,
  sportIcon,
  weekTotals,
} from "./activityTypes";

function totals(activityCount: number, movingTimeSec: number): SportTypeTotals {
  return { activityCount, distanceM: 0, movingTimeSec, elapsedTimeSec: movingTimeSec, elevationGainM: 0, days: [] };
}

function summary(
  thisWeek: Record<string, SportTypeTotals>,
  lastWeek: Record<string, SportTypeTotals>,
): ActivityTypeSummary {
  return {
    thisWeek: { start: "2026-10-05", end: "2026-10-11", bySportType: thisWeek },
    lastWeek: { start: "2026-09-28", end: "2026-10-04", bySportType: lastWeek },
  };
}

function activity(overrides: Partial<StoredActivity>): StoredActivity {
  return {
    id: "1",
    name: "Activity",
    sportType: "Run",
    startDateLocal: "2026-10-07T06:02:00+00:00",
    distanceM: null,
    movingTimeSec: null,
    elapsedTimeSec: null,
    elevationGainM: null,
    averageHeartrate: null,
    averagePaceSecPerKm: null,
    ...overrides,
  };
}

describe("activityTypeRows", () => {
  it("sorts by this week's moving time, then last week's, and keeps missing weeks as null", () => {
    const rows = activityTypeRows(
      summary(
        { Run: totals(2, 5840), Padel: totals(1, 4285), Walk: totals(1, 3004) },
        { Run: totals(2, 8300), Golf: totals(1, 5823), Workout: totals(1, 2763) },
      ),
    );

    expect(rows.map((row) => row.sportType)).toEqual(["Run", "Padel", "Walk", "Golf", "Workout"]);
    expect(rows[0].trend).toBe("down");
    expect(rows[1].lastWeek).toBeNull();
    expect(rows[1].trend).toBe("up");
    expect(rows[3].thisWeek).toBeNull();
    expect(rows[3].trend).toBe("down");
  });

  it("breaks ties by sport_type name and marks equal time as flat", () => {
    const rows = activityTypeRows(summary({ Walk: totals(1, 600), Golf: totals(1, 600) }, { Walk: totals(1, 600) }));
    expect(rows.map((row) => row.sportType)).toEqual(["Walk", "Golf"]);
    expect(rows[0].trend).toBe("flat");
  });

  it("returns no rows when both weeks are empty", () => {
    expect(activityTypeRows(summary({}, {}))).toEqual([]);
  });
});

describe("weekTotals", () => {
  it("sums activity count and moving time across sport types", () => {
    const week = summary({ Run: totals(2, 5840), Padel: totals(1, 4285) }, {}).thisWeek;
    expect(weekTotals(week)).toEqual({ activityCount: 3, movingTimeSec: 10125 });
  });
});

describe("sport helpers", () => {
  it("uses an icon per known sport_type and a dot otherwise", () => {
    expect(sportIcon("Padel")).toBe("🎾");
    expect(sportIcon("Pickleball")).toBe("•");
    expect(sportIcon(null)).toBe("•");
  });

  it("recognises run sport types only", () => {
    expect(isRunSport("TrailRun")).toBe(true);
    expect(isRunSport("Walk")).toBe(false);
    expect(isRunSport(null)).toBe(false);
  });

  it("formats durations, pace, and distance", () => {
    expect(formatHoursMinutes(5823)).toBe("1h 37m");
    expect(formatHoursMinutes(3004)).toBe("50m");
    expect(formatPace(311.88)).toBe("5:12/km");
    expect(formatDistanceKm(4349.7)).toBe("4.35 km");
  });
});

describe("activityCardFacts", () => {
  it("shows elapsed time but no pace for a non-run activity", () => {
    const padel = activity({
      sportType: "Padel",
      distanceM: 2508,
      movingTimeSec: 4285,
      elapsedTimeSec: 4968,
      elevationGainM: 0,
      averageHeartrate: 122.7,
      averagePaceSecPerKm: 1708,
    });
    expect(activityCardFacts(padel, false)).toEqual([
      { key: "distance", text: "2.51 km" },
      { key: "moving", text: "⏱ 1h 11m 25s" },
      { key: "elapsed", text: "elapsed 1h 22m 48s" },
      { key: "heartrate", text: "♥ 123" },
    ]);
  });

  it("hides distance when it is zero", () => {
    const workout = activity({ sportType: "Workout", distanceM: 0, movingTimeSec: 2763, elapsedTimeSec: 2763 });
    expect(activityCardFacts(workout, false).map((fact) => fact.key)).toEqual(["moving", "elapsed"]);
  });

  it("shows pace for runs and drops elapsed time and elevation when compact", () => {
    const run = activity({
      sportType: "Run",
      distanceM: 10100,
      movingTimeSec: 3150,
      elapsedTimeSec: 3205,
      elevationGainM: 92,
      averageHeartrate: 148,
      averagePaceSecPerKm: 311.88,
    });
    expect(activityCardFacts(run, true)).toEqual([
      { key: "distance", text: "10.10 km" },
      { key: "moving", text: "⏱ 52m 30s" },
      { key: "pace", text: "5:12/km" },
      { key: "heartrate", text: "♥ 148" },
    ]);
    expect(activityCardFacts(run, false).map((fact) => fact.key)).toEqual([
      "distance",
      "moving",
      "elapsed",
      "pace",
      "elevation",
      "heartrate",
    ]);
  });
});
