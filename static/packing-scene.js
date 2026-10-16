/* Shared SVG packing renderer. No inventory navigation or network requests. */
window.InventoryPackingScene = {
        openBinpackingPreview(asset = null) {
            const targetAsset = asset || this.selectedAsset;
            const preview = targetAsset?.binpacking;
            if (!preview?.enabled) {
                return;
            }
            this.binpackingPreviewOpen = true;
            this.binpackingPreviewLayerIndex = 0;
            this.binpackingPreviewActiveStep = preview.steps?.[0]?.step || null;
            this.setBinpackingCamera('iso');
        },

        closeBinpackingPreview() {
            this.binpackingPreviewOpen = false;
            this.binpackingPreviewLayerIndex = 0;
            this.binpackingPreviewActiveStep = null;
            this.binpacking3dDragging = false;
            this.binpacking3dDragStart = null;
        },

        currentBinpackingPreview() {
            return this.selectedAsset?.binpacking || null;
        },

        currentBinpackingLayer() {
            const layers = this.currentBinpackingPreview()?.layers || [];
            if (!layers.length) {
                return null;
            }
            return layers[this.binpackingPreviewLayerIndex] || layers[0];
        },

        setBinpackingPreviewLayer(index) {
            const layers = this.currentBinpackingPreview()?.layers || [];
            if (!layers.length) {
                return;
            }
            const normalizedIndex = Math.max(0, Math.min(index, layers.length - 1));
            this.binpackingPreviewLayerIndex = normalizedIndex;
            const firstStep = (layers[normalizedIndex]?.items || [])[0]?.step;
            if (firstStep) {
                this.binpackingPreviewActiveStep = firstStep;
            }
        },

        focusBinpackingStep(step) {
            const preview = this.currentBinpackingPreview();
            const normalizedStep = Number(step?.step || step);
            if (!preview || !normalizedStep) {
                return;
            }
            this.binpackingPreviewActiveStep = normalizedStep;
            const matchingLayerIndex = (preview.layers || []).findIndex((layer) =>
                (layer.items || []).some((placement) => Number(placement.step) === normalizedStep)
            );
            if (matchingLayerIndex >= 0) {
                this.binpackingPreviewLayerIndex = matchingLayerIndex;
            }
        },

        isBinpackingStepActive(step) {
            return Number(step?.step || step) === Number(this.binpackingPreviewActiveStep);
        },

        currentBinpackingActiveStep() {
            const preview = this.currentBinpackingPreview();
            if (!preview) {
                return null;
            }
            return (
                (preview.steps || []).find((step) => Number(step.step) === Number(this.binpackingPreviewActiveStep))
                || preview.steps?.[0]
                || null
            );
        },

        currentBinpackingActivePlacement() {
            const preview = this.currentBinpackingPreview();
            if (!preview) {
                return null;
            }
            return (
                (preview.placements || []).find((placement) => Number(placement.step) === Number(this.binpackingPreviewActiveStep))
                || preview.placements?.[0]
                || null
            );
        },

        binpackingPlacementByStep(step) {
            const preview = this.currentBinpackingPreview();
            const normalizedStep = Number(step?.step || step);
            if (!preview || !normalizedStep) {
                return null;
            }
            return (preview.placements || []).find((placement) => Number(placement.step) === normalizedStep) || null;
        },

        focusAdjacentBinpackingStep(direction = 1) {
            const steps = this.currentBinpackingPreview()?.steps || [];
            if (!steps.length) {
                return;
            }
            const currentIndex = steps.findIndex((step) => Number(step.step) === Number(this.binpackingPreviewActiveStep));
            const safeIndex = currentIndex >= 0 ? currentIndex : 0;
            const nextIndex = Math.max(0, Math.min(safeIndex + direction, steps.length - 1));
            this.focusBinpackingStep(steps[nextIndex]);
        },

        setBinpackingCamera(camera = 'iso') {
            const presets = {
                iso: { x: 60, z: -38 },
                front: { x: 60, z: 0 },
                side: { x: 60, z: -90 },
                top: { x: 0, z: -38 },
            };
            const nextPreset = presets[camera] || presets.iso;
            this.binpackingPreviewCamera = camera;
            this.binpackingRotationX = nextPreset.x;
            this.binpackingRotationZ = nextPreset.z;
        },

        binpackingSceneViewBox() {
            return '0 0 1000 620';
        },

        startBinpacking3dDrag(event) {
            this.binpacking3dDragging = true;
            this.binpacking3dDragStart = {
                x: event.clientX,
                y: event.clientY,
                rotationZ: this.binpackingRotationZ,
            };
            event.currentTarget?.setPointerCapture?.(event.pointerId);
        },

        dragBinpacking3dView(event) {
            if (!this.binpacking3dDragging || !this.binpacking3dDragStart) {
                return;
            }
            const deltaX = event.clientX - this.binpacking3dDragStart.x;
            this.binpackingPreviewCamera = 'custom';
            this.binpackingRotationZ = this.binpacking3dDragStart.rotationZ + (deltaX * 0.18);
        },

        endBinpacking3dDrag(event) {
            if (this.binpacking3dDragging) {
                event.currentTarget?.releasePointerCapture?.(event.pointerId);
            }
            this.binpacking3dDragging = false;
            this.binpacking3dDragStart = null;
        },

        binpackingSceneProjector(preview) {
            const container = preview?.container || {};
            const width = Math.max(Number(container.width) || 1, 1);
            const depth = Math.max(Number(container.depth) || 1, 1);
            const height = Math.max(Number(container.height) || 1, 1);
            const viewWidth = 1000;
            const viewHeight = 620;
            const padding = 72;
            const yaw = (Number.isFinite(Number(this.binpackingRotationZ)) ? Number(this.binpackingRotationZ) : -38) * (Math.PI / 180);
            const topView = this.binpackingPreviewCamera === 'top';
            const rawPoint = (point) => {
                const x = Number(point.x) || 0;
                const y = Number(point.y) || 0;
                const z = Number(point.z) || 0;
                if (topView) {
                    return { x, y, depth: y + (z * 0.02), z };
                }
                const centeredX = x - (width / 2);
                const centeredY = y - (depth / 2);
                const rotatedX = (centeredX * Math.cos(yaw)) - (centeredY * Math.sin(yaw));
                const rotatedY = (centeredX * Math.sin(yaw)) + (centeredY * Math.cos(yaw));
                return {
                    x: rotatedX,
                    y: (rotatedY * 0.48) - (z * 0.88),
                    depth: rotatedY + (z * 0.05),
                    z,
                };
            };
            const vertices = [
                { x: 0, y: 0, z: 0 },
                { x: width, y: 0, z: 0 },
                { x: width, y: depth, z: 0 },
                { x: 0, y: depth, z: 0 },
                { x: 0, y: 0, z: height },
                { x: width, y: 0, z: height },
                { x: width, y: depth, z: height },
                { x: 0, y: depth, z: height },
            ].map(rawPoint);
            const minX = Math.min(...vertices.map((point) => point.x));
            const maxX = Math.max(...vertices.map((point) => point.x));
            const minY = Math.min(...vertices.map((point) => point.y));
            const maxY = Math.max(...vertices.map((point) => point.y));
            const scale = Math.min(
                (viewWidth - (padding * 2)) / Math.max(maxX - minX, 1),
                (viewHeight - (padding * 2)) / Math.max(maxY - minY, 1)
            );
            const offsetX = (viewWidth / 2) - (((minX + maxX) / 2) * scale);
            const offsetY = (viewHeight / 2) - (((minY + maxY) / 2) * scale);
            return {
                width,
                depth,
                height,
                topView,
                project(point) {
                    const raw = rawPoint(point);
                    return {
                        x: offsetX + (raw.x * scale),
                        y: offsetY + (raw.y * scale),
                        depth: raw.depth,
                        z: Number(point.z) || 0,
                    };
                },
            };
        },

        binpackingScenePointString(points) {
            return points.map((point) => `${point.x.toFixed(1)},${point.y.toFixed(1)}`).join(' ');
        },

        binpackingShadeColor(color, factor = 1) {
            const hex = String(color || '#2563eb').replace('#', '');
            const normalized = hex.length === 3
                ? hex.split('').map((character) => character + character).join('')
                : hex.padEnd(6, '0').slice(0, 6);
            const values = [0, 2, 4].map((index) => parseInt(normalized.slice(index, index + 2), 16));
            const shaded = values.map((value) => {
                if (factor >= 1) {
                    return Math.round(value + ((255 - value) * (factor - 1)));
                }
                return Math.round(value * factor);
            });
            return `rgb(${shaded.map((value) => Math.max(0, Math.min(255, value))).join(', ')})`;
        },

        escapeSvgAttribute(value) {
            return String(value ?? '')
                .replace(/&/g, '&amp;')
                .replace(/"/g, '&quot;')
                .replace(/</g, '&lt;')
                .replace(/>/g, '&gt;');
        },

        escapeSvgText(value) {
            return String(value ?? '')
                .replace(/&/g, '&amp;')
                .replace(/</g, '&lt;')
                .replace(/>/g, '&gt;');
        },

        binpackingSceneFaces(preview) {
            if (!preview?.container) {
                return [];
            }
            const projector = this.binpackingSceneProjector(preview);
            const width = projector.width;
            const depth = projector.depth;
            const height = projector.height;
            const yaw = (Number.isFinite(Number(this.binpackingRotationZ)) ? Number(this.binpackingRotationZ) : -38) * (Math.PI / 180);
            const visibleX = Math.cos(yaw) >= 0 ? width : 0;
            const visibleY = Math.sin(yaw) >= 0 ? depth : 0;
            const projectFace = (points) => points.map((point) => projector.project(point));
            const buildFace = ({ key, points, fill, stroke, type = 'box', step = null, assetName = '', active = false, depthBias = 0 }) => {
                const projected = projectFace(points);
                const averageDepth = projected.reduce((sum, point) => sum + point.depth, 0) / projected.length;
                return {
                    key,
                    points: this.binpackingScenePointString(projected),
                    fill,
                    stroke,
                    type,
                    step,
                    assetName,
                    active,
                    depth: averageDepth + depthBias,
                    className: [
                        'binpacking-scene__face',
                        type === 'storage' ? 'is-storage' : '',
                        active ? 'is-active' : '',
                    ].filter(Boolean).join(' '),
                };
            };
            const faces = [
                buildFace({
                    key: 'storage-floor',
                    type: 'storage',
                    points: [
                        { x: 0, y: 0, z: 0 },
                        { x: width, y: 0, z: 0 },
                        { x: width, y: depth, z: 0 },
                        { x: 0, y: depth, z: 0 },
                    ],
                    fill: 'rgba(248, 250, 252, 0.96)',
                    stroke: 'rgba(15, 23, 42, 0.18)',
                    depthBias: -100,
                }),
            ];

            if (!projector.topView) {
                faces.push(
                    buildFace({
                        key: 'storage-wall-y',
                        type: 'storage',
                        points: [
                            { x: 0, y: visibleY, z: 0 },
                            { x: width, y: visibleY, z: 0 },
                            { x: width, y: visibleY, z: height },
                            { x: 0, y: visibleY, z: height },
                        ],
                        fill: 'rgba(226, 232, 240, 0.28)',
                        stroke: 'rgba(15, 23, 42, 0.12)',
                        depthBias: -98,
                    }),
                    buildFace({
                        key: 'storage-wall-x',
                        type: 'storage',
                        points: [
                            { x: visibleX, y: 0, z: 0 },
                            { x: visibleX, y: depth, z: 0 },
                            { x: visibleX, y: depth, z: height },
                            { x: visibleX, y: 0, z: height },
                        ],
                        fill: 'rgba(236, 253, 245, 0.32)',
                        stroke: 'rgba(15, 23, 42, 0.12)',
                        depthBias: -97,
                    })
                );
            }

            (preview.placements || []).forEach((placement) => {
                const x0 = Number(placement.x) || 0;
                const y0 = Number(placement.y) || 0;
                const z0 = Number(placement.z) || 0;
                const x1 = x0 + (Number(placement.width) || 0);
                const y1 = y0 + (Number(placement.depth) || 0);
                const z1 = z0 + (Number(placement.height) || 0);
                const color = placement.color || '#2563eb';
                const active = this.isBinpackingStepActive(placement);
                const opacityFactor = active ? 1 : 0.82;
                const facesForBox = projector.topView
                    ? [
                        {
                            name: 'top',
                            points: [
                                { x: x0, y: y0, z: z1 },
                                { x: x1, y: y0, z: z1 },
                                { x: x1, y: y1, z: z1 },
                                { x: x0, y: y1, z: z1 },
                            ],
                            shade: 1.08,
                            depthBias: 2,
                        },
                    ]
                    : [
                        {
                            name: 'side-y',
                            points: [
                                { x: x0, y: visibleY === depth ? y1 : y0, z: z0 },
                                { x: x1, y: visibleY === depth ? y1 : y0, z: z0 },
                                { x: x1, y: visibleY === depth ? y1 : y0, z: z1 },
                                { x: x0, y: visibleY === depth ? y1 : y0, z: z1 },
                            ],
                            shade: 0.7,
                            depthBias: 1,
                        },
                        {
                            name: 'side-x',
                            points: [
                                { x: visibleX === width ? x1 : x0, y: y0, z: z0 },
                                { x: visibleX === width ? x1 : x0, y: y1, z: z0 },
                                { x: visibleX === width ? x1 : x0, y: y1, z: z1 },
                                { x: visibleX === width ? x1 : x0, y: y0, z: z1 },
                            ],
                            shade: 0.82,
                            depthBias: 1.5,
                        },
                        {
                            name: 'top',
                            points: [
                                { x: x0, y: y0, z: z1 },
                                { x: x1, y: y0, z: z1 },
                                { x: x1, y: y1, z: z1 },
                                { x: x0, y: y1, z: z1 },
                            ],
                            shade: 1.08,
                            depthBias: 2,
                        },
                    ];
                facesForBox.forEach((face) => {
                    faces.push(buildFace({
                        key: `box-${placement.asset_id}-${face.name}`,
                        type: 'box',
                        step: placement.step,
                        assetName: placement.asset_name,
                        active,
                        points: face.points,
                        fill: this.binpackingShadeColor(color, face.shade * opacityFactor),
                        stroke: active ? '#0f172a' : 'rgba(255, 255, 255, 0.64)',
                        depthBias: face.depthBias,
                    }));
                });
            });

            return faces.sort((a, b) => a.depth - b.depth);
        },

        binpackingSceneEdges(preview) {
            if (!preview?.container) {
                return [];
            }
            const projector = this.binpackingSceneProjector(preview);
            const width = projector.width;
            const depth = projector.depth;
            const height = projector.height;
            const points = {
                a: { x: 0, y: 0, z: 0 },
                b: { x: width, y: 0, z: 0 },
                c: { x: width, y: depth, z: 0 },
                d: { x: 0, y: depth, z: 0 },
                e: { x: 0, y: 0, z: height },
                f: { x: width, y: 0, z: height },
                g: { x: width, y: depth, z: height },
                h: { x: 0, y: depth, z: height },
            };
            return [
                ['a', 'b'], ['b', 'c'], ['c', 'd'], ['d', 'a'],
                ['e', 'f'], ['f', 'g'], ['g', 'h'], ['h', 'e'],
                ['a', 'e'], ['b', 'f'], ['c', 'g'], ['d', 'h'],
            ].map(([from, to], index) => {
                const start = projector.project(points[from]);
                const end = projector.project(points[to]);
                return {
                    key: `edge-${index}`,
                    x1: start.x,
                    y1: start.y,
                    x2: end.x,
                    y2: end.y,
                };
            });
        },

        binpackingSceneLabels(preview) {
            if (!preview?.container) {
                return [];
            }
            const projector = this.binpackingSceneProjector(preview);
            return (preview.placements || []).map((placement) => {
                const point = projector.project({
                    x: (Number(placement.x) || 0) + ((Number(placement.width) || 0) / 2),
                    y: (Number(placement.y) || 0) + ((Number(placement.depth) || 0) / 2),
                    z: (Number(placement.z) || 0) + (Number(placement.height) || 0),
                });
                const active = this.isBinpackingStepActive(placement);
                return {
                    key: `label-${placement.asset_id}`,
                    x: point.x,
                    y: point.y - 12,
                    step: placement.step,
                    assetName: placement.asset_name,
                    color: placement.color || '#2563eb',
                    active,
                    className: [
                        'binpacking-scene__label',
                        active ? 'is-active' : '',
                    ].filter(Boolean).join(' '),
                };
            }).sort((a, b) => Number(a.active) - Number(b.active));
        },

        binpackingSceneMarkup(preview) {
            if (!preview?.container) {
                return '<rect class="binpacking-scene__backdrop" x="0" y="0" width="1000" height="620" rx="28"></rect>';
            }
            const edges = this.binpackingSceneEdges(preview).map((edge) => (
                `<line x1="${edge.x1.toFixed(1)}" y1="${edge.y1.toFixed(1)}" x2="${edge.x2.toFixed(1)}" y2="${edge.y2.toFixed(1)}"></line>`
            )).join('');
            const faces = this.binpackingSceneFaces(preview).map((face) => {
                const stepAttribute = face.step ? ` data-binpacking-step="${this.escapeSvgAttribute(face.step)}"` : '';
                const tabIndex = face.step ? '0' : '-1';
                const role = face.step ? 'button' : 'presentation';
                const label = face.step
                    ? `${face.assetName}, Schritt ${face.step}`
                    : 'Regalbegrenzung';
                return (
                    `<polygon${stepAttribute} points="${this.escapeSvgAttribute(face.points)}" fill="${this.escapeSvgAttribute(face.fill)}" stroke="${this.escapeSvgAttribute(face.stroke)}" class="${this.escapeSvgAttribute(face.className)}" tabindex="${tabIndex}" role="${role}" aria-label="${this.escapeSvgAttribute(label)}"></polygon>`
                );
            }).join('');
            const labels = this.binpackingSceneLabels(preview).map((label) => {
                const name = label.active
                    ? `<text x="${(label.x + 22).toFixed(1)}" y="${(label.y + 5).toFixed(1)}" class="binpacking-scene__name">${this.escapeSvgText(label.assetName)}</text>`
                    : '';
                return (
                    `<g class="${this.escapeSvgAttribute(label.className)}" data-binpacking-step="${this.escapeSvgAttribute(label.step)}" role="button" tabindex="0" aria-label="${this.escapeSvgAttribute(`${label.assetName}, Schritt ${label.step}`)}">`
                    + `<circle cx="${label.x.toFixed(1)}" cy="${label.y.toFixed(1)}" r="15" fill="${this.escapeSvgAttribute(label.color)}"></circle>`
                    + `<text x="${label.x.toFixed(1)}" y="${(label.y + 4).toFixed(1)}" text-anchor="middle">${this.escapeSvgText(label.step)}</text>`
                    + name
                    + '</g>'
                );
            }).join('');
            return (
                '<rect class="binpacking-scene__backdrop" x="0" y="0" width="1000" height="620" rx="28"></rect>'
                + `<g class="binpacking-scene__edges" aria-hidden="true">${edges}</g>`
                + faces
                + labels
            );
        },

        handleBinpackingSceneEvent(event) {
            const target = event.target?.closest?.('[data-binpacking-step]');
            const step = Number(target?.dataset?.binpackingStep);
            if (!step) {
                return;
            }
            this.focusBinpackingStep(step);
        },

        currentBinpackingLayerSteps() {
            const layer = this.currentBinpackingLayer();
            const preview = this.currentBinpackingPreview();
            if (!layer || !preview) {
                return [];
            }
            return (preview.steps || []).filter((step) => Number(step.layer_index) === Number(layer.index));
        },

};
