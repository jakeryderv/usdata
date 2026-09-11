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
    const repositoryFiles: Record<string, string> = {
      CONTRIBUTING: "CONTRIBUTING.md",
      SECURITY: "SECURITY.md",
      LICENSE: "LICENSE",
      changes: "changes/README.md",
    };
    const policy = url.pathname.match(
      /^\/(CONTRIBUTING|SECURITY|LICENSE|changes)(?:\/|\/index\.html|\.html)?$/,
    );
    if (policy) {
      const target = new URL(
        `https://github.com/jakeryderv/usdata/blob/main/${repositoryFiles[policy[1]]}`,
      );
      target.search = url.search;
      return new Response(null, {
        status: 302,
        headers: { Location: target.href, "Cache-Control": "no-store" },
      });
    }
    if (url.pathname !== new URL(request.url).pathname) {
      return new Response(null, {
        status: 302,
        headers: { Location: url.href, "Cache-Control": "no-store" },
      });
    }
    return env.ASSETS.fetch(request);
  },
} satisfies ExportedHandler<DocsEnv>;
