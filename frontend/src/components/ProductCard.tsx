import type { Recommendation, InteractionType } from "../types";

interface Props {
  rec: Recommendation;
  onAction: (article_id: number, type: InteractionType) => void;
  busy?: boolean;
}

function Placeholder() {
  return (
    <svg viewBox="0 0 100 100" className="h-full w-full text-neutral-300" fill="currentColor">
      <rect width="100" height="100" fill="#f4f4f5" />
      <path
        d="M20 70 L40 45 L55 60 L70 40 L85 70 Z"
        fill="none"
        stroke="currentColor"
        strokeWidth="2"
      />
      <circle cx="35" cy="30" r="6" fill="none" stroke="currentColor" strokeWidth="2" />
    </svg>
  );
}

export default function ProductCard({ rec, onAction, busy }: Props) {
  const m = rec.metadata;
  const imageUrl = (m.image_url as string | null | undefined) || null;
  const pct = Math.round(rec.similarity * 100);

  return (
    <div className="flex flex-col overflow-hidden rounded-lg border border-neutral-200 bg-white shadow-sm">
      <div className="relative aspect-[3/4] bg-neutral-100">
        {imageUrl ? (
          <img src={imageUrl} alt={m.prod_name} className="h-full w-full object-cover" />
        ) : (
          <Placeholder />
        )}
        <div className="absolute right-2 top-2 rounded-full bg-black/70 px-2 py-0.5 text-xs font-medium text-white">
          {pct}% match
        </div>
      </div>

      <div className="flex flex-1 flex-col gap-1 px-3 py-2">
        <div className="line-clamp-1 text-sm font-medium">{m.prod_name ?? `Article ${rec.article_id}`}</div>
        <div className="line-clamp-1 text-xs text-neutral-500">
          {[m.product_type_name, m.colour_group_name, m.index_group_name]
            .filter(Boolean)
            .join(" · ")}
        </div>

        <div className="mt-2 flex gap-1.5">
          <button
            disabled={busy}
            onClick={() => onAction(rec.article_id, "like")}
            className="flex-1 rounded border border-neutral-300 py-1.5 text-sm hover:border-neutral-900 disabled:opacity-50"
            title="Show me more like this"
          >
            👍
          </button>
          <button
            disabled={busy}
            onClick={() => onAction(rec.article_id, "dislike")}
            className="flex-1 rounded border border-neutral-300 py-1.5 text-sm hover:border-neutral-900 disabled:opacity-50"
            title="Not for me — hide this"
          >
            👎
          </button>
          <button
            disabled={busy}
            onClick={() => onAction(rec.article_id, "cart")}
            className="flex-1 rounded border border-neutral-300 py-1.5 text-sm hover:border-neutral-900 disabled:opacity-50"
            title="Add to cart (demo — nothing is actually purchased)"
          >
            🛒
          </button>
        </div>
      </div>
    </div>
  );
}
