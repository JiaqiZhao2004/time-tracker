/**
 * API service functions for fetching and posting time tracker entries
 */
import type { Category } from "../types/category";

export type Entry = {
  id: string;
  categoryId: string;
  categoryNameSnapshot: string;
  timestamp: string;
};

export type EntriesLocalResponse = {
  prevEntryCategoryId: string | null;
  entries: Entry[];
};

const API_BASE = import.meta.env.VITE_API_BASE ?? "http://localhost:8000";
const USER_ID = "roy";

const errorMessage = async (response: Response, fallback: string): Promise<string> => {
  try {
    const data: unknown = await response.json();
    if (
      typeof data === "object" &&
      data !== null &&
      "detail" in data &&
      typeof data.detail === "string"
    ) {
      return data.detail;
    }
  } catch {
    // Use the friendly fallback when the response is not JSON.
  }
  return fallback;
};

export const fetchCategories = async (): Promise<Category[]> => {
  const params = new URLSearchParams({ user_id: USER_ID });
  const response = await fetch(`${API_BASE}/categories?${params.toString()}`);

  if (!response.ok) {
    throw new Error(await errorMessage(response, "Failed to load categories"));
  }

  return response.json();
};

/**
 * Posts a new category entry to the API
 */
export const postEntry = async (
  categoryId: string,
  timestamp: string,
): Promise<Entry> => {
  const response = await fetch(`${API_BASE}/entries`, {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({ user_id: USER_ID, categoryId, timestamp }),
  });

  if (!response.ok) {
    throw new Error(await errorMessage(response, "Failed to save entry"));
  }

  return response.json();
};

/**
 * Fetches entries for a specific local day with timezone
 */
export const fetchEntriesLocal = async (
  timezone: string,
  date: string,
): Promise<EntriesLocalResponse> => {
  const params = new URLSearchParams({ user_id: USER_ID, timezone, date });
  const response = await fetch(
    `${API_BASE}/entries-local?${params.toString()}`,
  );

  if (!response.ok) {
    throw new Error(await errorMessage(response, "Failed to load entries"));
  }

  return response.json();
};
