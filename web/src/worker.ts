import { compare, readCatalog, safePath, type Catalog } from "./catalog";
import { synchronize } from "./import";
const selector = `document.addEventListener('change', e => {if(e.target.id !== 'docs-version') return; const parts = location.pathname.split('/'); const previous=parts[1]; parts[1]=e.target.value; location.href=parts.join('/')+'?from='+encodeURIComponent(previous);});`;
function redirect(url: string): Response {
  return new Response(null, {
    status: 302,
    headers: { Location: url, "Cache-Control": "no-store" },
  });
}
function banner(catalog: Catalog, version: string, missing: boolean): string {
  const versions = Object.keys(catalog.versions).sort((a, b) => compare(b, a));
  const control =
    versions.length > 1
      ? `<label>Version <select id="docs-version" aria-label="Documentation version">${versions.map((v) => `<option value="${v}"${v === version ? " selected" : ""}>${v}${v === catalog.current ? " (current)" : ""}</option>`).join("")}</select></label>`
      : `Documentation ${version}`;
  return `<aside aria-label="Documentation release" style="padding:12px 20px;border-bottom:1px solid #8885;font-size:14px">${control} ${version !== catalog.current ? `— Older version. <a href="/${catalog.current}/">Read current docs</a>.` : ""}${missing ? " The requested page is unavailable in this version; showing its start page." : ""}</aside>`;
}
export async function serve(
  request: Request,
  env: Env,
  ctx: ExecutionContext,
): Promise<Response> {
  if (!["GET", "HEAD"].includes(request.method))
    return new Response("Method not allowed", {
      status: 405,
      headers: { Allow: "GET, HEAD" },
    });
  const url = new URL(request.url);
  if (url.pathname === "/version-selector.js")
    return new Response(request.method === "HEAD" ? null : selector, {
      headers: {
        "Content-Type": "text/javascript; charset=utf-8",
        "Cache-Control": "no-cache",
      },
    });
  const { catalog } = await readCatalog(env.DOCS);
  if (url.pathname === "/versions.json")
    return Response.json(
      {
        current: catalog.current,
        versions: Object.keys(catalog.versions).sort((a, b) => compare(b, a)),
      },
      { headers: { "Cache-Control": "no-store" } },
    );
  if (!catalog.current)
    return new Response(
      "Documentation is being prepared. Please try again shortly.",
      {
        status: 503,
        headers: { "Retry-After": "60", "Cache-Control": "no-store" },
      },
    );
  if (
    url.pathname === "/" ||
    url.pathname === "/latest" ||
    url.pathname.startsWith("/latest/")
  ) {
    return redirect(
      `/${catalog.current}/${url.pathname.startsWith("/latest/") ? url.pathname.slice(8) : ""}${url.search}`,
    );
  }
  let decoded: string;
  try {
    decoded = decodeURIComponent(url.pathname.slice(1));
  } catch {
    return new Response("Invalid path", { status: 400 });
  }
  const [version, ...parts] = decoded.split("/");
  const snapshot = catalog.versions[version];
  if (!snapshot)
    return new Response("Documentation version not found", { status: 404 });
  if (parts.length === 0) return redirect(`/${version}/${url.search}`);
  let path = parts.join("/");
  if (path.endsWith("/") || !path) path += "index.html";
  if (!safePath(path)) return new Response("Invalid path", { status: 400 });
  const cacheKey = new Request(
    `https://docs.usdata.dev/__objects/${snapshot.revision}/${path}`,
  );
  let response = await caches.default.match(cacheKey);
  let status = 200;
  if (!response) {
    const object = await env.DOCS.get(snapshot.prefix + path);
    if (!object) {
      if (!path.split("/").pop()?.includes(".")) {
        const directory = await env.DOCS.head(
          snapshot.prefix + path + "/index.html",
        );
        if (directory) return redirect(url.pathname + "/" + url.search);
      }
      if (url.searchParams.has("from"))
        return redirect(`/${version}/?missing=1`);
      const missing = await env.DOCS.get(snapshot.prefix + "404.html");
      return new Response(missing?.body ?? "Page not found", {
        status: 404,
        headers: {
          "Content-Type": "text/html; charset=utf-8",
          "Cache-Control": "no-store",
        },
      });
    }
    const headers = new Headers();
    object.writeHttpMetadata(headers);
    headers.set("ETag", object.httpEtag);
    headers.set("Cache-Control", "public, max-age=31536000, immutable");
    response = new Response(object.body, { headers });
    ctx.waitUntil(caches.default.put(cacheKey, response.clone()));
  }
  const headers = new Headers(response.headers);
  headers.set("X-Content-Type-Options", "nosniff");
  headers.set("Cache-Control", "public, max-age=0, must-revalidate");
  const html = headers.get("Content-Type")?.includes("text/html");
  if (html) {
    headers.delete("ETag");
    headers.delete("Content-Length");
    headers.set("Cache-Control", "no-cache");
    response = new HTMLRewriter()
      .on("main", {
        element(el) {
          el.prepend(
            banner(catalog, version, url.searchParams.has("missing")),
            { html: true },
          );
        },
      })
      .on("body", {
        element(el) {
          el.append('<script src="/version-selector.js" defer></script>', {
            html: true,
          });
        },
      })
      .transform(new Response(response.body, { headers }));
  } else if (request.headers.get("If-None-Match") === headers.get("ETag")) {
    status = 304;
  }
  return new Response(
    request.method === "HEAD" || status === 304 ? null : response.body,
    { status, headers },
  );
}
export default {
  async fetch(request, env, ctx) {
    try {
      return await serve(request, env, ctx);
    } catch (error) {
      console.error(
        JSON.stringify({ event: "docs-request-failed", error: String(error) }),
      );
      return new Response("Documentation temporarily unavailable", {
        status: 503,
        headers: { "Cache-Control": "no-store" },
      });
    }
  },
  async scheduled(_controller, env) {
    try {
      await synchronize(env);
    } catch (error) {
      console.error(
        JSON.stringify({ event: "docs-import-failed", error: String(error) }),
      );
      throw error;
    }
  },
} satisfies ExportedHandler<Env>;
