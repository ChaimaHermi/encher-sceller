/** Types alignés avec backend_api */

export interface ImageModel {
  filename: string;
  original_name: string;
  local_path: string;
  mime_type: string;
}

export interface BlockchainModel {
  auction_address?: string | null;
  tx_hash?: string | null;
}

export interface Listing {
  listing_id: string;
  seller_id: string;
  image: ImageModel;
  status: string;
  pipeline_phase: number;
  created_at: string;
  updated_at: string;
  ai_analysis?: Record<string, unknown> | null;
  price_estimation?: Record<string, unknown> | null;
  generated_post?: Record<string, unknown> | null;
  blockchain: BlockchainModel;
}
