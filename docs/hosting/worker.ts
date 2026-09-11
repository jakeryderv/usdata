export default {
  async fetch(request: Request, env: DocsEnv): Promise<Response> {
    if (request.method !== "GET" && request.method !== "HEAD") {
      return new Response("Method not allowed", {
        status: 405,
        headers: { Allow: "GET, HEAD" },
      });
    }
    const url = new URL(request.url);
    // There is one current documentation set. Retired versions resolve into it.
    const path =
      url.pathname.replace(/^\/(?:latest|0\.10\.0)(?=\/|$)/, "") || "/";
    url.pathname =
      /^\/(?:start|docs)(?:\/|\/index\.html|\.html)?$/.test(path) ||
      path === "/index.html"
        ? "/"
        : path;
    if (url.pathname !== new URL(request.url).pathname) {
      return new Response(null, {
        status: 302,
        headers: { Location: url.href, "Cache-Control": "no-store" },
      });
    }
    return env.ASSETS.fetch(request);
  },
} satisfies ExportedHandler<DocsEnv>;
