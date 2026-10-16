# Assets and inventory

[Deutsch](../de/inventory.md) · [Documentation](../INDEX.md)

**Inventory** is the central worklist. Search, category, location, status and assignment narrow the results. Page size limits the number of rows. Clicking an entry opens its detail panel; the detail page holds extensive information.

An asset can contain other assets with quantities: a mini PC can contain a CPU and two RAM modules. **Contained assets** shows this direction; **Used in** shows parent objects. The selection dialog retains selected items while searching. Self references and cycles are rejected. General relationships are separate from containment.

**Edit** changes master data directly on the detail page. **Save** applies changes; **Cancel** discards confirmed changes. Failed saves retain input. A revision check detects simultaneous edits.

Deleting an asset detaches its incoming and outgoing links. Other assets, tickets, purchase orders and software catalog records remain. Unknown blocking database references cause an error and a complete rollback. Categories containing inventory are protected from deletion and can be emptied by reassignment.

## Existing data

Automatic asset conversion first creates a private database backup under `backups/pre-asset-conversion/` next to the database. Conversion does not start without a valid backup. Compatibility mappings preserve existing devices, categories, IDs and permissions; custom pictures reference the same server files. Repeated starts do not create additional assets.

Matching names do not prove duplication. Different physical objects can have the same name. There is no automatic deletion based on names. An explicitly reviewed consolidation requires a backup and must account for serial numbers, fields, images, relationships and permissions.
