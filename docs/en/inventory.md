# Assets and inventory

[Deutsch](../de/inventory.md) · [Documentation](../INDEX.md)

**Inventory** is the central worklist. Search, category, location, status and assignment narrow the results. Page size limits the number of rows. Clicking an entry opens its detail panel; the detail page holds extensive information.

An asset can contain other assets with quantities: a mini PC can contain a CPU and two RAM modules. **Contained assets** shows this direction; **Used in** shows parent objects. The selection dialog retains selected items while searching. Self references and cycles are rejected. General relationships are separate from containment.

**Edit** changes master data directly on the detail page. **Save** applies changes; **Cancel** discards confirmed changes. Failed saves retain input. A revision check detects simultaneous edits.

Deleting an asset detaches its incoming and outgoing links. Other assets, tickets, purchase orders and software catalog records remain. Unknown blocking database references cause an error and a complete rollback. Categories containing inventory are protected from deletion and can be emptied by reassignment.

## Existing data

Automatic asset conversion first creates a private database backup under `backups/pre-asset-conversion/` next to the database. Conversion does not start without a valid backup. Compatibility mappings preserve existing devices, categories, IDs and permissions; custom pictures reference the same server files. Repeated starts do not create additional assets.

Matching names do not prove duplication. Different physical objects can have the same name. There is no automatic deletion based on names. An explicitly reviewed consolidation requires a backup and must account for serial numbers, fields, images, relationships and permissions.

## Edit or delete multiple assets

1. Select assets using the checkboxes. The header checkbox selects entries on the current page, up to 100. Changing pages clears the selection.
2. **Edit selected assets** displays the selected names. For category, location, cost centre, warranty expiry and retirement details, choose **Leave unchanged**, **Set value** or **Clear value**.
3. **Save changes** applies only selected fields. Individual names, serial numbers, properties and pictures are retained. Category changes validate existing properties against the new category.

**Delete selected assets** displays the count and names before permanent deletion. Only selected assets are deleted. Unselected contained or parent assets are retained and detached. Historical references to a deleted asset follow their respective domain rules; a wish that is no longer fulfilled is shown as missing again.

Write permission is checked for every asset. Missing permissions, invalid values, blocking references or concurrent edits roll back the entire action. After a revision conflict, close the dialog, reload the page and review the selection. These actions do not require export permission.

## Storage and space planning

**3D view** opens the calculated packing proposal inside the workspace, including before saving. Camera presets, rotation and individual packing steps support keyboard interaction. Escape closes the view and returns focus to its trigger. The packing list remains the authoritative textual representation of the heuristic proposal.

Under **Saved plans**, **Delete** removes only the plan and its calculation after confirmation. Inventoried assets are retained. Plan creators and administrators can also remove plans whose former assets have since been deleted. Access restrictions on assets that still exist continue to apply.
