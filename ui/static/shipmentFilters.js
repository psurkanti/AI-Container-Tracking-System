/**
 * Shipment list filters. Search text and the destination filter are independent.
 * Destination options are built from records that already respect other filters
 * (search, and any status / country / arrival-window narrowing the caller applied)
 * and never from the destination filter itself, so choosing one location cannot
 * hide the others.
 */
(function (root, factory) {
  const api = factory();
  if (typeof module !== "undefined" && module.exports) {
    module.exports = api;
  }
  if (root) root.ShipmentFilters = api;
})(typeof globalThis !== "undefined" ? globalThis : this, function () {
  function text(value) {
    if (value === null || value === undefined) return "";
    return String(value).trim();
  }

  function destinationOf(record) {
    const recordOrEmpty = record || {};
    return (
      text(recordOrEmpty.destination) ||
      text(recordOrEmpty.last_arrived_location) ||
      text(recordOrEmpty.current_location) ||
      "Unknown"
    );
  }

  function matchesQuery(record, query) {
    const q = text(query).toLowerCase();
    if (!q) return true;
    return text(record && record.part_number).toLowerCase().includes(q);
  }

  /** Rows that feed the destination list. Does not apply the destination filter. */
  function recordsForDestinationList(records, query) {
    return (records || []).filter((record) => matchesQuery(record, query));
  }

  function byName(a, b) {
    return a.name.localeCompare(b.name, undefined, { sensitivity: "base" });
  }

  function destinationOptions(records) {
    const counts = new Map();
    for (const record of records || []) {
      const name = destinationOf(record);
      counts.set(name, (counts.get(name) || 0) + 1);
    }
    return Array.from(counts.entries())
      .map(([name, count]) => ({ name, count }))
      .sort(byName);
  }

  /** Keep a selected destination visible (count 0) when other filters remove its rows. */
  function ensureSelectedListed(options, selected) {
    const name = text(selected);
    const list = (options || []).slice();
    if (!name) return list;
    if (list.some((option) => option.name.toLowerCase() === name.toLowerCase())) return list;
    list.push({ name, count: 0 });
    list.sort(byName);
    return list;
  }

  function filterByDestination(records, destination) {
    const selected = text(destination).toLowerCase();
    if (!selected) return (records || []).slice();
    return (records || []).filter((record) => destinationOf(record).toLowerCase() === selected);
  }

  /**
   * Clicking the active destination clears it. Clicking another switches to it.
   * The return value is the next destination filter only — never a search string.
   */
  function toggleDestination(current, clicked) {
    const next = text(clicked);
    if (!next) return null;
    const active = text(current);
    if (active && active.toLowerCase() === next.toLowerCase()) return null;
    return next;
  }

  function visibleShipments(records, query, destination) {
    return filterByDestination(recordsForDestinationList(records, query), destination);
  }

  return {
    destinationOf,
    matchesQuery,
    recordsForDestinationList,
    destinationOptions,
    ensureSelectedListed,
    filterByDestination,
    toggleDestination,
    visibleShipments,
  };
});
