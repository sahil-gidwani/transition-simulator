import { afterEach, describe, expect, it, vi } from 'vitest';
import { ApiError, getHealth, postSimulation, searchPlayers } from './api';

function jsonResponse(body: unknown, status = 200): Response {
  return {
    ok: status >= 200 && status < 300,
    status,
    json: () => Promise.resolve(body),
  } as Response;
}

function nonJsonResponse(status: number): Response {
  return {
    ok: false,
    status,
    json: () => Promise.reject(new SyntaxError('not json')),
  } as Response;
}

afterEach(() => {
  vi.unstubAllGlobals();
});

describe('apiFetch (via endpoint wrappers)', () => {
  it('returns parsed JSON on success', async () => {
    const results = [{ player_id: 1, name: 'Test' }];
    const fetchMock = vi.fn().mockResolvedValue(jsonResponse(results));
    vi.stubGlobal('fetch', fetchMock);

    await expect(searchPlayers('te st')).resolves.toEqual(results);
    expect(fetchMock).toHaveBeenCalledWith('/api/players/search?q=te%20st', undefined);
  });

  it('throws ApiError carrying the server error envelope', async () => {
    vi.stubGlobal(
      'fetch',
      vi.fn().mockResolvedValue(
        jsonResponse(
          {
            error: {
              code: 'player_without_value',
              message: 'No valuation on record',
              detail: null,
            },
          },
          409,
        ),
      ),
    );

    const err = await getHealth().catch((e: unknown) => e);
    expect(err).toBeInstanceOf(ApiError);
    expect(err).toMatchObject({
      status: 409,
      code: 'player_without_value',
      message: 'No valuation on record',
    });
  });

  it("throws ApiError with code 'unknown' for non-JSON error bodies", async () => {
    vi.stubGlobal('fetch', vi.fn().mockResolvedValue(nonJsonResponse(500)));

    const err = await getHealth().catch((e: unknown) => e);
    expect(err).toBeInstanceOf(ApiError);
    expect(err).toMatchObject({ status: 500, code: 'unknown' });
  });

  it("throws ApiError with code 'network' when fetch itself fails", async () => {
    vi.stubGlobal('fetch', vi.fn().mockRejectedValue(new TypeError('Failed to fetch')));

    const err = await getHealth().catch((e: unknown) => e);
    expect(err).toBeInstanceOf(ApiError);
    expect(err).toMatchObject({ status: 0, code: 'network' });
  });

  it('POSTs simulations as JSON', async () => {
    const fetchMock = vi.fn().mockResolvedValue(jsonResponse({ narrative: 'x' }));
    vi.stubGlobal('fetch', fetchMock);

    await postSimulation({ player_id: 7, destination: { league_id: 'GB1', club_id: 985 } });

    expect(fetchMock).toHaveBeenCalledWith('/api/simulations', {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ player_id: 7, destination: { league_id: 'GB1', club_id: 985 } }),
    });
  });
});
