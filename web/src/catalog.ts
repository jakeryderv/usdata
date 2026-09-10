export const KEY = "docs/catalog.json";
export interface Snapshot {
  version: string;
  revision: string;
  package_commit: string;
  docs_commit: string;
  prefix: string;
}
export interface Catalog {
  schema: 1;
  current: string;
  versions: Record<string, Snapshot>;
}
export function compare(a: string, b: string): number {
  const x = a.split(".").map(Number),
    y = b.split(".").map(Number);
  return x[0] - y[0] || x[1] - y[1] || x[2] - y[2];
}
export function safePath(path: string): boolean {
  return (
    path.length > 0 &&
    path.length < 512 &&
    !path.startsWith("/") &&
    !/[\\\x00-\x1f?#%]/.test(path) &&
    path.split("/").every((p) => p !== "." && p !== ".." && p !== "")
  );
}
export async function readCatalog(
  bucket: R2Bucket,
): Promise<{ catalog: Catalog; etag: string | null }> {
  const object = await bucket.get(KEY);
  if (!object)
    return { catalog: { schema: 1, current: "", versions: {} }, etag: null };
  return { catalog: await object.json<Catalog>(), etag: object.etag };
}
