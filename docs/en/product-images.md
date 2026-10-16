# Product images

[Deutsch](../de/product-images.md) · [Documentation](../INDEX.md)

The product catalog stores manufacturer, model, identifiers, image provenance and license in the instance database. A licensed MacBook Air M4 model image is included. Model pictures represent a product family, not an individual inventory item.

## Automatic matching

An administrator can enable the public image source in the product catalog and run the missing-image search. Wikidata provides model information; suitable pictures are retrieved from Wikimedia Commons. When a photo exists only on Commons, an additional lookup requires a complete, unambiguous model name in the file title. Comparison images and other generations are excluded. Searches use only manufacturer and public model information. Personal assignments, locations, serial numbers and internal inventory names are not transmitted.

Manufacturer and full model must match. Clear product names such as “Apple AirPods 4 ANC” are recognized without separate manufacturer and model fields. Name recognition uses bounded product patterns; unknown free text and personal name suffixes are not transmitted as search terms. For other products, enter the manufacturer and full model in their properties. Opening inventory starts an incremental background check of existing items; the list does not wait for external image requests. Ambiguous results or unsuitable licenses are not assigned automatically. Source management shows jobs, missing matches and errors. No public database covers every possible inventory item. A consistent type icon appears when no suitable image is available.

## Custom photos and persistence

Each authorized object can have a custom photo, which takes precedence over catalog pictures. The server validates and re-encodes uploads. WebP files and thumbnails are stored under `INVENTORY_UPLOADS_DIR/product-media/`, or `/data/uploads/product-media/` in the default container. Every authorized client retrieves the same files through authenticated media URLs. Images are not stored only in the uploading browser.

Disabling the public source retains cached files. Preserve the database **and** uploads for updates and restores. Exports that include uploads can transport images; database-only exports contain references. Imports do not silently overwrite conflicting files.

See the [starter image license and author](../../inventorypro/data/product_images/LICENSE.md). Each image retains its own license; the application license does not replace it.
