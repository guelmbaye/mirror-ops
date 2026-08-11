/**
 * Client d'API MIRROR OPS.
 *
 * Le navigateur ne parle jamais à YouCam : il ne connaît que ce backend.
 * Chaque erreur remonte sous une forme unique, déjà rédigée pour l'utilisateur —
 * l'interface n'a jamais à inventer un message ni à exposer un code technique.
 */

import type {
  AppearanceAnalysisResponse,
  ErrorEnvelope,
  GarmentListResponse,
  Goal,
  MomentResponse,
  Occasion,
  OneChangeResponse,
  OutfitIn,
  SessionCreateResponse,
  SessionDetail,
  TimeAvailable,
  UploadedGarment,
  VTOResult,
} from "@mirror-ops/types";

const BASE =
  process.env.NEXT_PUBLIC_API_BASE_URL?.replace(/\/$/, "") ?? "http://localhost:8000";

const API = `${BASE}/api/v1`;

export class ApiError extends Error {
  readonly code: string;
  readonly retryable: boolean;
  readonly status: number;

  constructor(code: string, message: string, retryable: boolean, status: number) {
    super(message);
    this.name = "ApiError";
    this.code = code;
    this.retryable = retryable;
    this.status = status;
  }
}

/** Le réseau a lâché avant même d'atteindre l'API : on le dit tel quel. */
const OFFLINE = new ApiError(
  "PROVIDER_UNAVAILABLE",
  "We can't reach Mirror Ops right now.",
  true,
  0,
);

async function request<T>(path: string, init: RequestInit = {}): Promise<T> {
  let response: Response;
  try {
    response = await fetch(`${API}${path}`, init);
  } catch {
    throw OFFLINE;
  }

  if (response.status === 204) return undefined as T;

  let payload: unknown = null;
  try {
    payload = await response.json();
  } catch {
    payload = null;
  }

  if (!response.ok) {
    const envelope = payload as ErrorEnvelope | null;
    const body = envelope?.error;
    throw new ApiError(
      body?.code ?? "INTERNAL_ERROR",
      body?.message ?? "Something went wrong on our side.",
      body?.retryable ?? false,
      response.status,
    );
  }

  return payload as T;
}

function json(body: unknown, idempotencyKey?: string): RequestInit {
  const headers: Record<string, string> = { "Content-Type": "application/json" };
  if (idempotencyKey) headers["Idempotency-Key"] = idempotencyKey;
  return { method: "POST", headers, body: JSON.stringify(body) };
}

/* --------------------------------------------------------------- le parcours */

export function createSession(): Promise<SessionCreateResponse> {
  return request<SessionCreateResponse>("/sessions", { method: "POST" });
}

export function createMoment(input: {
  sessionId: string;
  occasion: Occasion;
  goal: Goal;
  timeAvailable: TimeAvailable;
}): Promise<MomentResponse> {
  return request<MomentResponse>(
    "/moments",
    json({
      session_id: input.sessionId,
      occasion: input.occasion,
      goal: input.goal,
      time_available: input.timeAvailable,
    }),
  );
}

export function analyzeAppearance(input: {
  sessionId: string;
  photo: File | Blob;
  outfit?: OutfitIn;
  idempotencyKey?: string;
}): Promise<AppearanceAnalysisResponse> {
  const form = new FormData();
  form.append("session_id", input.sessionId);
  form.append("image", input.photo, "look.jpg");
  if (input.outfit && Object.keys(input.outfit).length > 0) {
    form.append("outfit", JSON.stringify(input.outfit));
  }

  const headers: Record<string, string> = {};
  if (input.idempotencyKey) headers["Idempotency-Key"] = input.idempotencyKey;

  return request<AppearanceAnalysisResponse>("/appearance/analyze", {
    method: "POST",
    headers,
    body: form,
  });
}

export function evaluateOneChange(sessionId: string): Promise<OneChangeResponse> {
  return request<OneChangeResponse>(
    "/one-change/evaluate",
    json({ session_id: sessionId }),
  );
}

export function generateVTO(input: {
  sessionId: string;
  garmentAssetId?: string;
  idempotencyKey?: string;
}): Promise<VTOResult> {
  return request<VTOResult>(
    "/vto/generate",
    json(
      {
        session_id: input.sessionId,
        garment_asset_id: input.garmentAssetId ?? null,
      },
      input.idempotencyKey,
    ),
  );
}

/**
 * Téléverse une pièce que la personne veut essayer.
 *
 * Le catalogue existe pour que le parcours ne s'arrête jamais ; ceci existe
 * parce que quelqu'un qui hésite devant une veste précise a une bien meilleure
 * raison de vouloir la voir sur lui. L'identifiant renvoyé s'utilise tel quel
 * comme `garmentAssetId`.
 */
export function uploadGarment(input: {
  sessionId: string;
  photo: File | Blob;
}): Promise<UploadedGarment> {
  const form = new FormData();
  form.append("session_id", input.sessionId);
  form.append("image", input.photo, "garment.jpg");
  return request<UploadedGarment>("/garments/upload", { method: "POST", body: form });
}

export function getSessionDetail(sessionId: string): Promise<SessionDetail> {
  return request<SessionDetail>(`/sessions/${sessionId}`, { cache: "no-store" });
}

export function listGarments(category?: string): Promise<GarmentListResponse> {
  const query = category ? `?category=${encodeURIComponent(category)}` : "";
  return request<GarmentListResponse>(`/garments${query}`);
}
