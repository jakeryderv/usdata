// The application owns the apex; documentation paths keep working after the split.
const docsPaths =
  /^\/(?:docs|examples|start|latest|0\.10\.0|project|CONTRIBUTING|CHANGELOG|SECURITY|changes)(?:\/|$|\.html$)/;

export default {
  async fetch(request: Request, env: Env): Promise<Response> {
    if (request.method !== "GET" && request.method !== "HEAD") {
      return new Response("Method not allowed", {
        status: 405,
        headers: { Allow: "GET, HEAD" },
      });
    }
    const url = new URL(request.url);
    if (docsPaths.test(url.pathname) || url.pathname === "/LICENSE") {
      url.hostname = "docs.usdata.dev";
      url.protocol = "https:";
      url.port = "";
      // Do not persist a second set of opposite permanent redirects during migration.
      return new Response(null, {
        status: 302,
        headers: { Location: url.href, "Cache-Control": "no-store" },
      });
    }
    return env.ASSETS.fetch(request);
  },
} satisfies ExportedHandler<Env>;
