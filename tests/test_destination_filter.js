const assert = require("assert");
const filters = require("../ui/static/shipmentFilters.js");

const records = [
  { part_number: "A-1", destination: "DIRECT", container_status: "Active" },
  { part_number: "B-2", destination: "WISCONSIN", container_status: "Active" },
  { part_number: "C-3", destination: "TENNESSEE", container_status: "On Water" },
  { part_number: "A-9", destination: "DIRECT", container_status: "Delivered" },
];

function names(options) {
  return options.map((option) => option.name);
}

const allOptions = filters.destinationOptions(filters.recordsForDestinationList(records, ""));
assert.deepStrictEqual(names(allOptions), ["DIRECT", "TENNESSEE", "WISCONSIN"]);
assert.strictEqual(allOptions.find((option) => option.name === "DIRECT").count, 2);

let selected = filters.toggleDestination(null, "DIRECT");
assert.strictEqual(selected, "DIRECT");

const directRows = filters.visibleShipments(records, "", selected);
assert.strictEqual(directRows.length, 2);
assert.ok(directRows.every((row) => row.destination === "DIRECT"));

// The destination list is not rebuilt from the already-filtered rows.
const stillListed = filters.destinationOptions(filters.recordsForDestinationList(records, ""));
assert.deepStrictEqual(names(stillListed), ["DIRECT", "TENNESSEE", "WISCONSIN"]);

selected = filters.toggleDestination(selected, "WISCONSIN");
assert.strictEqual(selected, "WISCONSIN");
const wisconsinRows = filters.visibleShipments(records, "", selected);
assert.strictEqual(wisconsinRows.length, 1);
assert.strictEqual(wisconsinRows[0].destination, "WISCONSIN");
assert.deepStrictEqual(
  names(filters.destinationOptions(filters.recordsForDestinationList(records, ""))),
  ["DIRECT", "TENNESSEE", "WISCONSIN"]
);

selected = filters.toggleDestination(selected, "WISCONSIN");
assert.strictEqual(selected, null);
assert.strictEqual(filters.visibleShipments(records, "", selected).length, 4);

// Search stays a separate filter: it can narrow counts, and it is not a destination write-back.
const searched = filters.recordsForDestinationList(records, "A-");
assert.deepStrictEqual(names(filters.destinationOptions(searched)), ["DIRECT"]);
assert.strictEqual(filters.visibleShipments(records, "A-", "WISCONSIN").length, 0);
assert.strictEqual(filters.visibleShipments(records, "A-", null).length, 2);

// Other filters (status) are applied before the destination list is built.
const active = records.filter((row) => row.container_status === "Active");
assert.deepStrictEqual(names(filters.destinationOptions(active)), ["DIRECT", "WISCONSIN"]);
const activeDirect = filters.filterByDestination(active, "DIRECT");
assert.strictEqual(activeDirect.length, 1);
assert.deepStrictEqual(names(filters.destinationOptions(active)), ["DIRECT", "WISCONSIN"]);

const kept = filters.ensureSelectedListed(filters.destinationOptions(active), "TENNESSEE");
assert.deepStrictEqual(names(kept), ["DIRECT", "TENNESSEE", "WISCONSIN"]);
assert.strictEqual(kept.find((option) => option.name === "TENNESSEE").count, 0);

console.log("destination filter tests passed");
