window.storagePlanning = () => ({
  ...window.InventoryPackingScene,
  binpackingPreviewLayerIndex: 0, binpackingPreviewActiveStep: null,
  binpackingPreviewCamera: 'iso', binpackingRotationX: 60, binpackingRotationZ: -38,
  binpacking3dDragging: false, binpacking3dDragStart: null,
  step: 1, labels: ['Lagerplatz', 'Abmessungen', uiText('Gegenstände'), uiText('Optionen'), uiText('Packliste')],
  options: [], page: 1, pages: 1, query: '', loading: false, error: '', requestNumber: 0,
  containerId: null, containerName: '', container: { width: '', height: '', depth: '' },
  containerFields: [], containerWarnings: [], items: [], unit: 'mm', previousUnit: 'mm',
  clearance: 0, gap: 0, allowRotation: true, preview: null, busy: false, savedId: null,
  planName: '', savedPlans: [], layerIndex: 0, changed: false,
  axes: [{ key: 'width', label: uiText('Breite') }, { key: 'height', label: uiText('Höhe') }, { key: 'depth', label: uiText('Tiefe') }],
  async init() {
    await Promise.all([this.search(), this.loadSaved()]);
    window.addEventListener('beforeunload', event => {
      if (this.changed) { event.preventDefault(); event.returnValue = ''; }
    });
  },
  async loadSaved() {
    try {
      const response = await fetch('/api/planning/plans');
      if (response.ok) this.savedPlans = (await response.json()).items;
    } catch (_) { /* Existing draft remains usable when history is unavailable. */ }
  },
  async search(page = 1) {
    const requestNumber = ++this.requestNumber;
    this.loading = true;
    try {
      const response = await fetch(`/api/planning/assets?q=${encodeURIComponent(this.query)}&page=${page}`);
      if (!response.ok) throw new Error(uiText('Inventareinträge konnten nicht geladen werden.'));
      const data = await response.json();
      if (requestNumber !== this.requestNumber) return;
      this.options = data.items;
      this.page = data.page;
      this.pages = data.pages;
    } catch (error) { this.error = error.message; }
    finally { if (requestNumber === this.requestNumber) this.loading = false; }
  },
  chooseContainer(asset) {
    this.containerId = asset.id;
    this.containerName = asset.name;
    this.container = { width: '', height: '', depth: '', ...asset.suggestions.dimensions };
    this.containerFields = asset.suggestions.fields;
    this.containerWarnings = asset.suggestions.warnings;
    this.unit = this.previousUnit = 'mm';
    this.changed = true;
  },
  addItem(asset) {
    if (asset.id === this.containerId || this.items.some(item => item.id === asset.id)) return;
    const factor = this.factors()[this.unit];
    const dimensions = { width: '', height: '', depth: '' };
    this.axes.forEach(axis => { if (asset.suggestions.dimensions[axis.key]) dimensions[axis.key] = asset.suggestions.dimensions[axis.key] / factor; });
    this.items.push({ id: asset.id, name: asset.name, dimensions, quantity: 1, fields: asset.suggestions.fields, warnings: asset.suggestions.warnings });
    this.changed = true;
  },
  removeItem(id) { this.items = this.items.filter(item => item.id !== id); this.changed = true; },
  factors() { return { mm: 1, cm: 10, m: 1000, in: 25.4 }; },
  changeUnit() {
    const ratio = this.factors()[this.previousUnit] / this.factors()[this.unit];
    for (const dimensions of [this.container, ...this.items.map(item => item.dimensions)]) {
      this.axes.forEach(axis => { if (dimensions[axis.key] !== '') dimensions[axis.key] = Number((Number(dimensions[axis.key]) * ratio).toFixed(6)); });
    }
    this.clearance = Number((Number(this.clearance) * ratio).toFixed(6));
    this.gap = Number((Number(this.gap) * ratio).toFixed(6));
    this.previousUnit = this.unit;
    this.changed = true;
  },
  applyField(axis, name) {
    const field = this.containerFields.find(field => field.name === name);
    if (field) this.container[axis] = field.value_mm / this.factors()[this.unit];
  },
  validDimensions(dimensions) { return this.axes.every(axis => Number.isFinite(Number(dimensions[axis.key])) && Number(dimensions[axis.key]) > 0); },
  async next() {
    this.error = '';
    if (this.step === 1 && !this.containerName.trim()) { this.error = uiText('Bitte einen Lagerplatz auswählen oder benennen.'); return; }
    if (this.step === 2 && !this.validDimensions(this.container)) { this.error = uiText('Bitte Breite, Höhe und Tiefe größer als null erfassen.'); return; }
    if (this.step === 3 && (!this.items.length || this.items.some(item => !this.validDimensions(item.dimensions)))) { this.error = uiText('Bitte Gegenstände wählen und ihre drei Abmessungen vervollständigen.'); return; }
    if (this.step === 4) { await this.calculate(); return; }
    this.step++;
    if (this.step === 3) { this.query = ''; await this.search(); }
    this.$nextTick(() => this.$refs.stepHeading.focus());
  },
  payload() { return { name: this.planName || `${this.containerName} – Packplan`, container_id: this.containerId, container: this.container, unit: this.unit, items: this.items.map(({ id, dimensions, quantity }) => ({ id, dimensions, quantity: Number(quantity) })), clearance: this.clearance, gap: this.gap, allow_rotation: this.allowRotation }; },
  async calculate() {
    if (this.busy) return;
    this.busy = true;
    try {
      const response = await fetch('/api/planning/preview', { method: 'POST', headers: { 'Content-Type': 'application/json' }, body: JSON.stringify(this.payload()) });
      const data = await response.json();
      if (!response.ok) throw new Error(data.error || uiText('Plan konnte nicht berechnet werden.'));
      this.preview = data;
      this.step = 5;
      this.layerIndex = 0;
      this.savedId = null;
      this.$nextTick(() => this.$refs.stepHeading.focus());
    } catch (error) { this.error = error.message; }
    finally { this.busy = false; }
  },
  async save() {
    if (this.busy) return;
    this.busy = true;
    this.error = '';
    try {
      const response = await fetch('/api/planning/plans', { method: 'POST', headers: { 'Content-Type': 'application/json' }, body: JSON.stringify(this.payload()) });
      const data = await response.json();
      if (!response.ok) throw new Error(data.error || uiText('Plan konnte nicht gespeichert werden.'));
      this.savedId = data.id;
      this.changed = false;
      await this.loadSaved();
    } catch (error) { this.error = error.message; }
    finally { this.busy = false; }
  },
  async openSaved(id) {
    if (this.busy || this.changed && !confirm(uiText('Ungespeicherte Änderungen verwerfen?'))) return;
    this.busy = true; this.error = '';
    try {
      const response = await fetch(`/api/planning/plans/${id}`);
      const data = await response.json();
      if (!response.ok) throw new Error(data.error || uiText('Plan konnte nicht geladen werden.'));
      this.preview = data.preview;
      this.savedId = data.id;
      this.planName = data.name;
      this.container = data.payload.container;
      this.containerId = data.payload.container_id;
      this.containerName = data.name;
      this.unit = this.previousUnit = data.payload.unit;
      this.items = data.payload.items.map(item => ({ ...item, name: data.preview.placements.find(p => p.asset_id === item.id)?.asset_name || uiText("Eintrag {0}", [item.id]) }));
      this.clearance = data.payload.clearance;
      this.gap = data.payload.gap;
      this.allowRotation = data.payload.allow_rotation;
      this.step = 5;
      this.layerIndex = 0;
      this.changed = false;
    } catch (error) { this.error = error.message; }
    finally { this.busy = false; }
  },
  async deleteSaved(plan) {
    if (this.busy || !confirm(uiText('Plan „{0}“ löschen? Die inventarisierten Assets bleiben erhalten.', [plan.name]))) return;
    this.busy = true; this.error = '';
    try {
      const response = await fetch(`/api/planning/plans/${plan.id}`, {method: 'DELETE'});
      const data = await response.json().catch(() => ({}));
      if (!response.ok) throw new Error(data.error || uiText('Plan konnte nicht gelöscht werden.'));
      if (this.savedId === plan.id) {this.savedId = null; this.changed = true;}
      await this.loadSaved();
      this.$nextTick(() => document.getElementById('saved-plans-heading')?.focus());
    } catch (error) {this.error = error.message;}
    finally {this.busy = false;}
  },
  previewStyle() {
    const ratio = (this.preview?.container.width || 1) / (this.preview?.container.depth || 1);
    return { width: `min(100%, ${Math.min(600, 360 * Math.max(.01, Math.min(100, ratio)))}px)`, aspectRatio: String(Math.max(.01, Math.min(100, ratio))) };
  },
  layerItems() { return this.preview?.layers?.[this.layerIndex]?.items || []; },
  boxStyle(placement) {
    const container = this.preview.container;
    return { left: `${placement.x / container.width * 100}%`, top: `${placement.y / container.depth * 100}%`, width: `${placement.width / container.width * 100}%`, height: `${placement.depth / container.depth * 100}%`, backgroundColor: placement.color };
  },
  currentBinpackingPreview() { return this.preview; },
  open3d() {
    if (!this.preview) return;
    this.binpackingPreviewActiveStep = this.preview.steps?.[0]?.step || null;
    this.binpackingPreviewLayerIndex = 0; this.setBinpackingCamera('iso');
    this.$refs.packingDialog.showModal();
  },
  close3d() { this.$refs.packingDialog.close(); }
});
