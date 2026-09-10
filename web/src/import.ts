import {
  compare,
  digest,
  KEY,
  readCatalog,
  REPO,
  safePath,
  SHA,
  VERSION,
  type Snapshot,
} from "./catalog";
const MAX_BYTES = 24 * 1024 * 1024;
const MAX_FILES = 500;
interface Asset {
  name: string;
  browser_download_url: string;
  size: number;
  digest?: string;
  updated_at: string;
}
interface Release {
  tag_name: string;
  draft: boolean;
  prerelease: boolean;
  assets: Asset[];
}
interface Description {
  schema: number;
  version: string;
  package_commit: string;
  docs_commit: string;
  bundle: { name: string; sha256: string; size: number };
  files: number;
}
async function bytes(response: Response, max: number): Promise<Uint8Array> {
  if (!response.ok || !response.body)
    throw new Error(`Download failed: ${response.status}`);
  const reader = response.body.getReader();
  const chunks: Uint8Array[] = [];
  let length = 0;
  try {
    while (true) {
      const { done, value } = await reader.read();
      if (done) break;
      length += value.length;
      if (length > max) throw new Error("Download exceeds limit");
      chunks.push(value);
    }
  } finally {
    await reader.cancel();
  }
  const result = new Uint8Array(length);
  let offset = 0;
  for (const chunk of chunks) {
    result.set(chunk, offset);
    offset += chunk.length;
  }
  return result;
}
async function get(url: string): Promise<Response> {
  return fetch(url, {
    headers: {
      "User-Agent": "usdata-docs-importer",
      Accept: "application/json",
    },
    signal: AbortSignal.timeout(60000),
  });
}
function assetURL(asset: Asset): string {
  const url = new URL(asset.browser_download_url);
  if (
    url.origin !== "https://github.com" ||
    !url.pathname.startsWith(`/${REPO}/releases/download/`)
  )
    throw new Error("Unexpected asset URL");
  return url.href;
}
export async function importRelease(
  bucket: R2Bucket,
  release: Release,
  asset: Asset,
): Promise<Snapshot> {
  const description = JSON.parse(
    new TextDecoder().decode(await bytes(await get(assetURL(asset)), 16384)),
  ) as Description;
  const version = release.tag_name.slice(1);
  if (
    description.schema !== 1 ||
    description.version !== version ||
    !VERSION.test(version) ||
    !/^[a-f0-9]{40}$/.test(description.package_commit) ||
    !/^[a-f0-9]{40}$/.test(description.docs_commit) ||
    !SHA.test(description.bundle.sha256) ||
    !Number.isInteger(description.files) ||
    description.files < 1 ||
    description.files > MAX_FILES
  )
    throw new Error("Invalid docs descriptor");
  const source = release.assets.find((a) => a.name === description.bundle.name);
  if (
    !source ||
    source.size !== description.bundle.size ||
    source.size > MAX_BYTES
  )
    throw new Error("Missing or oversized bundle");
  const compressed = await bytes(await get(assetURL(source)), MAX_BYTES);
  if (
    compressed.length !== source.size ||
    (await digest(compressed)) !== description.bundle.sha256
  )
    throw new Error("Bundle checksum mismatch");
  const prefix = `docs/${version}/${description.bundle.sha256}/`;
  const snapshot: Snapshot = {
    version,
    revision: description.bundle.sha256,
    package_commit: description.package_commit,
    docs_commit: description.docs_commit,
    prefix,
  };
  const stream = new Blob([compressed])
    .stream()
    .pipeThrough(new DecompressionStream("gzip"));
  const raw = await bytes(new Response(stream), MAX_BYTES);
  const lines = new TextDecoder().decode(raw).trimEnd().split("\n");
  if (lines.length !== description.files)
    throw new Error("File count mismatch");
  const seen = new Set<string>();
  let total = 0;
  for (const line of lines) {
    const file = JSON.parse(line) as {
      path: string;
      data: string;
      sha256: string;
      type: string;
    };
    if (
      !safePath(file.path) ||
      seen.has(file.path) ||
      !SHA.test(file.sha256) ||
      typeof file.type !== "string" ||
      /[\r\n]/.test(file.type)
    )
      throw new Error("Invalid archive entry");
    seen.add(file.path);
    const body = Uint8Array.from(atob(file.data), (c) => c.charCodeAt(0));
    total += body.length;
    if (total > MAX_BYTES || (await digest(body)) !== file.sha256)
      throw new Error("File checksum mismatch");
    await bucket.put(prefix + file.path, body, {
      httpMetadata: { contentType: file.type },
      sha256: file.sha256,
    });
  }
  if (!seen.has("index.html") || !seen.has("404.html"))
    throw new Error("Archive lacks entry pages");
  return snapshot;
}
export async function synchronize(env: Env): Promise<void> {
  if (env.IMPORT_ENABLED !== "true") return;
  const pypi = JSON.parse(
    new TextDecoder().decode(
      await bytes(
        await get("https://pypi.org/pypi/usdata/json"),
        2 * 1024 * 1024,
      ),
    ),
  ) as { info: { version: string } };
  const latest = pypi.info.version;
  if (!VERSION.test(latest)) throw new Error("Invalid published version");
  // Bounded discovery: paginate so retained versions are not lost as releases grow.
  const releases: Release[] = [];
  for (let page = 1; page <= 10; page++) {
    const batch = JSON.parse(
      new TextDecoder().decode(
        await bytes(
          await get(
            `https://api.github.com/repos/${REPO}/releases?per_page=100&page=${page}`,
          ),
          4 * 1024 * 1024,
        ),
      ),
    ) as Release[];
    releases.push(...batch);
    if (batch.length < 100) break;
    if (page === 10) throw new Error("Release discovery limit reached");
  }
  const initial = await readCatalog(env.DOCS);
  const candidates = releases
    .filter(
      (r) =>
        !r.draft &&
        !r.prerelease &&
        r.tag_name.startsWith("v") &&
        VERSION.test(r.tag_name.slice(1)) &&
        compare(r.tag_name.slice(1), "0.10.0") >= 0 &&
        compare(r.tag_name.slice(1), latest) <= 0,
    )
    .sort((a, b) => compare(a.tag_name.slice(1), b.tag_name.slice(1)));
  for (const release of candidates) {
    const version = release.tag_name.slice(1);
    const asset = release.assets
      .filter((a) => /^usdata-docs-[a-f0-9]{40}\.json$/.test(a.name))
      .sort(
        (a, b) =>
          b.updated_at.localeCompare(a.updated_at) ||
          b.name.localeCompare(a.name),
      )[0];
    if (
      !asset ||
      initial.catalog.versions[version]?.docs_commit ===
        asset.name.slice(12, 52)
    )
      continue;
    const published = await get(`https://pypi.org/pypi/usdata/${version}/json`);
    if (!published.ok) throw new Error(`Package ${version} is not published`);
    await published.body?.cancel();
    const snapshot = await importRelease(env.DOCS, release, asset);
    // Re-read after upload and compare-and-swap, so competing imports cannot lose versions.
    const { catalog, etag } = await readCatalog(env.DOCS);
    catalog.versions[version] = snapshot;
    if (!catalog.current || compare(version, catalog.current) > 0)
      catalog.current = version;
    const stored = await env.DOCS.put(KEY, JSON.stringify(catalog), {
      onlyIf: etag ? { etagMatches: etag } : { etagDoesNotMatch: "*" },
      httpMetadata: {
        contentType: "application/json",
        cacheControl: "no-store",
      },
    });
    if (!stored)
      throw new Error("Concurrent publication; retry on next schedule");
    console.log(
      JSON.stringify({
        event: "docs-published",
        version,
        revision: snapshot.revision,
        files: asset.name,
      }),
    );
    return; // One release per invocation bounds work and retries.
  }
  console.log(
    JSON.stringify({ event: "docs-current", version: initial.catalog.current }),
  );
}
