# Modules and workflows

[Deutsch](../de/modules.md) · [Documentation](../INDEX.md)

## Service desk

Queues, search, filters and saved views organize tickets. Bulk actions respect permissions for each selected ticket. Priority, due date, SLA risk and escalation are separate properties. Ticket links show only visible assets. Knowledge suggestions and similar cases respect the same access boundaries. A change requires an accepted review before completion.

## Procurement and knowledge

Procurement brings together suppliers, contracts, orders and order lines. Orders can reference assets. The knowledge base provides articles, categories and search; roadmaps organize initiatives, milestones and ownership. Locations open their filtered asset lists. Reports and dependencies use accessible records. The timeline presents historical or planned states within its supported scope.

## Storage and space planning

1. Select a storage location or container.
2. Check width, height, depth and the shared unit. Suitable existing numeric fields can supply dimensions; field mapping is an advanced option.
3. Select items and quantities. Correct missing or invalid dimensions.
4. Configure rotation, spacing and wall clearance.
5. Review the packing list, unplaced items and preview, then save the plan.

The packing list works without 3D rendering. Calculated suggestions are algorithmic approximations, not guarantees of optimal packing. Review placement problems and missing dimensions before practical use.

## Health and maintenance console

Health checks require permissions; administrators restrict network targets and allowed check types. The maintenance console is disabled by default and exposes approved diagnostic recipes, not an unrestricted shell. `terminal.view`, `terminal.use` and `terminal.db_write` are separate permissions. Database writes also require the enabled server option and renewed authentication. Sessions expire, output is limited and sensitive values are masked.
