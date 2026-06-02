export type TarotOrientation = 'upright' | 'reversed';

export type DivinationStatus =
  | 'drawing'
  | 'draw_complete'
  | 'reading_ready'
  | 'error';

export type SpreadId = 'three-card' | 'celtic-cross' | 'seven-planets' | string;

export interface ApiErrorPayload {
  error: {
    code: string;
    message: string;
  };
}

export interface SpreadSummary {
  id: SpreadId;
  name: string;
  subtitle: string;
  description: string;
  card_count: number;
  premium_reserved: boolean;
}

export interface SpreadPosition {
  index: number;
  key: string;
  name: string;
  description: string;
}

export interface SpreadDetail extends SpreadSummary {
  positions: SpreadPosition[];
}

export interface TarotCardMeta {
  id: string;
  name_cn: string;
  arcana_type: 'major' | 'minor';
  suit: string | null;
  element: string | null;
}

export interface DrawnCard {
  position_index: number;
  position_name: string;
  card: TarotCardMeta;
  orientation: TarotOrientation;
  cover_image_url: string;
  face_image_url: string;
}

export interface ReadingCard {
  position_name: string;
  card_name: string;
  orientation: TarotOrientation;
  core_meaning: string;
  analysis: string;
}

export interface ReadingResult {
  title: string;
  opening_message: string;
  question: string;
  cards: ReadingCard[];
  overall_analysis: string;
  energy_flow: string;
  conflict_and_harmony: string;
  timing_hint: string;
  action_advice: string;
  long_term_advice: string;
}

export interface GetSpreadsResponse {
  items: SpreadSummary[];
}

export interface CreateDivinationRequest {
  question: string;
  spread_id: SpreadId;
}

export interface CreateDivinationResponse {
  session_id: string;
  status: 'drawing';
  question: string;
  spread: SpreadSummary;
  positions: SpreadPosition[];
  remaining_count: number;
  expires_at: string;
}

export interface DrawCardRequest {
  client_draw_index?: number;
}

export interface DrawCardResponse {
  session_id: string;
  status: 'drawing' | 'draw_complete';
  current_position_index: number;
  next_position_index: number | null;
  remaining_count: number;
  drawn_card: DrawnCard;
  all_cards_drawn: boolean;
}

export interface GenerateReadingResponse {
  session_id: string;
  status: 'reading_ready';
  reading: ReadingResult;
}

export interface GetDivinationSessionResponse {
  session_id: string;
  status: DivinationStatus;
  question: string;
  spread_id: SpreadId;
  spread: SpreadSummary;
  positions: SpreadPosition[];
  drawn_cards: DrawnCard[];
  remaining_count: number;
  reading: ReadingResult | null;
  expires_at: string;
}

export interface HealthResponse {
  status: 'ok';
  service: string;
  mode: 'mock' | string;
}
