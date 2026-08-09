import { useState } from "react";
import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { api } from "../api";
import type { InteractionType, Profile } from "../types";
import { useDebounce } from "../hooks/useDebounce";
import ProductCard from "./ProductCard";

interface Props {
  profileId: string;
  onSwitchProfile: () => void;
}

export default function ProductGrid({ profileId, onSwitchProfile }: Props) {
  const qc = useQueryClient();
  const [toast, setToast] = useState<string | null>(null);
  const [rawQuery, setRawQuery] = useState("");
  const query = useDebounce(rawQuery.trim(), 300);
  const searching = query.length > 0;

  const profQ = useQuery({
    queryKey: ["profile", profileId],
    queryFn: () => api.getProfile(profileId),
  });
  const recsQ = useQuery({
    queryKey: ["recs", profileId],
    queryFn: () => api.getRecommendations(profileId, 24),
    enabled: !searching,
  });
  const searchQ = useQuery({
    queryKey: ["search", profileId, query],
    queryFn: () => api.search(profileId, query, 24),
    enabled: searching,
  });

  const interact = useMutation({
    mutationFn: ({ article_id, type }: { article_id: number; type: InteractionType }) =>
      api.addInteraction(profileId, article_id, type),
    onSuccess: (_data, vars) => {
      qc.invalidateQueries({ queryKey: ["recs", profileId] });
      qc.invalidateQueries({ queryKey: ["search", profileId] });
      qc.invalidateQueries({ queryKey: ["profile", profileId] });
      if (vars.type === "cart") {
        setToast("Added to cart — this is a demo, nothing is actually purchased.");
        setTimeout(() => setToast(null), 3000);
      }
    },
  });

  const reset = useMutation({
    mutationFn: () => api.resetProfile(profileId),
    onSuccess: (p: Profile) => {
      qc.setQueryData(["profile", profileId], p);
      qc.invalidateQueries({ queryKey: ["recs", profileId] });
      qc.invalidateQueries({ queryKey: ["search", profileId] });
    },
  });

  const switchProf = useMutation({
    mutationFn: () => api.deleteProfile(profileId),
    onSettled: onSwitchProfile,
  });

  const seed = profQ.data?.seed_source ?? "loading…";
  const seedLabel = seed.startsWith("category:")
    ? seed.slice("category:".length)
    : seed.startsWith("preset:")
    ? "Persona"
    : seed === "global"
    ? "Everyone"
    : seed;

  const activeQ = searching ? searchQ : recsQ;

  return (
    <div className="min-h-full">
      <header className="sticky top-0 z-10 border-b border-neutral-200 bg-white/80 backdrop-blur">
        <div className="mx-auto flex max-w-7xl flex-wrap items-center justify-between gap-4 px-6 py-3">
          <div>
            <div className="text-xs uppercase tracking-wider text-neutral-500">Profile</div>
            <div className="text-sm font-medium">
              {seedLabel}
              <span className="ml-2 text-neutral-500">
                · {profQ.data?.interaction_count ?? 0} interactions
              </span>
            </div>
          </div>

          <div className="relative flex-1 min-w-[200px] max-w-md">
            <input
              value={rawQuery}
              onChange={(e) => setRawQuery(e.target.value)}
              placeholder="Search products…"
              className="w-full rounded-full border border-neutral-300 bg-white px-4 py-1.5 pr-8 text-sm outline-none focus:border-neutral-900"
            />
            {rawQuery && (
              <button
                onClick={() => setRawQuery("")}
                className="absolute right-2 top-1/2 -translate-y-1/2 text-neutral-400 hover:text-neutral-900"
                aria-label="Clear search"
              >
                ✕
              </button>
            )}
          </div>

          <div className="flex items-center gap-2">
            <button
              onClick={() => reset.mutate()}
              disabled={reset.isPending}
              className="rounded border border-neutral-300 px-3 py-1.5 text-sm hover:border-neutral-900 disabled:opacity-50"
            >
              Refresh profile
            </button>
            <button
              onClick={() => {
                if (confirm("Delete this profile and pick a new one?")) switchProf.mutate();
              }}
              disabled={switchProf.isPending}
              className="rounded bg-neutral-900 px-3 py-1.5 text-sm text-white hover:bg-neutral-700 disabled:opacity-50"
            >
              Switch profile
            </button>
          </div>
        </div>

        {searching && (
          <div className="mx-auto max-w-7xl px-6 pb-2 text-xs text-neutral-500">
            Showing search results for “{query}” — ranked by match to your profile.
          </div>
        )}
      </header>

      <main className="mx-auto max-w-7xl px-6 py-6">
        {activeQ.isLoading && <p className="text-neutral-500">Loading…</p>}
        {activeQ.error && (
          <p className="text-red-600">Failed to load. Backend up?</p>
        )}
        {activeQ.data && activeQ.data.length === 0 && (
          <p className="text-neutral-500">
            {searching ? `No products match “${query}”.` : "No recommendations yet."}
          </p>
        )}
        {activeQ.data && activeQ.data.length > 0 && (
          <div className="grid grid-cols-2 gap-4 sm:grid-cols-3 md:grid-cols-4 lg:grid-cols-5 xl:grid-cols-6">
            {activeQ.data.map((r) => (
              <ProductCard
                key={r.article_id}
                rec={r}
                busy={interact.isPending}
                onAction={(article_id, type) => interact.mutate({ article_id, type })}
              />
            ))}
          </div>
        )}
      </main>

      {toast && (
        <div className="fixed bottom-6 left-1/2 -translate-x-1/2 rounded-lg bg-neutral-900 px-4 py-2 text-sm text-white shadow-lg">
          {toast}
        </div>
      )}
    </div>
  );
}
