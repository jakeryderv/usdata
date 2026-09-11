// One static site; redirect the old docs hostname without changing versioned links.
export default {
  async fetch(request: Request, env: Env): Promise<Response> {
    if (request.method !== "GET" && request.method !== "HEAD") {
      return new Response("Method not allowed", {
        status: 405,
        headers: { Allow: "GET, HEAD" },
      });
    }
    const url = new URL(request.url);
    let redirect = url.hostname === "docs.usdata.dev";
    if (redirect) {
      url.hostname = "usdata.dev";
      url.protocol = "https:";
      url.port = "";
      if (url.pathname === "/") url.pathname = "/start/";
    }
    if (url.pathname === "/latest" || url.pathname.startsWith("/latest/")) {
      const suffix = url.pathname.slice("/latest".length);
      url.pathname =
        suffix === "" || suffix === "/" || suffix === "/index.html"
          ? "/start/"
          : suffix;
      redirect = true;
    }
    if (redirect) return Response.redirect(url.href, 301);
    return env.ASSETS.fetch(request);
  },
} satisfies ExportedHandler<Env>;
