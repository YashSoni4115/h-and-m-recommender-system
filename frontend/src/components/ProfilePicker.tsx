import { useQuery, useMutation } from "@tanstack/react-query";
import { api } from "../api";
import type { Profile } from "../types";

interface Props {
  onPicked: (p: Profile) => void;
}

export default function ProfilePicker({ onPicked }: Props) {
  const catsQ = useQuery({ queryKey: ["categories"], queryFn: api.listCategories });
  const presetsQ = useQuery({ queryKey: ["presets"], queryFn: api.listPresets });

  const forkCat = useMutation({
    mutationFn: (c: string) => api.forkByCategory(c),
    onSuccess: onPicked,
  });
  const forkPreset = useMutation({
    mutationFn: (id: string) => api.forkByPreset(id),
    onSuccess: onPicked,
  });
  const forkGlobal = useMutation({
    mutationFn: () => api.forkGlobal(),
    onSuccess: onPicked,
  });

  const busy = forkCat.isPending || forkPreset.isPending || forkGlobal.isPending;

  return (
    <div className="mx-auto max-w-3xl px-6 py-16">
      <h1 className="text-3xl font-semibold tracking-tight">Start shopping</h1>
      <p className="mt-2 text-neutral-600">
        Pick a starting point. Your profile will drift as you like, dislike, and add items to
        your (fake) cart.
      </p>

      {presetsQ.data && presetsQ.data.length > 0 && (
        <section className="mt-10">
          <h2 className="text-sm font-medium uppercase tracking-wider text-neutral-500">
            Pick a persona
          </h2>
          <div className="mt-3 flex flex-wrap gap-2">
            {presetsQ.data.map((p) => (
              <button
                key={p.id}
                disabled={busy}
                onClick={() => forkPreset.mutate(p.id)}
                className="rounded-full border border-neutral-300 bg-white px-4 py-2 text-sm hover:border-neutral-900 disabled:opacity-50"
              >
                {p.name ?? p.id.slice(0, 8)}
              </button>
            ))}
          </div>
        </section>
      )}

      <section className="mt-10">
        <h2 className="text-sm font-medium uppercase tracking-wider text-neutral-500">
          Or start fresh — pick a section
        </h2>
        {catsQ.isLoading && <p className="mt-3 text-neutral-500">Loading…</p>}
        {catsQ.error && (
          <p className="mt-3 text-red-600">Couldn't reach the backend. Is it running?</p>
        )}
        <div className="mt-3 flex flex-wrap gap-2">
          {catsQ.data?.map((c) => (
            <button
              key={c.index_group_name}
              disabled={busy}
              onClick={() => forkCat.mutate(c.index_group_name)}
              className="rounded-full border border-neutral-300 bg-white px-4 py-2 text-sm hover:border-neutral-900 disabled:opacity-50"
            >
              {c.index_group_name}
              <span className="ml-2 text-xs text-neutral-500">{c.item_count.toLocaleString()}</span>
            </button>
          ))}
        </div>
      </section>

      <section className="mt-10">
        <button
          disabled={busy}
          onClick={() => forkGlobal.mutate()}
          className="text-sm text-neutral-500 underline underline-offset-4 hover:text-neutral-900 disabled:opacity-50"
        >
          Or just show me what everyone's into
        </button>
      </section>
    </div>
  );
}
