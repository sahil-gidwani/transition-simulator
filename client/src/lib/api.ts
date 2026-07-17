export const API_BASE: string = import.meta.env.VITE_API_BASE ?? '/api';

export interface Health {
  status: string;
  version: string;
}

export async function getHealth(): Promise<Health> {
  const res = await fetch(`${API_BASE}/health`);
  if (!res.ok) {
    throw new Error(`Health check failed: ${res.status}`);
  }
  return (await res.json()) as Health;
}
