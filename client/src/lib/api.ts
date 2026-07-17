import type {
  DestinationsResponse,
  Health,
  PercentilesResponse,
  PlayerProfile,
  PlayerSearchResult,
  SimulationRequest,
  SimulationResponse,
} from './types';

export const API_BASE: string = import.meta.env.VITE_API_BASE ?? '/api';

/** Every server error carries `{"error": {code, message, detail}}`; this preserves it. */
export class ApiError extends Error {
  readonly status: number;
  readonly code: string;
  readonly detail: unknown;

  constructor(status: number, code: string, message: string, detail: unknown = null) {
    super(message);
    this.name = 'ApiError';
    this.status = status;
    this.code = code;
    this.detail = detail;
  }
}

interface ErrorEnvelope {
  error: { code: string; message: string; detail?: unknown };
}

function isErrorEnvelope(body: unknown): body is ErrorEnvelope {
  if (typeof body !== 'object' || body === null || !('error' in body)) return false;
  const error = (body as { error: unknown }).error;
  return (
    typeof error === 'object' &&
    error !== null &&
    typeof (error as { code?: unknown }).code === 'string' &&
    typeof (error as { message?: unknown }).message === 'string'
  );
}

async function apiFetch<T>(path: string, init?: RequestInit): Promise<T> {
  let res: Response;
  try {
    res = await fetch(`${API_BASE}${path}`, init);
  } catch {
    throw new ApiError(0, 'network', 'Could not reach the Precedent API');
  }
  if (!res.ok) {
    let body: unknown = null;
    try {
      body = await res.json();
    } catch {
      // non-JSON error body; fall through to the generic ApiError
    }
    if (isErrorEnvelope(body)) {
      throw new ApiError(
        res.status,
        body.error.code,
        body.error.message,
        body.error.detail ?? null,
      );
    }
    throw new ApiError(res.status, 'unknown', `Request failed (${res.status})`);
  }
  return (await res.json()) as T;
}

export function getHealth(): Promise<Health> {
  return apiFetch('/health');
}

export function searchPlayers(q: string): Promise<PlayerSearchResult[]> {
  return apiFetch(`/players/search?q=${encodeURIComponent(q)}`);
}

export function getPlayer(id: number): Promise<PlayerProfile> {
  return apiFetch(`/players/${id}`);
}

export function getPlayerPercentiles(id: number): Promise<PercentilesResponse> {
  return apiFetch(`/players/${id}/percentiles`);
}

export function getDestinations(): Promise<DestinationsResponse> {
  return apiFetch('/destinations');
}

export function postSimulation(req: SimulationRequest): Promise<SimulationResponse> {
  return apiFetch('/simulations', {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify(req),
  });
}
