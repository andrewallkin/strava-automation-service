import { afterEach, describe, expect, it, vi } from "vitest";

import {
  createCoachLinkCode,
  fetchCoachSettings,
  updateCoachSettings,
} from "./api";

describe("coach api helpers", () => {
  afterEach(() => {
    vi.restoreAllMocks();
  });

  it("fetches coach settings", async () => {
    const mockResponse = {
      vector_store_id: "vs_1",
      agent_name: "Coach",
      agent_instructions: "Help me train",
      openai_model: "gpt-4.1-mini",
      telegram_user_id: 123,
      telegram_linked: true,
    };
    vi.stubGlobal(
      "fetch",
      vi.fn().mockResolvedValue({
        ok: true,
        status: 200,
        json: async () => mockResponse,
      }),
    );

    await expect(fetchCoachSettings()).resolves.toEqual(mockResponse);
  });

  it("updates coach settings", async () => {
    const next = {
      vector_store_id: "vs_2",
      agent_name: "My Coach",
      agent_instructions: "Be direct",
      openai_model: "gpt-4.1-mini",
      telegram_user_id: null,
      telegram_linked: false,
    };
    vi.stubGlobal(
      "fetch",
      vi.fn().mockResolvedValue({
        ok: true,
        status: 200,
        json: async () => next,
      }),
    );

    await expect(updateCoachSettings({ vector_store_id: "vs_2" })).resolves.toEqual(next);
  });

  it("creates a coach link code", async () => {
    vi.stubGlobal(
      "fetch",
      vi.fn().mockResolvedValue({
        ok: true,
        status: 200,
        json: async () => ({ code: "ABC123", expires_in_seconds: 600 }),
      }),
    );

    await expect(createCoachLinkCode()).resolves.toEqual({
      code: "ABC123",
      expires_in_seconds: 600,
    });
  });
});
