/**
 * Cloudflare Worker entrypoint.
 *
 * The application is served from a path prefix on an existing zone rather than
 * from its own hostname, so this Worker has two jobs: strip that prefix before
 * anything downstream sees it, and split traffic between the FastAPI container
 * and the static frontend bundle.
 *
 * FastAPI is never told about the prefix. It receives `/api/catalog`, exactly
 * as it does when run locally, which keeps one fewer thing different between
 * development and production.
 */
import { Container, getContainer } from '@cloudflare/containers';

/** Path prefix this deployment is mounted under, without a trailing slash. */
const BASE_PATH = '/00000000-0000-0000-0000-000000000000';

/** Prefixes that belong to the backend rather than to static assets. */
const BACKEND_PREFIXES = ['/api/', '/healthz', '/openapi.json', '/docs', '/redoc'] as const;

/**
 * A single logical backend instance.
 *
 * The backend is stateless, so one instance is sufficient and a fixed name
 * keeps warm starts likely. Nothing is lost when it sleeps: run state lives in
 * signed tokens and in GitHub, never on the container's disk.
 */
const INSTANCE_NAME = 'benchmark-backend';

export interface Env {
  BACKEND: DurableObjectNamespace<BackendContainer>;
  ASSETS: Fetcher;
  GITHUB_TOKEN: string;
  TOKEN_SECRET: string;
  USER_KEY_SECRET: string;
  GITHUB_OWNER?: string;
  GITHUB_REPO?: string;
  GITHUB_REF?: string;
  REPO_IS_PUBLIC?: string;
  CORS_ORIGINS?: string;
}

export class BackendContainer extends Container<Env> {
  /** Port uvicorn listens on inside the image. */
  defaultPort = 8000;

  /**
   * Benchmark runs take minutes and the frontend polls throughout, so a short
   * sleep window would evict the container between polls. Nothing breaks if it
   * does - the backend holds no state - but a cold start on every poll is
   * wasteful.
   */
  sleepAfter = '15m';

  /**
   * Secrets arrive as Worker secrets and are handed to the container as
   * environment variables. `pydantic-settings` reads them from there, so the
   * container needs no Cloudflare-specific code.
   */
  envVars = {
    GITHUB_TOKEN: this.env.GITHUB_TOKEN,
    TOKEN_SECRET: this.env.TOKEN_SECRET,
    USER_KEY_SECRET: this.env.USER_KEY_SECRET,
    GITHUB_OWNER: this.env.GITHUB_OWNER ?? 'samypr100',
    GITHUB_REPO: this.env.GITHUB_REPO ?? 'gh-workflow-fiesta',
    GITHUB_REF: this.env.GITHUB_REF ?? 'main',
    REPO_IS_PUBLIC: this.env.REPO_IS_PUBLIC ?? 'false',
    CORS_ORIGINS: this.env.CORS_ORIGINS ?? '[]',
    // Must stay unset-or-zero. When this is truthy, `uv python list
    // --only-downloads` returns an empty array with exit status zero, and the
    // interpreter dropdown is silently empty with nothing in the logs.
    UV_NO_MANAGED_PYTHON: '0',
  };
}

/**
 * Decide whether a prefix-stripped path belongs to the backend.
 *
 * @param pathname Path with the deployment prefix already removed.
 * @returns True when the request should be forwarded to the container.
 */
function isBackendPath(pathname: string): boolean {
  return BACKEND_PREFIXES.some(
    (prefix) => pathname === prefix || pathname.startsWith(prefix),
  );
}

export default {
  async fetch(request: Request, env: Env): Promise<Response> {
    const url = new URL(request.url);

    if (url.pathname !== BASE_PATH && !url.pathname.startsWith(`${BASE_PATH}/`)) {
      return new Response('Not found', { status: 404 });
    }

    // Send a bare visit to the prefix to its canonical trailing-slash form, so
    // relative asset URLs in index.html resolve against the right directory.
    if (url.pathname === BASE_PATH) {
      return Response.redirect(`${url.origin}${BASE_PATH}/${url.search}`, 308);
    }

    const stripped = url.pathname.slice(BASE_PATH.length) || '/';
    const downstream = new URL(url.toString());
    downstream.pathname = stripped;

    if (isBackendPath(stripped)) {
      // `cf-connecting-ip` is added at the edge and survives this hop intact;
      // the backend derives its per-user key from it.
      return getContainer(env.BACKEND, INSTANCE_NAME).fetch(
        new Request(downstream.toString(), request),
      );
    }

    const asset = await env.ASSETS.fetch(new Request(downstream.toString(), request));
    if (asset.status !== 404) {
      return asset;
    }

    // Single-page app: unknown paths fall back to the entry document so client
    // routing works on a hard refresh.
    return env.ASSETS.fetch(new Request(`${url.origin}/index.html`, request));
  },
} satisfies ExportedHandler<Env>;
