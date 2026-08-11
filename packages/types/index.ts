/**
 * MIRROR OPS — contrat d'API partagé.
 *
 * Miroir exact des schémas Pydantic de `apps/api/app/schemas`.
 * Toute évolution du backend doit être répercutée ici : c'est la seule source
 * de vérité du frontend sur ce que l'API renvoie réellement.
 */

/* ------------------------------------------------------------------ énumérations */

export const OCCASIONS = [
  "interview",
  "presentation",
  "date",
  "business",
  "event",
  // Un même look peut convenir à un dîner et pas à un mariage : chaque
  // occasion porte son propre profil d'exigence.
  "wedding",
  "conference",
  "dinner",
  "travel",
  "other",
] as const;
export type Occasion = (typeof OCCASIONS)[number];

export const GOALS = [
  "confident",
  "professional",
  "approachable",
  "elegant",
  "expressive",
] as const;
export type Goal = (typeof GOALS)[number];

export const TIME_OPTIONS = ["<5m", "5_15m", "15_30m", "30m_plus"] as const;
export type TimeAvailable = (typeof TIME_OPTIONS)[number];

export const CHANGE_ACTIONS = [
  "CHANGE_JACKET",
  "CHANGE_TOP",
  "CHANGE_BOTTOM",
  "CHANGE_SHOES",
  "CHANGE_ACCESSORY",
  "CHANGE_COLOR",
  "REMOVE_ACCESSORY",
  "NO_CHANGE",
] as const;
export type ChangeAction = (typeof CHANGE_ACTIONS)[number];

export const OUTFIT_ELEMENTS = [
  "jacket",
  "top",
  "bottom",
  "shoes",
  "accessories",
] as const;
export type OutfitElement = (typeof OUTFIT_ELEMENTS)[number];

export type ConfidenceLevel = "low" | "medium" | "high";

export type SessionStatus = "active" | "completed" | "expired" | "failed";

export type SessionState =
  | "SESSION_CREATED"
  | "MOMENT_CREATED"
  | "ANALYSIS_COMPLETED"
  | "DECISION_COMPLETED"
  | "VTO_PROCESSING"
  | "VTO_COMPLETED"
  | "SESSION_COMPLETED";

export type VTOStatus = "queued" | "processing" | "completed" | "failed";

/** Ordre canonique du parcours : sert à interdire les sauts d'étape côté client. */
export const STATE_ORDER: Record<SessionState, number> = {
  SESSION_CREATED: 0,
  MOMENT_CREATED: 1,
  ANALYSIS_COMPLETED: 2,
  DECISION_COMPLETED: 3,
  VTO_PROCESSING: 4,
  VTO_COMPLETED: 5,
  SESSION_COMPLETED: 6,
};

/* ----------------------------------------------------------------------- erreurs */

export type ErrorCode =
  | "INVALID_REQUEST"
  | "INVALID_IMAGE"
  | "IMAGE_TOO_LARGE"
  | "IMAGE_UNSUPPORTED"
  | "ANALYSIS_FAILED"
  | "DECISION_FAILED"
  | "VTO_FAILED"
  | "VTO_TIMEOUT"
  | "VTO_NOT_APPLICABLE"
  | "SESSION_EXPIRED"
  | "NOT_FOUND"
  | "INVALID_STATE"
  | "PROVIDER_UNAVAILABLE"
  | "RATE_LIMITED"
  | "INTERNAL_ERROR"
  | "MEDIA_LINK_EXPIRED";

export interface ErrorBody {
  code: ErrorCode | string;
  message: string;
  retryable: boolean;
  request_id?: string | null;
  details?: Record<string, unknown> | null;
}

export interface ErrorEnvelope {
  error: ErrorBody;
}

/* ---------------------------------------------------------------------- sessions */

export interface SessionCreateResponse {
  id: string;
  status: SessionStatus;
  state: SessionState;
  expires_at: string;
}

export interface SessionSummary {
  id: string;
  status: SessionStatus;
  state: SessionState;
  created_at: string;
  expires_at: string;
}

/* ----------------------------------------------------------------------- moments */

export interface MomentCreateRequest {
  session_id: string;
  occasion: Occasion;
  goal: Goal;
  time_available: TimeAvailable;
  note?: string | null;
}

export interface MomentResponse {
  id: string;
  session_id: string;
  occasion: Occasion;
  goal: Goal;
  time_available: TimeAvailable;
  note?: string | null;
}

/* -------------------------------------------------------------------- apparence */

/**
 * Description optionnelle d'une pièce. Tous les champs numériques sont
 * facultatifs : absents, MIRROR OPS applique un a priori neutre ET abaisse sa
 * confiance de décision. Le produit ne prétend jamais avoir mesuré ce qu'il n'a
 * pas mesuré.
 */
export interface OutfitItemIn {
  present: boolean;
  formality?: number | null;
  structure?: number | null;
  color_harmony?: number | null;
  condition?: number | null;
  descriptor?: string | null;
}

export type OutfitIn = Partial<Record<OutfitElement, OutfitItemIn>>;

export interface SkinObservations {
  texture: number | null;
  redness: number | null;
  oiliness: number | null;
  radiance: number | null;
}

export interface ImageQuality {
  score: number;
  brightness: number | null;
  sharpness: number | null;
  resolution_score: number | null;
  full_look_visible: boolean;
}

export interface AppearanceAnalysisResponse {
  analysis_id: string;
  status: string;
  /** 6 dimensions normalisées 0..1 (professional_presence, visual_coherence, …). */
  appearance: Record<string, number>;
  skin: SkinObservations;
  skin_source: string;
  /** `true` quand les observations viennent d'une heuristique locale, pas de YouCam. */
  skin_simulated: boolean;
  element_suitability: Record<string, number>;
  image_quality: ImageQuality;
  data_confidence: number;
  image_url: string | null;
  created_at: string;
}

/* ---------------------------------------------------------------------- décision */

export interface OneChangeEvaluateRequest {
  session_id: string;
  moment_id?: string | null;
  analysis_id?: string | null;
}

export interface Impact {
  /** Scores 0-100 avant le changement, par dimension. */
  before: Record<string, number>;
  /** Scores 0-100 projetés après le changement. */
  after: Record<string, number>;
  /** Les features qui ont réellement porté la décision. */
  dominant_factors: string[];
}

/** Le look convient-il au moment ? La première réponse du produit. */
export type FitState = "FIT" | "ALMOST_THERE" | "MISMATCH";

export interface Fit {
  state: FitState;
  /** 0–100 : à quel point le look actuel convient à CE moment. */
  score: number;
  /** La phrase affichée en premier. */
  headline: string;
  /** Ce qui explique le verdict, en une phrase. */
  detail: string;
  /** L'élément qui tire l'ensemble vers le bas, s'il y en a un. */
  weakest_element: string | null;
}

/** La pièce que la preuve visuelle utilisera. Annoncée, jamais choisie. */
export interface SuggestedGarment {
  id: string;
  name: string;
  category: string;
}

export interface Recommendation {
  id: string;
  action: ChangeAction;
  label: string;
  score: number;
  confidence: ConfidenceLevel;
  reason: string;
  what: string;
  why: string;
  how: string;
  /** Éléments explicitement conservés. */
  keep: string[];
  impact: Impact;
  requires_vto: boolean;
  /**
   * `true` quand la pièce visée était absente : l'interface doit écrire
   * « Add » plutôt que « Change », partout où elle nomme l'intervention.
   * Le verbe vient du backend — jamais d'une lecture du libellé.
   */
  is_addition: boolean;
  /**
   * Le verdict d'adéquation, calculé AVANT le choix du levier :
   * « FIT THE MOMENT » précède « ONE CHANGE ».
   */
  fit: Fit | null;
  /**
   * Ce que « See the difference » montrera. Le produit l'annonce pour être
   * lisible — il ne propose pas d'en choisir un autre : une liste de vêtements
   * à parcourir ferait de MIRROR OPS le catalogue qu'il refuse d'être.
   */
  suggested_garment: SuggestedGarment | null;
}

export interface OneChangeResponse {
  recommendation: Recommendation;
}

/* --------------------------------------------------------------------------- VTO */

export interface VTOGenerateRequest {
  session_id: string;
  recommendation_id?: string | null;
  garment_asset_id?: string | null;
}

export interface VTOResult {
  id: string;
  status: VTOStatus;
  action: ChangeAction;
  garment_id: string;
  provider: string;
  /** `true` quand l'aperçu a été composé localement et NON généré par YouCam. */
  simulated: boolean;
  before_image_url: string | null;
  result_image_url: string | null;
  latency_ms: number | null;
  created_at: string;
}

export interface Garment {
  id: string;
  category: string;
  name: string;
  description: string;
  color: string;
  attributes: Record<string, number>;
  /** `true` tant que le visuel est un aplat généré, pas une photographie. */
  placeholder: boolean;
}

/** Une pièce fournie par l'utilisateur, valable le temps de la session. */
export interface UploadedGarment {
  id: string;
  width: number;
  height: number;
  size_bytes: number;
}

export interface GarmentListResponse {
  garments: Garment[];
}

/* ------------------------------------------------------------- vue d'ensemble */

/** Tout l'écran final en une seule requête : refresh, reprise, démo. */
export interface SessionDetail {
  session: SessionSummary;
  moment: MomentResponse | null;
  analysis: AppearanceAnalysisResponse | null;
  recommendation: Recommendation | null;
  vto: VTOResult | null;
}

/* -------------------------------------------------------------------- santé API */

export interface HealthResponse {
  status: string;
  version: string;
  environment: string;
}

export interface DependencyHealthResponse {
  api: string;
  database: string;
  storage: string;
  youcam: string;
  youcam_mode: "mock" | "live" | string;
}
