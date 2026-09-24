// Small query aliases help familiar words match the registry's scientific terms.
const aliases = { rainfall: "precipitation", rain: "precipitation", hurricanes: "hurricane", tides: "tide", smoke: "pm2.5", pollution: "air" };

/** Whether a catalog record passes the finder's search text, agency, topic, and planned toggle. */
export function matches(dataset, { query = "", agency = "", topic = "", planned = false } = {}) {
  if (agency && dataset.provider !== agency) return false;
  if (topic && dataset.domain !== topic) return false;
  if (!planned && dataset.availability === "Planned") return false;
  const haystack = [dataset.id, dataset.title, dataset.product, dataset.description, dataset.provider,
    dataset.domain, dataset.selection, dataset.inputs, ...dataset.keywords, ...dataset.formats].join(" ").toLowerCase();
  return query.trim().toLowerCase().split(/\s+/).filter(Boolean).every(term => haystack.includes(aliases[term] ?? term));
}
