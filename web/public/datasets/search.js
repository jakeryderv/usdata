// Small query aliases help familiar words match the registry's scientific terms.
const aliases = { rainfall: "precipitation", rain: "precipitation", hurricanes: "hurricane", tides: "tide" };

export function matches(dataset, { query = "", provider = "", availability = "implemented" } = {}) {
  if (provider && dataset.provider !== provider) return false;
  if (availability === "implemented" && dataset.availability === "Planned") return false;
  if (!["implemented", "all"].includes(availability) && dataset.availability !== availability) return false;
  const haystack = [dataset.id, dataset.title, dataset.description, dataset.provider,
    dataset.domain, dataset.selection, dataset.inputs, ...dataset.keywords, ...dataset.formats].join(" ").toLowerCase();
  return query.trim().toLowerCase().split(/\s+/).filter(Boolean).every(term => haystack.includes(aliases[term] ?? term));
}
