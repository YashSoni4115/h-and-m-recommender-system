export type InteractionType = "like" | "cart" | "dislike";

export interface Category {
  index_group_name: string;
  item_count: number;
}

export interface Profile {
  id: string;
  name: string | null;
  is_preset: boolean;
  seed_source: string | null;
  forked_from: string | null;
  interaction_count: number;
}

export interface ProductMetadata {
  prod_name?: string;
  product_type_name?: string;
  colour_group_name?: string;
  index_group_name?: string;
  detail_desc?: string;
  image_url?: string | null;
  [k: string]: unknown;
}

export interface Recommendation {
  article_id: number;
  similarity: number;
  metadata: ProductMetadata;
}
