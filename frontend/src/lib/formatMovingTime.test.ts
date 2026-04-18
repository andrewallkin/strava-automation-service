import { describe, expect, it } from "vitest";

import { formatMovingTime } from "./formatMovingTime";

describe("formatMovingTime", () => {
  it.each([
    [0, "0s"],
    [59, "59s"],
    [60, "1m"],
    [90, "1m 30s"],
    [3600, "1h"],
    [3661, "1h 1m 1s"],
    [4894, "1h 21m 34s"],
    [5074, "1h 24m 34s"],
  ] as const)("formatMovingTime(%s) === %s", (seconds, expected) => {
    expect(formatMovingTime(seconds)).toBe(expected);
  });

  it("truncates fractional seconds like integer division", () => {
    expect(formatMovingTime(3661.7)).toBe("1h 1m 1s");
  });
});
