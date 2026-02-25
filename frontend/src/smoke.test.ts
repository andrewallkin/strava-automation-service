import { describe, expect, it } from "vitest";

describe("frontend smoke", () => {
  it("runs tests in container", () => {
    expect(1 + 1).toBe(2);
  });
});
