import type {
  CatalogResponse,
  CreateRunResponse,
  InterpretersResponse,
  RunStatusResponse,
  RunnersResponse,
  SelectionRequest,
} from './types';

export type ApiErrorKind = 'duplicate' | 'rate_limited' | 'rejected' | 'network' | 'server';

export class ApiError extends Error {
  readonly kind: ApiErrorKind;
  readonly retryAfterSeconds: number;

  constructor(kind: ApiErrorKind, message: string, retryAfterSeconds = 0) {
    super(message);
    this.name = 'ApiError';
    this.kind = kind;
    this.retryAfterSeconds = retryAfterSeconds;
  }
}

export type FetchLike = (url: string, init?: RequestInit) => Promise<Response>;

export interface ApiClient {
  catalog(): Promise<CatalogResponse>;
  interpreters(): Promise<InterpretersResponse>;
  runners(): Promise<RunnersResponse>;
  createRun(selections: readonly SelectionRequest[]): Promise<CreateRunResponse>;
  runStatus(runToken: string): Promise<RunStatusResponse>;
}

function kindFor(status: number): ApiErrorKind {
  if (status === 409) return 'duplicate';
  if (status === 429) return 'rate_limited';
  if (status >= 400 && status < 500) return 'rejected';
  return 'server';
}

async function detailOf(response: Response): Promise<string> {
  try {
    const body = (await response.json()) as { detail?: unknown };
    return typeof body.detail === 'string' ? body.detail : response.statusText;
  } catch {
    return response.statusText;
  }
}

export function createClient(baseUrl: string, fetchImpl: FetchLike = fetch): ApiClient {
  async function request<T>(path: string, init?: RequestInit): Promise<T> {
    let response: Response;
    try {
      response = await fetchImpl(`${baseUrl}${path}`, init);
    } catch (error) {
      throw new ApiError('network', error instanceof Error ? error.message : 'request failed');
    }

    if (!response.ok) {
      const retryAfter = Number(response.headers.get('retry-after') ?? '0');
      throw new ApiError(
        kindFor(response.status),
        await detailOf(response),
        Number.isFinite(retryAfter) ? retryAfter : 0,
      );
    }
    return (await response.json()) as T;
  }

  return {
    catalog: () => request<CatalogResponse>('/api/catalog'),
    interpreters: () => request<InterpretersResponse>('/api/interpreters'),
    runners: () => request<RunnersResponse>('/api/runners'),
    createRun: (selections) =>
      request<CreateRunResponse>('/api/runs', {
        method: 'POST',
        headers: { 'content-type': 'application/json' },
        body: JSON.stringify({ selections }),
      }),
    runStatus: (runToken) => request<RunStatusResponse>(`/api/runs/${runToken}`),
  };
}
