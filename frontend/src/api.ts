import type { Category, InteractionType, Profile, Recommendation } from "./types";

const BASE = import.meta.env.VITE_API_URL || "http://localhost:8000";

async function req<T>(method: string, path: string, body?: unknown): Promise<T> {
  const res = await fetch(BASE + path, {
    method,
    headers: body ? { "Content-Type": "application/json" } : undefined,
    body: body ? JSON.stringify(body) : undefined,
  });
  if (!res.ok) {
    const text = await res.text();
    throw new Error(`${res.status} ${res.statusText}: ${text}`);
  }
  if (res.status === 204) return undefined as T;
  const ct = res.headers.get("content-type") || "";
  return ct.includes("application/json") ? ((await res.json()) as T) : (undefined as T);
}

export const api = {
  listCategories: () => req<Category[]>("GET", "/profiles/categories"),
  listPresets: () => req<Profile[]>("GET", "/profiles/presets"),
  forkByCategory: (category: string) =>
    req<Profile>("POST", `/profiles/fork?category=${encodeURIComponent(category)}`),
  forkByPreset: (preset_id: string) =>
    req<Profile>("POST", `/profiles/fork?preset_id=${encodeURIComponent(preset_id)}`),
  forkGlobal: () => req<Profile>("POST", "/profiles/fork"),
  getProfile: (id: string) => req<Profile>("GET", `/profiles/${id}`),
  getRecommendations: (id: string, limit = 24) =>
    req<Recommendation[]>("GET", `/profiles/${id}/recommendations?limit=${limit}`),
  addInteraction: (id: string, article_id: number, type: InteractionType) =>
    req<{ ok: true }>("POST", `/profiles/${id}/interactions`, { article_id, type }),
  resetProfile: (id: string) => req<Profile>("POST", `/profiles/${id}/reset`),
  deleteProfile: (id: string) => req<void>("DELETE", `/profiles/${id}`),
  search: (id: string, q: string, limit = 24) =>
    req<Recommendation[]>(
      "GET",
      `/profiles/${id}/search?q=${encodeURIComponent(q)}&limit=${limit}`
    ),
};
