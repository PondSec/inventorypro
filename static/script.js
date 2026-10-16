document.addEventListener('alpine:init', () => {
    Alpine.data('app', () => ({
        ...window.InventoryPackingScene,
        // State
        categoryRemoval: { open: false, kind: 'device', id: null, target: '', error: '', busy: false },
        openCategoryRemoval(kind, id) {
            this.categoryRemoval = { open: true, kind, id, target: '', error: '', busy: false };
        },
        categoryRemovalTargets() {
            const list = this.categoryRemoval.kind === 'device' ? this.categories : this.assetCategories;
            return list.filter(item => item.id !== this.categoryRemoval.id);
        },
        async submitCategoryRemoval() {
            const removal = this.categoryRemoval;
            if (removal.busy) return;
            removal.busy = true;
            removal.error = '';
            try {
                const path = removal.kind === 'device' ? 'categories' : 'asset-categories';
                const response = await fetch(`/api/${path}/${removal.id}`, {
                    method: 'DELETE', headers: { 'Content-Type': 'application/json' },
                    body: JSON.stringify(removal.target ? { target_category_id: Number(removal.target) } : {})
                });
                const data = await response.json();
                if (!response.ok) { removal.error = data.error || uiText('Löschen fehlgeschlagen.'); return; }
                removal.open = false;
                this.categoryModalOpen = false;
                this.assetCategoryModalOpen = false;
                this.activeCategory = null;
                this.selectedAssetCategory = null;
                await Promise.all([this.loadCategories(), this.loadAssetCategories(), this.loadDevices(), this.loadAssets()]);
                await this.loadActivityFeed();
            } catch (error) { removal.error = uiText('Verbindung fehlgeschlagen. Bitte erneut versuchen.'); }
            finally { removal.busy = false; }
        },
        dashboardTasks: [],
        dashboardTasksLoading: true,
        dashboardTasksError: '',
        categories: [],
        assetCategories: [],
        locations: [],
        devices: [],
        filteredDevices: [],
        allDevices: [],
        assets: [],
        vendors: [],
        purchaseOrders: [],
        assetEntryOptions: [],
        relationTypes: [],
        activeCategory: null,
        workspaceView: 'overview',
        inventoryTab: 'devices',
        categoriesOpen: false,
        assetsOpen: false,
        searchQuery: '',
        categorySearchQuery: '',
        assetCategorySearchQuery: '',
        assetSearchQuery: '',
        ownerQuery: '',
        locationFilter: '',
        categoryFilter: '',
        createdFrom: '',
        createdTo: '',
        specQuery: '',
        sortDropdownOpen: false,
        filtersOpen: false,
        featureFlags: {
            pro_enabled: false,
            pro_features: [],
            free_features: []
        },
        userPermissions: window.inventoryPermissions || [],
        isSuperuser: window.inventoryIsSuperuser || false,
        maintenanceSummary: {
            pro_locked: true,
            open: 0,
            overdue: 0
        },
        enterpriseWorkflow: {
            score: 100,
            integration_score: 100,
            status_label: uiText('Lädt'),
            signals: [],
            next_actions: [],
            summary: {
                devices: 0,
                assets: 0,
                linked_assets: 0,
                issues: 0
            }
        },
        activityFeed: [],
        selectedDevice: null,
        deviceDetailOpen: false,
        selectedAsset: null,
        assetDetailOpen: false,
        binpackingPreviewOpen: false,
        binpackingPreviewLayerIndex: 0,
        binpackingPreviewActiveStep: null,
        binpackingPreviewCamera: 'iso',
        binpackingRotationX: 66,
        binpackingRotationZ: -38,
        binpacking3dDragging: false,
        binpacking3dDragStart: null,
        selectedAssetCategory: null,
        assetAssignmentHistory: [],
        assignmentModalOpen: false,
        assignmentAction: '',
        assignmentForm: {
            assigned_to_user_id: '',
            assigned_to_team_id: '',
            due_at: '',
            note: ''
        },
        assignmentOptions: {
            users: [],
            teams: []
        },
        assetAttachments: [],
        assetAttachmentError: '',
        assetFormErrors: {},
        assetFormMessage: '',
        deviceTags: [],
        deviceNotes: [],
        deviceFormErrors: {},
        deviceDirty: false,
        deviceSaving: false,
        assetDirty: false,
        assetSaving: false,
        assetDeviceQuery: '',
        assetDeviceCategory: '',
        assetDevicePage: 1,
        assetDeviceOnlySelected: false,
        deviceFormMessage: '',
        maintenanceTasks: [],
        maintenanceAttachments: {},
        maintenanceAttachmentErrors: {},
        newTag: '',
        newNote: '',
        newMaintenance: {
            title: '',
            due_date: ''
        },
        currentSort: { field: null, direction: null },
        otpModalOpen: false,
        otpSecret: '',
        otpQrCode: '',
        otpEnabled: false,
        
        // Modals
        isCategoryModalOpen: false,
        isAssetCategoryModalOpen: false,
        isDeviceModalOpen: false,
        isAssetModalOpen: false,
        isAssetCategoryModalOpen: false,
        editingCategory: null,
        editingAssetCategory: null,
        editingDevice: null,
        editingAsset: null,
        editingAssetCategory: null,
        categoryMenuOpen: null,  // Geändert von openCategoryId zu categoryMenuOpen für Konsistenz
        assetCategoryMenuOpen: null,
        openDeviceId: null,
        iconSearch: '',
        iconCatalog: [],
        
        // Current Items
        currentCategory: {
            id: null,
            name: '',
            icon: 'cpu',
            description: '',
            fields: []
        },
        currentAssetCategory: {
            id: null,
            name: '',
            icon: 'package',
            description: '',
            fields: [],
            binpacking_config: {
                enabled: false,
                content_category_id: '',
                allow_rotation: true,
                clearance: '',
                container_fields: {
                    width: '',
                    height: '',
                    depth: ''
                },
                item_fields: {
                    width: '',
                    height: '',
                    depth: ''
                }
            }
        },
        currentDevice: {
            id: null,
            name: '',
            category_id: null,
            serial_number: '',
            location_id: '',
            specs: {},
            extraSpecs: []
        },
        currentAsset: {
            id: null,
            name: '',
            category_id: null,
            notes: '',
            specs: {},
            extraSpecs: [],
            device_ids: [],
            acquisition_date: '',
            commissioning_date: '',
            warranty_end: '',
            depreciation_months: '',
            vendor_id: '',
            purchase_order_id: '',
            purchase_cost: '',
            currency: 'EUR',
            cost_center: '',
            invoice_number: '',
            retirement_date: '',
            retirement_reason: '',
            relations: []
        },

        // Initialization
        async init() {
            this.initWorkspaceViewFromUrl();
            await this.loadCategories();
            await this.loadAssetCategories();
            await this.loadLocations();
            await this.loadAllDevices();
            await this.loadDevices();
            this.applyInitialDeviceFilters();
            await this.loadAssetCategories();
            await this.loadAssets();
            await this.loadRelationTypes();
            await this.loadVendors();
            await this.loadPurchaseOrders();
            await this.loadFeatureFlags();
            await this.loadMaintenanceSummary();
            await this.loadDashboardTasks();
            await this.loadActivityFeed();
            await this.checkOTPStatus();
            this.loadIconCatalog();
            this.$watch('searchQuery', () => this.searchDevices());
            this.$watch('categorySearchQuery', () => this.filterCategories());
            this.$watch('assetCategorySearchQuery', () => this.filterAssetCategories());
            this.$watch('assetSearchQuery', () => this.filterAssets());
            this.$watch('ownerQuery', () => this.searchDevices());
            this.$watch('locationFilter', () => this.searchDevices());
            this.$watch('categoryFilter', () => this.searchDevices());
            this.$watch('createdFrom', () => this.searchDevices());
            this.$watch('createdTo', () => this.searchDevices());
            this.$watch('specQuery', () => this.searchDevices());
            this.refreshFeatherIcons();
            this.startLiveRefresh();
            window.addEventListener('beforeunload', event => {
                if (this.deviceDirty || this.assetDirty) { event.preventDefault(); event.returnValue = ''; }
            });
            await this.applyInventoryIntent();
        },

        async applyInventoryIntent() {
            const intent = new URLSearchParams(location.search);
            const deviceId = Number(intent.get('edit_device') || intent.get('manage_device'));
            const assetId = Number(intent.get('edit_asset') || intent.get('manage_asset'));
            const planId = Number(intent.get('preview_plan'));
            if (Number.isSafeInteger(planId) && planId > 0 && this.can('assets.view')) {
                const response = await fetch(`/api/planning/plans/${planId}`);
                if (response.ok) {
                    const plan = await response.json();
                    this.selectedAsset = { id: null, name: plan.name, binpacking: plan.preview };
                    this.openBinpackingPreview(this.selectedAsset);
                }
            }
            if (intent.get('create') === 'device' && this.can('devices.manage')) this.openAddDeviceModal();
            if (intent.get('create') === 'asset' && this.can('assets.manage')) this.openAddAssetModal();
            if (Number.isSafeInteger(deviceId) && deviceId > 0) {
                const device = this.devices.find(item => item.id === deviceId);
                if (device && intent.has('edit_device') && this.can('devices.manage')) this.openEditDeviceModal(device);
                else if (device && intent.has('manage_device')) await this.openDeviceDetail(device);
            }
            if (Number.isSafeInteger(assetId) && assetId > 0) {
                const asset = this.assets.find(item => item.id === assetId);
                if (asset && intent.has('edit_asset') && this.can('assets.manage')) await this.openEditAssetModal(asset);
                else if (asset && intent.has('manage_asset')) await this.openAssetDetail(asset);
            }
        },

        refreshFeatherIcons() {
            const replaceIcons = () => {
                if (typeof window.InventoryRefreshIcons === 'function') {
                    window.InventoryRefreshIcons();
                } else if (window.feather && typeof feather.replace === 'function') {
                    feather.replace();
                }
            };
            this.$nextTick(() => {
                replaceIcons();
                setTimeout(replaceIcons, 80);
            });
        },

        initWorkspaceViewFromUrl() {
            const params = new URLSearchParams(window.location.search || '');
            const requestedView = params.get('view');
            const allowedViews = ['overview', 'devices', 'assets', 'taxonomy'];
            this.workspaceView = allowedViews.includes(requestedView) ? requestedView : 'overview';
            this.inventoryTab = this.workspaceView === 'assets' ? 'assets' : 'devices';
            if (this.workspaceView === 'taxonomy') {
                this.inventoryTab = 'devices';
            }
        },

        setWorkspaceView(view) {
            const allowedViews = ['overview', 'devices', 'assets', 'taxonomy'];
            if (!allowedViews.includes(view)) {
                view = 'overview';
            }
            this.workspaceView = view;
            if (view === 'assets') {
                this.inventoryTab = 'assets';
            } else if (view === 'devices') {
                this.inventoryTab = 'devices';
            }
            if (view !== 'devices') {
                this.filtersOpen = false;
            }
            const url = new URL(window.location.href);
            if (view === 'overview') {
                url.searchParams.delete('view');
            } else {
                url.searchParams.set('view', view);
            }
            window.history.replaceState({}, '', url);
            this.refreshFeatherIcons();
        },

        workspaceTitle() {
            const titles = {
                overview: uiText('Inventar'),
                devices: this.activeCategory
                    ? this.getCategoryName(this.activeCategory)
                    : (this.locationFilter ? uiText("Geräte in {0}", [this.locationFilterName()]) : uiText('Geräte')),
                assets: this.selectedAssetCategory ? this.selectedAssetCategory.name : 'Assets',
                taxonomy: uiText('Struktur')
            };
            return titles[this.workspaceView] || uiText('Inventar');
        },

        workspaceDescription() {
            const descriptions = {
                overview: uiText('Überblick, nächste Aktionen und aktuelle Bewegung.'),
                devices: uiText('Geräte suchen, filtern und präzise pflegen.'),
                assets: uiText('Asset-Einträge, Komponenten, Zuweisungen und Lebenszyklus.'),
                taxonomy: uiText('Kategorien und Asset-Profile verwalten.')
            };
            return descriptions[this.workspaceView] || '';
        },

        can(permissionKey) {
            return this.isSuperuser || this.userPermissions.includes(permissionKey);
        },

        async loadFeatureFlags() {
            try {
                const response = await fetch('/api/features');
                if (response.ok) {
                    this.featureFlags = await response.json();
                }
            } catch (error) {
                console.error('Error loading feature flags:', error);
            }
        },

        async loadMaintenanceSummary() {
            try {
                const response = await fetch('/api/maintenance/summary');
                if (response.ok) {
                    this.maintenanceSummary = await response.json();
                }
            } catch (error) {
                console.error('Error loading maintenance summary:', error);
            }
        },

        async loadDashboardTasks() {
            this.dashboardTasksError = '';
            try {
                const response = await fetch('/api/workspace/tasks');
                if (!response.ok) throw new Error(uiText('Aufgaben konnten nicht geladen werden.'));
                this.dashboardTasks = (await response.json()).tasks;
            } catch (error) { this.dashboardTasksError = error.message; }
            finally { this.dashboardTasksLoading = false; }
        },

        async loadEnterpriseWorkflow() {
            try {
                const response = await fetch('/api/enterprise/workflow-hub');
                if (response.ok) {
                    this.enterpriseWorkflow = await response.json();
                }
            } catch (error) {
                console.error('Error loading enterprise workflow hub:', error);
            }
        },

        async loadActivityFeed() {
            try {
                const response = await fetch('/api/activity');
                if (response.ok) {
                    this.activityFeed = await response.json();
                }
            } catch (error) {
                console.error('Error loading activity feed:', error);
            }
        },

        startLiveRefresh() {
            setInterval(async () => {
                await this.loadActivityFeed();
                await this.loadMaintenanceSummary();
                await this.loadDashboardTasks();
            }, 15000);
        },

        async checkOTPStatus() {
            try {
                const response = await fetch('/api/otp/status', {
                    method: 'GET',
                    headers: { 'Content-Type': 'application/json' },
                    credentials: 'include'
                });
                const data = await response.json();
                this.otpEnabled = data.enabled;
            } catch (error) {
                console.error(uiText('Fehler beim Abrufen des 2FA-Status:'), error);
            }
        },

        async setupOTP() {
            try {
                const response = await fetch('/api/otp/setup', {
                    method: 'POST',
                    headers: { 'Content-Type': 'application/json' },
                    credentials: 'include'
                });
                const data = await response.json();

                if (data.enabled) {
                    const confirmed = confirm(uiText('2FA ist bereits aktiviert. Möchten Sie es deaktivieren?'));
                    if (confirmed) {
                        const disableResponse = await fetch('/api/otp/disable', {
                            method: 'POST',
                            headers: { 'Content-Type': 'application/json' },
                            credentials: 'include'
                        });
                        const disableData = await disableResponse.json();
                        if (disableData.disabled) {
                            this.otpEnabled = false;
                            alert('2FA wurde deaktiviert.');
                        } else {
                            alert(uiText('Fehler beim Deaktivieren von 2FA.'));
                        }
                    }
                    return;
                }

                this.otpSecret = data.secret;
                this.otpQrCode = data.qr_code;
                this.otpModalOpen = true;
            } catch (error) {
                console.error('Fehler:', error);
                alert(uiText('Ein Fehler ist aufgetreten'));
            }
        },
		
        // Data Loading
        async loadCategories() {
            const response = await fetch('/api/categories');
            if (response.ok) {
                this.categories = await response.json();
            }
        },

        async loadAssetCategories() {
            const response = await fetch('/api/asset-categories');
            if (response.ok) {
                this.assetCategories = await response.json();
            }
        },

        async loadLocations() {
            const response = await fetch('/api/locations');
            if (response.ok) {
                this.locations = await response.json();
            }
        },

        async loadDevices(categoryId = null) {
            this.activeCategory = categoryId;
            if (categoryId) {
                this.filtersOpen = false;
                this.setWorkspaceView('devices');
            }
            const url = categoryId 
                ? `/api/devices?category_id=${categoryId}`
                : '/api/devices';
            
            const response = await fetch(url);
            if (response.ok) {
                this.devices = await response.json();
                this.searchDevices();
                this.$nextTick(() => {
                    if (window.feather) {
                        feather.replace();
                    }
                });
            }
            if (this.selectedDevice) {
                const updated = this.devices.find(device => device.id === this.selectedDevice.id);
                if (updated) {
                    this.selectedDevice = updated;
                }
            }
        },
		
        async loadAllDevices() {
            const response = await fetch('/api/devices');
            if (response.ok) {
                this.allDevices = await response.json();
            }
        },

        async loadAssetCategories() {
            const response = await fetch('/api/asset-categories');
            if (response.ok) {
                this.assetCategories = await response.json();
            }
        },

        async loadAssets(categoryId = null) {
            const resolvedCategoryId = categoryId ?? this.selectedAssetCategory?.id;
            const url = resolvedCategoryId ? `/api/asset-entries?category_id=${resolvedCategoryId}` : '/api/asset-entries';
            const response = await fetch(url);
            if (response.ok) {
                this.assets = await response.json();
            }
        },

        matchingAssetDevices() {
            const query = this.assetDeviceQuery.trim().toLocaleLowerCase('de');
            return this.allDevices.filter(device =>
                (!this.assetDeviceCategory || Number(device.category_id) === Number(this.assetDeviceCategory)) &&
                (!this.assetDeviceOnlySelected || this.currentAsset.device_ids.some(id => Number(id) === device.id)) &&
                (!query || [device.name, device.serial_number, device.location_name].join(' ').toLocaleLowerCase('de').includes(query)));
        },
        visibleAssetDevices() {
            const rows = this.matchingAssetDevices();
            return rows.slice((this.assetDevicePage - 1) * 20, this.assetDevicePage * 20);
        },
        selectedAssetDevices() {
            return this.allDevices.filter(device => this.currentAsset.device_ids.some(id => Number(id) === device.id));
        },
        toggleAssetDevice(deviceId) {
            const ids = this.currentAsset.device_ids.map(Number);
            this.currentAsset.device_ids = ids.includes(deviceId) ? ids.filter(id => id !== deviceId) : [...ids, deviceId];
            this.assetDirty = true;
        },

        async loadAssetEntryOptions() {
            const response = await fetch('/api/asset-entries');
            if (response.ok) {
                this.assetEntryOptions = await response.json();
            }
        },

        async loadRelationTypes() {
            const response = await fetch('/api/asset-relation-types');
            if (response.ok) {
                this.relationTypes = await response.json();
            }
        },

        async loadVendors() {
            if (!this.can('procurement.view') && !this.can('procurement.manage')) {
                this.vendors = [];
                return;
            }
            const response = await fetch('/api/vendors');
            if (response.ok) {
                this.vendors = await response.json();
            }
        },

        async loadPurchaseOrders() {
            if (!this.can('procurement.view') && !this.can('procurement.manage')) {
                this.purchaseOrders = [];
                return;
            }
            const response = await fetch('/api/purchase-orders');
            if (response.ok) {
                this.purchaseOrders = await response.json();
            }
        },

        parseIconName(iconName) {
            const raw = (iconName || '').toString().trim();
            if (!raw) {
                return { set: 'feather', name: 'cpu' };
            }
            if (raw.includes(':')) {
                const [set, ...rest] = raw.split(':');
                return { set: set || 'feather', name: rest.join(':') };
            }
            return { set: 'feather', name: raw };
        },

        iconsMatch(leftIcon, rightIcon) {
            const left = this.parseIconName(leftIcon);
            const right = this.parseIconName(rightIcon);
            return left.set === right.set && left.name === right.name;
        },

        formatIconLabel(iconName) {
            const { set, name } = this.parseIconName(iconName);
            if (set === 'feather') {
                return name;
            }
            return `${set}:${name}`;
        },

        renderIconSvg(iconName, className) {
            const { set, name } = this.parseIconName(iconName);
            if (set === 'feather') {
                return window.feather?.icons?.[name]?.toSvg({ class: className }) || '';
            }
            if (set === 'tech') {
                const renderer = window.InventoryCustomIcons?.[name];
                return renderer ? renderer(className) : '';
            }
            return '';
        },

        loadIconCatalog() {
            const catalog = [];
            if (window.feather?.icons) {
                Object.keys(window.feather.icons).forEach(name => {
                    catalog.push(`feather:${name}`);
                });
            }
            if (window.InventoryCustomIcons) {
                Object.keys(window.InventoryCustomIcons).forEach(name => {
                    catalog.push(`tech:${name}`);
                });
            }
            this.iconCatalog = catalog.sort((a, b) => {
                return this.formatIconLabel(a).localeCompare(this.formatIconLabel(b));
            });
        },

        // Search and Sort
        applyInitialDeviceFilters() {
            const params = new URLSearchParams(window.location.search);
            const locationId = params.get('location');
            if (!locationId || !this.locations.some(location => String(location.id) === String(locationId))) return;

            this.setWorkspaceView('devices');
            this.activeCategory = null;
            this.locationFilter = String(locationId);
            this.filtersOpen = true;
            this.searchDevices();
            this.$nextTick(() => {
                window.requestAnimationFrame(() => {
                    document.getElementById('device-inventory')?.scrollIntoView({ block: 'start' });
                });
            });
        },

        locationFilterName() {
            if (!this.locationFilter) return '';
            return this.locations.find(location => String(location.id) === String(this.locationFilter))?.name || '';
        },

        clearLocationFilter() {
            this.locationFilter = '';
            const url = new URL(window.location.href);
            url.searchParams.delete('location');
            window.history.replaceState({}, '', `${url.pathname}${url.search}${url.hash}`);
            this.searchDevices();
        },

        async showAllDevices() {
            this.clearLocationFilter();
            await this.loadDevices();
            this.setWorkspaceView('devices');
        },

        searchDevices() {
            const matchesCreatedRange = (deviceDate) => {
                if (!deviceDate) return !this.createdFrom && !this.createdTo;
                const value = new Date(deviceDate);
                if (Number.isNaN(value.getTime())) return true;
                if (this.createdFrom) {
                    const fromDate = new Date(this.createdFrom);
                    if (!Number.isNaN(fromDate.getTime()) && value < fromDate) return false;
                }
                if (this.createdTo) {
                    const toDate = new Date(this.createdTo);
                    if (!Number.isNaN(toDate.getTime())) {
                        const endOfDay = new Date(toDate);
                        endOfDay.setHours(23, 59, 59, 999);
                        if (value > endOfDay) return false;
                    }
                }
                return true;
            };
            const normalize = (value) => (value || '').toString().toLowerCase();
            const query = normalize(this.searchQuery).trim();
            const ownerQuery = normalize(this.ownerQuery).trim();
            const specQuery = normalize(this.specQuery).trim();
            const locationFilter = this.locationFilter ? String(this.locationFilter) : '';
            const categoryFilter = this.categoryFilter ? String(this.categoryFilter) : '';

            if (!this.searchQuery) {
                this.filteredDevices = [...this.devices];
            }
            this.filteredDevices = this.devices.filter(device => {
                const deviceName = normalize(device.name);
                const ownerName = normalize(device.serial_number);
                const categoryName = normalize(device.category_name);
                const locationName = normalize(device.location_name);
                const specsString = normalize(JSON.stringify(device.specs || {}));
                const createdAt = device.created_at;

                const matchesQuery = !query ||
                    deviceName.includes(query) ||
                    ownerName.includes(query) ||
                    categoryName.includes(query) ||
                    locationName.includes(query) ||
                    specsString.includes(query);

                const matchesOwner = !ownerQuery || ownerName.includes(ownerQuery);
                const matchesLocation = !locationFilter || String(device.location_id || '') === locationFilter;
                const matchesCategory = !categoryFilter || String(device.category_id || '') === categoryFilter;
                const matchesSpecs = !specQuery || specsString.includes(specQuery);

                return matchesQuery && matchesOwner && matchesLocation && matchesCategory && matchesSpecs && matchesCreatedRange(createdAt);
            });
            
            // Apply current sort if one is active
            if (this.currentSort.field) {
                this.sortDevices(this.currentSort.field, this.currentSort.direction);
            }
        },

        filterCategories() {
            return this.filteredCategories();
        },

        filteredCategories() {
            const query = (this.categorySearchQuery || '').toLowerCase().trim();
            if (!query) {
                return this.categories;
            }
            return this.categories.filter(category =>
                (category.name || '').toLowerCase().includes(query)
            );
        },

        filterAssetCategories() {
            return this.filteredAssetCategories();
        },

        filteredAssetCategories() {
            const query = (this.assetCategorySearchQuery || '').toLowerCase().trim();
            if (!query) {
                return this.assetCategories;
            }
            return this.assetCategories.filter(category =>
                (category.name || '').toLowerCase().includes(query)
            );
        },

        filterAssets() {
            return this.filteredAssets();
        },

        filteredAssets() {
            const query = (this.assetSearchQuery || '').toLowerCase().trim();
            if (!query) {
                return this.assets;
            }
            return this.assets.filter(asset =>
                (asset.name || '').toLowerCase().includes(query) ||
                (asset.category_name || '').toLowerCase().includes(query)
            );
        },

        resetDeviceFilters() {
            this.searchQuery = '';
            this.ownerQuery = '';
            this.clearLocationFilter();
            this.categoryFilter = '';
            this.createdFrom = '';
            this.createdTo = '';
            this.specQuery = '';
            this.searchDevices();
        },

        toggleSortDropdown() {
            this.sortDropdownOpen = !this.sortDropdownOpen;
        },

        sortDevices(field, direction) {
            this.currentSort = { field, direction };
            this.sortDropdownOpen = false;
            
            this.filteredDevices.sort((a, b) => {
                let valueA = a[field];
                let valueB = b[field];
                
                // Handle cases where values might be null or undefined
                if (valueA === null || valueA === undefined) valueA = '';
                if (valueB === null || valueB === undefined) valueB = '';
                
                // Convert to string for case-insensitive comparison
                valueA = String(valueA).toLowerCase();
                valueB = String(valueB).toLowerCase();
                
                if (direction === 'asc') {
                    return valueA.localeCompare(valueB);
                } else {
                    return valueB.localeCompare(valueA);
                }
            });
        },

        // Category Methods
        openAddCategoryModal() {
            this.editingCategory = false;
            this.currentCategory = {
                id: null,
                name: '',
                icon: 'cpu',
                description: '',
                fields: []
            };
            this.iconSearch = '';
            this.isCategoryModalOpen = true;
            this.categoryMenuOpen = null; // Menü schließen beim Öffnen des Modals
        },

		editCategoryModal(category) {  // <-- Parameter korrekt entgegennehmen
            const fieldsObject = this.getCategoryFields(category.id) || {};
			this.editingCategory = true;
			this.currentCategory = {
				id: category.id,
				name: category.name,
				icon: category.icon,
                description: category.description || '',
				fields: Object.entries(fieldsObject).map(([fieldName, fieldConfig]) => {
                    const options = Array.isArray(fieldConfig?.options) ? fieldConfig.options : [];
                    return {
                        id: crypto.randomUUID(),
                        name: fieldName,
                        type: fieldConfig?.type || 'text',
                        options,
                        optionsText: options.join(', '),
                        unit: fieldConfig?.unit || ''
                    };
                })
			};
            this.iconSearch = '';
			this.isCategoryModalOpen = true;
			this.categoryMenuOpen = null; // Menü schließen beim Öffnen des Modals
		},

        closeCategoryModal() {
            this.isCategoryModalOpen = false;
        },

        addCategoryField() {
            this.currentCategory.fields.push({
                id: crypto.randomUUID(),
                name: '',
                type: 'text',
                options: [],
                optionsText: '',
                unit: ''
            });
        },

        removeCategoryField(fieldId) {
            this.currentCategory.fields = this.currentCategory.fields.filter(field => field.id !== fieldId);
        },

        moveCategoryField(fieldId, direction) {
            const currentIndex = this.currentCategory.fields.findIndex(field => field.id === fieldId);
            if (currentIndex < 0) return;
            const targetIndex = currentIndex + direction;
            if (targetIndex < 0 || targetIndex >= this.currentCategory.fields.length) return;
            const [field] = this.currentCategory.fields.splice(currentIndex, 1);
            this.currentCategory.fields.splice(targetIndex, 0, field);
        },

        filteredIconCatalog() {
            const query = this.iconSearch.trim().toLowerCase();
            if (!query) {
                return this.iconCatalog;
            }
            return this.iconCatalog.filter(iconName => {
                const { set, name } = this.parseIconName(iconName);
                const label = `${set}:${name}`;
                return name.includes(query) || set.includes(query) || label.includes(query);
            });
        },

        selectIcon(iconName) {
            this.currentCategory.icon = iconName;
        },

        selectAssetIcon(iconName) {
            this.currentAssetCategory.icon = iconName;
        },

        async saveCategory() {
            try {
                const fields = {};
                for (const field of this.currentCategory.fields) {
                    const trimmedName = field.name.trim();
                    if (!trimmedName) continue;
                    const unit = (field.unit || '').trim();
                    if (field.type === 'select') {
                        const options = (field.optionsText || '')
                            .split(',')
                            .map(option => option.trim())
                            .filter(Boolean);
                        fields[trimmedName] = {
                            type: field.type,
                            options,
                            unit: ''
                        };
                    } else {
                        fields[trimmedName] = {
                            type: field.type,
                            options: [],
                            unit
                        };
                    }
                }

                const categoryData = {
                    name: this.currentCategory.name,
                    icon: this.currentCategory.icon,
                    description: this.currentCategory.description,
                    fields
                };

                let response;
                if (this.editingCategory) {
                    response = await fetch(`/api/categories/${this.currentCategory.id}`, {
                        method: 'PUT',
                        headers: { 'Content-Type': 'application/json' },
                        body: JSON.stringify(categoryData)
                    });
                } else {
                    response = await fetch('/api/categories', {
                        method: 'POST',
                        headers: { 'Content-Type': 'application/json' },
                        body: JSON.stringify(categoryData)
                    });
                }

                if (!response.ok) {
                    const error = await response.json();
                    throw new Error(error.error || 'Failed to save category');
                }

                await this.loadCategories();
                this.closeCategoryModal();
                await this.loadActivityFeed();
            } catch (error) {
                console.error('Error saving category:', error);
                alert('Error saving category: ' + error.message);
            }
        },

        async deleteCategory(categoryId) {
            this.categoryModalOpen = false;
            this.openCategoryRemoval('device', categoryId);
            return false;
        },

        async confirmDeleteCategory() {
            if (!this.currentCategory.id) return;
            const deleted = await this.deleteCategory(this.currentCategory.id);
            if (deleted) {
                this.closeCategoryModal();
            }
        },

        // Asset Category Methods
        defaultBinpackingConfig() {
            return {
                enabled: false,
                content_category_id: '',
                allow_rotation: true,
                clearance: '',
                container_fields: {
                    width: '',
                    height: '',
                    depth: ''
                },
                item_fields: {
                    width: '',
                    height: '',
                    depth: ''
                }
            };
        },

        readBinpackingConfig(rawConfig) {
            const defaults = this.defaultBinpackingConfig();
            let parsed = rawConfig;
            if (typeof rawConfig === 'string') {
                try {
                    parsed = JSON.parse(rawConfig || '{}');
                } catch (error) {
                    console.error('Error parsing binpacking config:', error);
                    return defaults;
                }
            }
            if (!parsed || typeof parsed !== 'object') {
                return defaults;
            }

            const normalizeMapping = (mapping) => ({
                width: (mapping?.width || '').toString(),
                height: (mapping?.height || '').toString(),
                depth: (mapping?.depth || '').toString()
            });

            return {
                enabled: !!parsed.enabled,
                content_category_id: parsed.content_category_id ? String(parsed.content_category_id) : '',
                allow_rotation: parsed.allow_rotation !== false,
                clearance: parsed.clearance ?? '',
                container_fields: normalizeMapping(parsed.container_fields),
                item_fields: normalizeMapping(parsed.item_fields)
            };
        },

        getCurrentAssetCategoryNumberFields() {
            return (this.currentAssetCategory.fields || []).filter((field) => field.type === 'number');
        },

        getBinpackingTargetCategory() {
            const targetId = this.currentAssetCategory?.binpacking_config?.content_category_id;
            if (!targetId) {
                return null;
            }
            return this.getAssetCategoryById(targetId);
        },

        getBinpackingTargetNumberFields() {
            const targetCategory = this.getBinpackingTargetCategory();
            if (!targetCategory) {
                return [];
            }
            return this.getAssetCategoryFieldEntries(targetCategory.id).filter((field) => field.type === 'number');
        },

        buildAssetCategoryBinpackingPayload() {
            const config = this.currentAssetCategory.binpacking_config || this.defaultBinpackingConfig();
            if (!config.enabled) {
                return { enabled: false };
            }

            const normalizeMapping = (mapping) => ({
                width: (mapping?.width || '').toString().trim(),
                height: (mapping?.height || '').toString().trim(),
                depth: (mapping?.depth || '').toString().trim()
            });

            return {
                enabled: true,
                content_category_id: config.content_category_id ? Number(config.content_category_id) : null,
                allow_rotation: config.allow_rotation !== false,
                clearance: config.clearance === '' ? 0 : Number(config.clearance),
                container_fields: normalizeMapping(config.container_fields),
                item_fields: normalizeMapping(config.item_fields)
            };
        },

        openAddAssetCategoryModal() {
            this.editingAssetCategory = false;
            this.currentAssetCategory = {
                id: null,
                name: '',
                icon: 'package',
                description: '',
                fields: [],
                binpacking_config: this.defaultBinpackingConfig()
            };
            this.iconSearch = '';
            this.isAssetCategoryModalOpen = true;
            this.assetCategoryMenuOpen = null;
        },

        openEditAssetCategoryModal(category) {
            this.editingAssetCategory = true;
            const parsedFields = this.getAssetCategoryFields(category.id) || {};
            this.currentAssetCategory = {
                id: category.id,
                name: category.name,
                icon: category.icon || 'package',
                description: category.description || '',
                fields: Object.entries(parsedFields).map(([fieldName, fieldConfig]) => {
                    const options = fieldConfig?.options || [];
                    return {
                        id: crypto.randomUUID(),
                        name: fieldName,
                        type: fieldConfig?.type || 'text',
                        options,
                        optionsText: options.join(', '),
                        unit: fieldConfig?.unit || ''
                    };
                }),
                binpacking_config: this.readBinpackingConfig(category.binpacking_config)
            };
            this.iconSearch = '';
            this.isAssetCategoryModalOpen = true;
            this.assetCategoryMenuOpen = null;
        },

        closeAssetCategoryModal() {
            this.isAssetCategoryModalOpen = false;
        },

        addAssetCategoryField() {
            this.currentAssetCategory.fields.push({
                id: crypto.randomUUID(),
                name: '',
                type: 'text',
                options: [],
                optionsText: '',
                unit: ''
            });
        },

        removeAssetCategoryField(fieldId) {
            this.currentAssetCategory.fields = this.currentAssetCategory.fields.filter(field => field.id !== fieldId);
        },

        moveAssetCategoryField(fieldId, direction) {
            const currentIndex = this.currentAssetCategory.fields.findIndex(field => field.id === fieldId);
            if (currentIndex < 0) return;
            const targetIndex = currentIndex + direction;
            if (targetIndex < 0 || targetIndex >= this.currentAssetCategory.fields.length) return;
            const [field] = this.currentAssetCategory.fields.splice(currentIndex, 1);
            this.currentAssetCategory.fields.splice(targetIndex, 0, field);
        },

        async saveAssetCategory() {
            try {
                const fields = {};
                for (const field of this.currentAssetCategory.fields) {
                    const trimmedName = field.name.trim();
                    if (!trimmedName) continue;
                    const unit = (field.unit || '').trim();
                    if (field.type === 'select') {
                        const options = (field.optionsText || '')
                            .split(',')
                            .map(option => option.trim())
                            .filter(Boolean);
                        fields[trimmedName] = {
                            type: field.type,
                            options,
                            unit: ''
                        };
                    } else {
                        fields[trimmedName] = {
                            type: field.type,
                            options: [],
                            unit
                        };
                    }
                }

                const categoryData = {
                    name: this.currentAssetCategory.name,
                    icon: this.currentAssetCategory.icon,
                    description: this.currentAssetCategory.description,
                    fields,
                    binpacking_config: this.buildAssetCategoryBinpackingPayload()
                };

                let response;
                if (this.editingAssetCategory) {
                    response = await fetch(`/api/asset-categories/${this.currentAssetCategory.id}`, {
                        method: 'PUT',
                        headers: { 'Content-Type': 'application/json' },
                        body: JSON.stringify(categoryData)
                    });
                } else {
                    response = await fetch('/api/asset-categories', {
                        method: 'POST',
                        headers: { 'Content-Type': 'application/json' },
                        body: JSON.stringify(categoryData)
                    });
                }

                if (!response.ok) {
                    const error = await response.json();
                    if (error.field_errors) {
                        const messages = Object.values(error.field_errors).join(' | ');
                        throw new Error(messages || error.error || uiText('Asset-Kategorie konnte nicht gespeichert werden'));
                    }
                    throw new Error(error.error || 'Failed to save asset category');
                }

                await this.loadAssetCategories();
                this.closeAssetCategoryModal();
                await this.loadAssets();
                await this.loadActivityFeed();
            } catch (error) {
                console.error('Error saving asset category:', error);
                alert('Error saving asset category: ' + error.message);
            }
        },

        async deleteAssetCategory(categoryId) {
            this.assetCategoryModalOpen = false;
            this.openCategoryRemoval('asset', categoryId);
            return false;
        },

        async confirmDeleteAssetCategory() {
            if (!this.currentAssetCategory.id) return;
            const deleted = await this.deleteAssetCategory(this.currentAssetCategory.id);
            if (deleted) {
                this.closeAssetCategoryModal();
            }
        },

        async selectAssetCategory(category) {
            this.selectedAssetCategory = category;
            this.setWorkspaceView('assets');
            await this.loadAssets(category.id);
        },

        async clearAssetCategorySelection() {
            this.selectedAssetCategory = null;
            this.setWorkspaceView('assets');
            await this.loadAssets();
        },

        toggleCategoryMenu(categoryId) {
            this.categoryMenuOpen = this.categoryMenuOpen === categoryId ? null : categoryId;
            // Schließe das Geräte-Menü, wenn ein Kategorie-Menü geöffnet wird
            if (this.categoryMenuOpen !== null) {
                this.openDeviceId = null;
            }
        },

        // Device Methods
        async openAddDeviceModal() {
            this.deviceDirty = false;
            this.clearDeviceFormState();
            if (this.categories.length === 0) {
                await this.loadCategories();
            }
            if (this.allDevices.length === 0) {
                await this.loadAllDevices();
            }
            const defaultCategoryId = this.activeCategory || this.categories[0]?.id || '';
            this.editingDevice = false;
            this.currentDevice = {
                id: null,
                name: '',
                category_id: defaultCategoryId,
                serial_number: '',
                location_id: '',
                specs: {},
                extraSpecs: []
            };
            this.isDeviceModalOpen = true;
            this.handleDeviceCategoryChange();
        },

        openEditDeviceModal(device) {
            this.deviceDirty = false;
            this.clearDeviceFormState();
            const specs = JSON.parse(device.specs || '{}');
            const categoryFields = this.getCategoryFields(device.category_id) || {};
            const baseSpecs = {};
            const extraSpecs = [];

            Object.entries(specs).forEach(([key, value]) => {
                if (categoryFields && Object.prototype.hasOwnProperty.call(categoryFields, key)) {
                    baseSpecs[key] = value;
                } else {
                    extraSpecs.push({
                        id: crypto.randomUUID(),
                        name: key,
                        value
                    });
                }
            });
            this.editingDevice = true;
            this.currentDevice = {
                id: device.id,
                name: device.name,
                category_id: device.category_id,
                serial_number: device.serial_number,
                location_id: device.location_id || '',
                specs: baseSpecs,
                extraSpecs
            };
            this.isDeviceModalOpen = true;
        },

        closeDeviceModal() {
            if (this.deviceSaving) return;
            if (this.deviceDirty && !confirm(uiText('Ungespeicherte Änderungen verwerfen?'))) return;
            this.deviceDirty = false;
            this.isDeviceModalOpen = false;
            this.clearDeviceFormState();
        },

        addExtraSpec() {
            this.currentDevice.extraSpecs.push({
                id: crypto.randomUUID(),
                name: '',
                value: ''
            });
        },

        removeExtraSpec(specId) {
            this.currentDevice.extraSpecs = this.currentDevice.extraSpecs.filter(spec => spec.id !== specId);
        },

        handleDeviceCategoryChange() {
            const fieldNames = new Set(
                this.getCategoryFieldEntries(this.currentDevice.category_id).map((field) => field.name)
            );
            const nextSpecs = {};
            Object.entries(this.currentDevice.specs || {}).forEach(([key, value]) => {
                if (fieldNames.has(key)) {
                    nextSpecs[key] = value;
                }
            });
            this.currentDevice.specs = nextSpecs;

            if (!this.editingDevice && !String(this.currentDevice.name || '').trim() && !String(this.currentDevice.serial_number || '').trim()) {
                this.applySuggestedDeviceIdentity();
            }
        },

        getCategoryCounterPrefix(categoryId) {
            const category = this.getCategoryById(categoryId);
            const rawName = String(category?.name || 'Device')
                .normalize('NFKD')
                .replace(/[^\w\s-]/g, '')
                .trim()
                .replace(/\s+/g, '-');
            return `${rawName || 'Device'}-`;
        },

        extractTrailingCounter(value) {
            const normalized = String(value || '').trim();
            if (!normalized) {
                return null;
            }
            const match = normalized.match(/^(.*?)(\d+)\s*$/);
            if (!match) {
                return null;
            }
            return {
                prefix: match[1] || '',
                number: Number.parseInt(match[2], 10),
                width: match[2].length,
            };
        },

        buildCounterSuggestion(values, fallbackPrefix) {
            const candidates = values
                .map((value) => this.extractTrailingCounter(value))
                .filter((candidate) => candidate && Number.isFinite(candidate.number));

            if (!candidates.length) {
                return `${fallbackPrefix}${String(1).padStart(3, '0')}`;
            }

            const best = candidates.reduce((currentBest, candidate) => {
                if (!currentBest) {
                    return candidate;
                }
                if (candidate.number > currentBest.number) {
                    return candidate;
                }
                if (candidate.number === currentBest.number && candidate.width > currentBest.width) {
                    return candidate;
                }
                return currentBest;
            }, null);

            const prefix = String(best?.prefix || '').trim() || fallbackPrefix;
            const nextNumber = (best?.number || 0) + 1;
            const width = Math.max(best?.width || 0, 3);
            return `${prefix}${String(nextNumber).padStart(width, '0')}`;
        },

        getDeviceIdentitySuggestions() {
            const categoryId = this.currentDevice.category_id || this.activeCategory;
            if (!categoryId) {
                return { name: '', serial_number: '' };
            }

            const devices = this.getDevicesForCategory(categoryId).filter((device) => {
                return !this.currentDevice.id || String(device.id) !== String(this.currentDevice.id);
            });
            const fallbackPrefix = this.getCategoryCounterPrefix(categoryId);
            const nameSuggestion = this.buildCounterSuggestion(
                devices.map((device) => device.name).filter(Boolean),
                fallbackPrefix
            );
            const serialSuggestion = this.buildCounterSuggestion(
                devices.map((device) => device.serial_number).filter(Boolean),
                fallbackPrefix
            );

            return {
                name: nameSuggestion,
                serial_number: serialSuggestion || nameSuggestion,
            };
        },

        applySuggestedDeviceIdentity(force = false) {
            if (this.editingDevice) {
                return;
            }
            const suggestions = this.getDeviceIdentitySuggestions();
            if (suggestions.name && (force || !String(this.currentDevice.name || '').trim())) {
                this.currentDevice.name = suggestions.name;
            }
            if (suggestions.serial_number && (force || !String(this.currentDevice.serial_number || '').trim())) {
                this.currentDevice.serial_number = suggestions.serial_number;
            }
        },

        async saveDevice() {
            if (this.deviceSaving) return;
            this.deviceSaving = true;
            try {
                this.clearDeviceFormState();
                const specs = { ...this.currentDevice.specs };
                this.currentDevice.extraSpecs.forEach((spec) => {
                    const trimmedName = spec.name.trim();
                    if (!trimmedName) return;
                    specs[trimmedName] = spec.value;
                });

                if (!String(this.currentDevice.name || '').trim()) {
                    this.deviceFormErrors = { name: 'Name ist erforderlich' };
                    this.deviceFormMessage = uiText('Bitte die markierten Felder prüfen.');
                    return;
                }

                if (!this.currentDevice.category_id) {
                    this.deviceFormErrors = { category_id: uiText('Kategorie ist erforderlich') };
                    this.deviceFormMessage = uiText('Bitte die markierten Felder prüfen.');
                    return;
                }

                const deviceData = {
                    name: this.currentDevice.name,
                    category_id: this.currentDevice.category_id || this.activeCategory,
                    serial_number: this.currentDevice.serial_number,
                    location_id: this.currentDevice.location_id || null,
                    specs
                };

                let response;
                if (this.editingDevice) {
                    response = await fetch(`/api/devices/${this.currentDevice.id}`, {
                        method: 'PUT',
                        headers: { 'Content-Type': 'application/json' },
                        body: JSON.stringify(deviceData)
                    });
                } else {
                    response = await fetch('/api/devices', {
                        method: 'POST',
                        headers: { 'Content-Type': 'application/json' },
                        body: JSON.stringify(deviceData)
                    });
                }

                if (!response.ok) {
                    const error = await this.readErrorPayload(response, uiText('Gerät konnte nicht gespeichert werden'));
                    this.deviceFormErrors = error.field_errors || {};
                    this.deviceFormMessage = error.error || uiText('Gerät konnte nicht gespeichert werden');
                    return;
                }

                await this.loadDevices(this.activeCategory);
                await this.loadAllDevices();
                this.deviceDirty = false;
                this.deviceSaving = false;
                this.closeDeviceModal();
                await this.loadActivityFeed();
            } catch (error) {
                console.error('Error saving device:', error);
                this.deviceFormMessage = error.message || uiText('Gerät konnte nicht gespeichert werden');
            } finally { this.deviceSaving = false; }
        },

        async deleteDevice(deviceId) {
            if (confirm(uiText('Möchten Sie dieses Gerät wirklich löschen?'))) {
                const response = await fetch(`/api/devices/${deviceId}`, {
                    method: 'DELETE'
                });
                if (response.ok) {
                    await this.loadDevices(this.activeCategory);
                    await this.loadAllDevices();
                    if (this.selectedDevice?.id === deviceId) {
                        this.closeDeviceDetail();
                    }
                    await this.loadActivityFeed();
                } else {
                    const error = await response.json();
                    alert(error.error || uiText('Gerät konnte nicht gelöscht werden'));
                }
            }
        },

        toggleDeviceMenu(deviceId) {
            this.openDeviceId = this.openDeviceId === deviceId ? null : deviceId;
            // Schließe das Kategorie-Menü, wenn ein Geräte-Menü geöffnet wird
            if (this.openDeviceId !== null) {
                this.categoryMenuOpen = null;
            }
        },

        async openDeviceDetail(device) {
            this.selectedDevice = device;
            this.deviceDetailOpen = true;
            await this.loadDeviceExtras(device.id);
        },

        closeDeviceDetail() {
            this.deviceDetailOpen = false;
            this.selectedDevice = null;
            this.deviceTags = [];
            this.deviceNotes = [];
            this.maintenanceTasks = [];
            this.maintenanceAttachments = {};
            this.maintenanceAttachmentErrors = {};
        },

        async loadDeviceExtras(deviceId) {
            try {
                const [tagsRes, notesRes] = await Promise.all([
                    fetch(`/api/devices/${deviceId}/tags`),
                    fetch(`/api/devices/${deviceId}/notes`)
                ]);
                if (tagsRes.ok) {
                    this.deviceTags = await tagsRes.json();
                }
                if (notesRes.ok) {
                    this.deviceNotes = await notesRes.json();
                }
            } catch (error) {
                console.error('Error loading device extras:', error);
            }

            try {
                const maintenanceRes = await fetch(`/api/maintenance?device_id=${deviceId}`);
                if (maintenanceRes.ok) {
                    this.maintenanceTasks = await maintenanceRes.json();
                    await this.loadMaintenanceAttachments();
                }
            } catch (error) {
                console.error('Error loading maintenance tasks:', error);
            }
        },

        async addTag() {
            if (!this.newTag.trim() || !this.selectedDevice) return;
            try {
                const response = await fetch(`/api/devices/${this.selectedDevice.id}/tags`, {
                    method: 'POST',
                    headers: { 'Content-Type': 'application/json' },
                    body: JSON.stringify({ tag: this.newTag.trim() })
                });
                if (response.ok) {
                    this.newTag = '';
                    await this.loadDeviceExtras(this.selectedDevice.id);
                    await this.loadActivityFeed();
                } else {
                    const error = await response.json();
                    alert(error.error || uiText('Tag konnte nicht gespeichert werden'));
                }
            } catch (error) {
                console.error(uiText('Error adding tag:'), error);
            }
        },

        async removeTag(tagId) {
            if (!this.selectedDevice) return;
            try {
                const response = await fetch(`/api/devices/${this.selectedDevice.id}/tags/${tagId}`, {
                    method: 'DELETE'
                });
                if (response.ok) {
                    await this.loadDeviceExtras(this.selectedDevice.id);
                    await this.loadActivityFeed();
                }
            } catch (error) {
                console.error(uiText('Error removing tag:'), error);
            }
        },

        async addNote() {
            if (!this.newNote.trim() || !this.selectedDevice) return;
            try {
                const response = await fetch(`/api/devices/${this.selectedDevice.id}/notes`, {
                    method: 'POST',
                    headers: { 'Content-Type': 'application/json' },
                    body: JSON.stringify({ note: this.newNote.trim() })
                });
                if (response.ok) {
                    this.newNote = '';
                    await this.loadDeviceExtras(this.selectedDevice.id);
                    await this.loadActivityFeed();
                } else {
                    const error = await response.json();
                    alert(error.error || uiText('Notiz konnte nicht gespeichert werden'));
                }
            } catch (error) {
                console.error('Error adding note:', error);
            }
        },

        async deleteNote(noteId) {
            if (!this.selectedDevice) return;
            try {
                const response = await fetch(`/api/devices/${this.selectedDevice.id}/notes/${noteId}`, {
                    method: 'DELETE'
                });
                if (response.ok) {
                    await this.loadDeviceExtras(this.selectedDevice.id);
                    await this.loadActivityFeed();
                }
            } catch (error) {
                console.error('Error deleting note:', error);
            }
        },

        async addMaintenanceTask() {
            if (!this.selectedDevice) return;
            if (!this.newMaintenance.title.trim()) return;
            try {
                const response = await fetch('/api/maintenance', {
                    method: 'POST',
                    headers: { 'Content-Type': 'application/json' },
                    body: JSON.stringify({
                        device_id: this.selectedDevice.id,
                        title: this.newMaintenance.title.trim(),
                        due_date: this.newMaintenance.due_date
                    })
                });
                if (response.ok) {
                    this.newMaintenance = { title: '', due_date: '' };
                    await this.loadDeviceExtras(this.selectedDevice.id);
                    await this.loadMaintenanceSummary();
                    await this.loadActivityFeed();
                } else {
                    const error = await response.json();
                    alert(error.error || uiText('Wartung konnte nicht gespeichert werden'));
                }
            } catch (error) {
                console.error('Error adding maintenance task:', error);
            }
        },

        async updateMaintenanceStatus(taskId, status) {
            try {
                const response = await fetch(`/api/maintenance/${taskId}`, {
                    method: 'PATCH',
                    headers: { 'Content-Type': 'application/json' },
                    body: JSON.stringify({ status })
                });
                if (response.ok) {
                    await this.loadDeviceExtras(this.selectedDevice.id);
                    await this.loadMaintenanceSummary();
                    await this.loadActivityFeed();
                }
            } catch (error) {
                console.error('Error updating maintenance task:', error);
            }
        },

        async loadMaintenanceAttachments() {
            this.maintenanceAttachments = {};
            this.maintenanceAttachmentErrors = {};
            if (!this.can('attachment.download')) {
                return;
            }
            const tasks = this.maintenanceTasks || [];
            await Promise.all(tasks.map(async (task) => {
                const response = await fetch(`/attachments?entity_type=maintenance&entity_id=${task.id}`);
                if (response.ok) {
                    this.maintenanceAttachments[task.id] = await response.json();
                } else {
                    this.maintenanceAttachments[task.id] = [];
                }
            }));
        },

        async uploadMaintenanceAttachment(taskId, event) {
            const file = event.target.files?.[0];
            if (!file) return;
            const formData = new FormData();
            formData.append('entity_type', 'maintenance');
            formData.append('entity_id', taskId);
            formData.append('file', file);
            this.maintenanceAttachmentErrors[taskId] = '';
            const response = await fetch('/attachments/upload', {
                method: 'POST',
                body: formData
            });
            if (response.ok) {
                await this.loadMaintenanceAttachments();
            } else {
                const error = await response.json();
                this.maintenanceAttachmentErrors[taskId] = error.error || uiText('Upload fehlgeschlagen');
            }
            event.target.value = '';
        },

        async deleteMaintenanceAttachment(taskId, attachmentId) {
            if (!confirm(uiText('Anhang wirklich löschen?'))) return;
            const response = await fetch(`/attachments/${attachmentId}/delete`, { method: 'POST' });
            if (response.ok) {
                await this.loadMaintenanceAttachments();
            }
        },

        formatActivity(item) {
            const name = item.details?.name || item.details?.tag || '';
            const label = `${item.action} ${item.entity_type}`.replace('_', ' ');
            return `${label}${name ? ` • ${name}` : ''}`;
        },

        formatFileSize(bytes) {
            if (!bytes && bytes !== 0) return '-';
            if (bytes < 1024) return `${bytes} B`;
            const kb = bytes / 1024;
            if (kb < 1024) return `${kb.toFixed(1)} KB`;
            const mb = kb / 1024;
            return `${mb.toFixed(1)} MB`;
        },

        formatCurrency(amount, currency) {
            if (amount === null || amount === undefined || amount === '') return '-';
            const value = Number(amount);
            if (Number.isNaN(value)) return amount;
            const code = currency || 'EUR';
            try {
                return new Intl.NumberFormat('de-DE', { style: 'currency', currency: code }).format(value);
            } catch (error) {
                return `${value.toFixed(2)} ${code}`;
            }
        },

        assignmentStatusLabel(status) {
            const labels = {
                assigned: uiText('Zugewiesen'),
                checked_out: uiText('Ausgegeben'),
                checked_in: 'Eingecheckt',
                transferred: uiText('Übertragen'),
                unassigned: uiText('Nicht zugewiesen')
            };
            return labels[status] || status || '-';
        },

        assignmentTargetLabel(assignment) {
            if (!assignment) return '-';
            if (assignment.assigned_user) return assignment.assigned_user;
            if (assignment.assigned_team) return assignment.assigned_team;
            return '-';
        },

        async loadAssetAssignmentHistory(assetId) {
            if (!this.can('asset.view_history')) {
                this.assetAssignmentHistory = [];
                return;
            }
            const response = await fetch(`/assets/${assetId}/history`);
            if (response.ok) {
                this.assetAssignmentHistory = await response.json();
            }
        },

        async loadAssetAssignmentOptions() {
            if (this.assignmentOptions.users.length || this.assignmentOptions.teams.length) {
                return;
            }
            const response = await fetch('/api/asset-assignments/options');
            if (response.ok) {
                this.assignmentOptions = await response.json();
            }
        },

        openAssetAssignmentModal(action) {
            this.assignmentAction = action;
            this.assignmentForm = {
                assigned_to_user_id: '',
                assigned_to_team_id: '',
                due_at: '',
                note: ''
            };
            if (action === 'assign' || action === 'checkout') {
                this.loadAssetAssignmentOptions();
            }
            this.assignmentModalOpen = true;
        },

        closeAssetAssignmentModal() {
            this.assignmentModalOpen = false;
            this.assignmentAction = '';
        },

        async submitAssetAssignment() {
            if (!this.selectedAsset) return;
            const payload = {
                assigned_to_user_id: this.assignmentForm.assigned_to_user_id || null,
                assigned_to_team_id: this.assignmentForm.assigned_to_team_id || null,
                due_at: this.assignmentForm.due_at || null,
                note: this.assignmentForm.note || ''
            };
            const endpointMap = {
                assign: 'assign',
                checkout: 'checkout',
                checkin: 'checkin',
                unassign: 'unassign'
            };
            const endpoint = endpointMap[this.assignmentAction];
            if (!endpoint) return;
            const response = await fetch(`/assets/${this.selectedAsset.id}/${endpoint}`, {
                method: 'POST',
                headers: { 'Content-Type': 'application/json' },
                body: JSON.stringify(payload)
            });
            if (response.ok) {
                const result = await response.json();
                this.selectedAsset.assignment = result.assignment;
                this.assetAssignmentHistory = result.history || [];
                await this.loadAssets();
                await this.loadActivityFeed();
                this.closeAssetAssignmentModal();
            } else {
                const error = await response.json();
                alert(error.error || uiText('Zuweisung konnte nicht gespeichert werden'));
            }
        },

        async loadAssetAttachments(assetId) {
            const response = await fetch(`/attachments?entity_type=asset&entity_id=${assetId}`);
            if (response.ok) {
                this.assetAttachments = await response.json();
            }
        },

        async uploadAssetAttachment(event) {
            if (!this.selectedAsset) return;
            const file = event.target.files?.[0];
            if (!file) return;
            const formData = new FormData();
            formData.append('entity_type', 'asset');
            formData.append('entity_id', this.selectedAsset.id);
            formData.append('file', file);
            this.assetAttachmentError = '';
            const response = await fetch('/attachments/upload', {
                method: 'POST',
                body: formData
            });
            if (response.ok) {
                await this.loadAssetAttachments(this.selectedAsset.id);
            } else {
                const error = await response.json();
                this.assetAttachmentError = error.error || uiText('Upload fehlgeschlagen');
            }
            event.target.value = '';
        },

        async deleteAssetAttachment(attachmentId) {
            if (!confirm(uiText('Anhang wirklich löschen?'))) return;
            const response = await fetch(`/attachments/${attachmentId}/delete`, { method: 'POST' });
            if (response.ok && this.selectedAsset) {
                await this.loadAssetAttachments(this.selectedAsset.id);
            }
        },

        // Asset Entry Methods
        async openAddAssetModal() {
            if (this.assetCategories.length === 0) {
                alert(uiText('Bitte zuerst eine Asset-Kategorie anlegen.'));
                return;
            }
            this.clearAssetFormState();
            this.editingAsset = false;
            if (this.assetCategories.length === 0) {
                await this.loadAssetCategories();
            }
            this.currentAsset = {
                id: null,
                name: '',
                category_id: this.assetCategories[0]?.id || null,
                notes: '',
                specs: {},
                extraSpecs: [],
                device_ids: [],
                acquisition_date: '',
                commissioning_date: '',
                warranty_end: '',
                depreciation_months: '',
                vendor_id: '',
                purchase_order_id: '',
                purchase_cost: '',
                currency: 'EUR',
                cost_center: '',
                invoice_number: '',
                retirement_date: '',
                retirement_reason: '',
                relations: []
            };
            if (this.allDevices.length === 0) {
                await this.loadAllDevices();
            }
            if (this.assetEntryOptions.length === 0) {
                await this.loadAssetEntryOptions();
            }
            if (this.relationTypes.length === 0) {
                await this.loadRelationTypes();
            }
            if (this.vendors.length === 0) {
                await this.loadVendors();
            }
            if (this.purchaseOrders.length === 0) {
                await this.loadPurchaseOrders();
            }
            this.assetDirty = false;
            this.assetDevicePage = 1;
            this.isAssetModalOpen = true;
        },

        async openEditAssetModal(asset) {
            try {
                this.clearAssetFormState();
                const response = await fetch(`/api/asset-entries/${asset.id}`);
                if (!response.ok) {
                    throw new Error(uiText('Asset konnte nicht geladen werden'));
                }
                const data = await response.json();
                if (this.assetCategories.length === 0) {
                    await this.loadAssetCategories();
                }
                const splitSpecs = this.splitAssetSpecsByCategory(data.category_id, data.specs || {});
                this.editingAsset = true;
                this.currentAsset = {
                    id: data.id,
                    name: data.name,
                    category_id: data.category_id || null,
                    notes: data.notes || '',
                    specs: splitSpecs.categorySpecs || {},
                    extraSpecs: splitSpecs.extraSpecs || [],
                    device_ids: (data.devices || []).map(device => device.id),
                    acquisition_date: data.acquisition_date || '',
                    commissioning_date: data.commissioning_date || '',
                    warranty_end: data.warranty_end || '',
                    depreciation_months: data.depreciation_months ?? '',
                    vendor_id: data.vendor_id || '',
                    purchase_order_id: data.purchase_order_id || '',
                    purchase_cost: data.purchase_cost ?? '',
                    currency: data.currency || 'EUR',
                    cost_center: data.cost_center || '',
                    invoice_number: data.invoice_number || '',
                    retirement_date: data.retirement_date || '',
                    retirement_reason: data.retirement_reason || '',
                    relations: (data.relations || [])
                        .filter(relation => relation.direction === 'outgoing')
                        .map((relation) => ({
                            id: relation.id || crypto.randomUUID(),
                            related_asset_id: relation.related_asset_id,
                            relation_type_id: relation.relation_type_id || ''
                        }))
                };
                if (this.assetEntryOptions.length === 0) {
                    await this.loadAssetEntryOptions();
                }
                if (this.relationTypes.length === 0) {
                    await this.loadRelationTypes();
                }
                if (this.vendors.length === 0) {
                    await this.loadVendors();
                }
                if (this.purchaseOrders.length === 0) {
                    await this.loadPurchaseOrders();
                }
                this.assetDirty = false;
            this.assetDevicePage = 1;
            this.isAssetModalOpen = true;
            } catch (error) {
                console.error('Error loading asset:', error);
                alert(error.message);
            }
        },

        closeAssetModal() {
            if (this.assetSaving) return;
            if (this.assetDirty && !confirm(uiText('Ungespeicherte Änderungen verwerfen?'))) return;
            this.assetDirty = false;
            this.isAssetModalOpen = false;
            this.clearAssetFormState();
        },

        addAssetSpec() {
            this.currentAsset.extraSpecs.push({
                id: crypto.randomUUID(),
                name: '',
                value: ''
            });
        },

        removeAssetSpec(specId) {
            this.currentAsset.extraSpecs = this.currentAsset.extraSpecs.filter(spec => spec.id !== specId);
        },

        addAssetRelation() {
            this.currentAsset.relations.push({
                id: crypto.randomUUID(),
                related_asset_id: '',
                relation_type_id: ''
            });
        },

        removeAssetRelation(relationId) {
            this.currentAsset.relations = this.currentAsset.relations.filter(relation => relation.id !== relationId);
        },

        async saveAsset() {
            if (this.assetSaving) return;
            this.assetSaving = true;
            try {
                this.clearAssetFormState();
                const specs = { ...this.currentAsset.specs };
                this.currentAsset.extraSpecs.forEach((spec) => {
                    const trimmedName = spec.name.trim();
                    if (!trimmedName) return;
                    specs[trimmedName] = spec.value;
                });

                if (!String(this.currentAsset.name || '').trim()) {
                    this.assetFormErrors = { name: 'Name ist erforderlich' };
                    this.assetFormMessage = uiText('Bitte die markierten Felder prüfen.');
                    return;
                }

                if (!this.currentAsset.category_id) {
                    this.assetFormErrors = { category_id: uiText('Kategorie ist erforderlich') };
                    this.assetFormMessage = uiText('Bitte die markierten Felder prüfen.');
                    return;
                }

                const payload = {
                    name: this.currentAsset.name,
                    category_id: this.currentAsset.category_id || null,
                    notes: this.currentAsset.notes,
                    specs,
                    device_ids: this.currentAsset.device_ids,
                    acquisition_date: this.currentAsset.acquisition_date,
                    commissioning_date: this.currentAsset.commissioning_date,
                    warranty_end: this.currentAsset.warranty_end,
                    depreciation_months: this.currentAsset.depreciation_months || null,
                    vendor_id: this.currentAsset.vendor_id || null,
                    purchase_order_id: this.currentAsset.purchase_order_id || null,
                    purchase_cost: this.currentAsset.purchase_cost || null,
                    currency: this.currentAsset.currency || null,
                    cost_center: this.currentAsset.cost_center,
                    invoice_number: this.currentAsset.invoice_number,
                    retirement_date: this.currentAsset.retirement_date,
                    retirement_reason: this.currentAsset.retirement_reason,
                    relations: this.currentAsset.relations
                        .filter(relation => relation.related_asset_id)
                        .map((relation) => ({
                            related_asset_id: relation.related_asset_id,
                            relation_type_id: relation.relation_type_id || null
                        }))
                };

                let response;
                if (this.editingAsset) {
                    response = await fetch(`/api/asset-entries/${this.currentAsset.id}`, {
                        method: 'PUT',
                        headers: { 'Content-Type': 'application/json' },
                        body: JSON.stringify(payload)
                    });
                } else {
                    response = await fetch('/api/asset-entries', {
                        method: 'POST',
                        headers: { 'Content-Type': 'application/json' },
                        body: JSON.stringify(payload)
                    });
                }

                if (!response.ok) {
                    const error = await this.readErrorPayload(response, uiText('Asset konnte nicht gespeichert werden'));
                    this.assetFormErrors = error.field_errors || {};
                    this.assetFormMessage = error.error || uiText('Asset konnte nicht gespeichert werden');
                    return;
                }

                await this.loadAssets();
                await this.loadAssetEntryOptions();
                this.assetDirty = false;
                this.assetSaving = false;
                this.closeAssetModal();
                await this.loadActivityFeed();
            } catch (error) {
                console.error(uiText('Error saving asset:'), error);
                this.assetFormMessage = error.message || uiText('Asset konnte nicht gespeichert werden');
            } finally { this.assetSaving = false; }
        },

        async deleteAsset(assetId) {
            if (!confirm(uiText('Möchten Sie dieses Asset wirklich löschen?'))) {
                return;
            }
            const response = await fetch(`/api/asset-entries/${assetId}`, {
                method: 'DELETE'
            });
            if (response.ok) {
                await this.loadAssets();
                await this.loadAssetEntryOptions();
                await this.loadActivityFeed();
            } else {
                const error = await response.json();
                alert(error.error || uiText('Asset konnte nicht gelöscht werden'));
            }
        },

        async openAssetDetail(asset) {
            try {
                const response = await fetch(`/api/asset-entries/${asset.id}`);
                if (!response.ok) {
                    throw new Error(uiText('Asset konnte nicht geladen werden'));
                }
                this.selectedAsset = await response.json();
                this.assetAssignmentHistory = this.selectedAsset.assignment_history || [];
                this.assetAttachments = [];
                this.assetAttachmentError = '';
                if (this.can('attachment.download')) {
                    await this.loadAssetAttachments(asset.id);
                }
                this.assetDetailOpen = true;
            } catch (error) {
                console.error('Error loading asset detail:', error);
                alert(error.message);
            }
        },

        closeAssetDetail() {
            this.assetDetailOpen = false;
            this.closeBinpackingPreview();
            this.selectedAsset = null;
            this.assetAssignmentHistory = [];
            this.assetAttachments = [];
            this.assetAttachmentError = '';
        },

        // Helper Methods
        getCategoryById(categoryId) {
            if (categoryId === null || categoryId === undefined || categoryId === '') return null;
            return this.categories.find(c => String(c.id) === String(categoryId)) || null;
        },

        getCategoryName(categoryId) {
            const category = this.getCategoryById(categoryId);
            return category ? category.name : 'Unknown';
        },

        getAssetCategoryById(categoryId) {
            if (categoryId === null || categoryId === undefined || categoryId === '') return null;
            return this.assetCategories.find(c => String(c.id) === String(categoryId)) || null;
        },

        normalizeFieldConfig(fieldConfig) {
            if (typeof fieldConfig === 'string') {
                return { type: fieldConfig, options: [], unit: '' };
            }
            return {
                type: fieldConfig?.type || 'text',
                options: Array.isArray(fieldConfig?.options) ? fieldConfig.options : [],
                unit: fieldConfig?.unit || ''
            };
        },

        readFieldDefinitions(rawFields, contextLabel) {
            let parsed = rawFields;
            if (typeof rawFields === 'string') {
                try {
                    parsed = JSON.parse(rawFields || '{}');
                } catch (error) {
                    console.error(`Error parsing ${contextLabel} fields:`, error);
                    return null;
                }
            }
            if (!parsed || typeof parsed !== 'object') {
                return null;
            }

            return Object.fromEntries(
                Object.entries(parsed || {}).map(([fieldName, fieldConfig]) => {
                    return [fieldName, this.normalizeFieldConfig(fieldConfig)];
                })
            );
        },

        getCategoryFields(categoryId) {
            const category = this.getCategoryById(categoryId);
            if (!category) return null;
            return this.readFieldDefinitions(category.fields, 'category');
        },

        getAssetCategoryFields(categoryId) {
            const category = this.getAssetCategoryById(categoryId);
            if (!category) return null;
            return this.readFieldDefinitions(category.fields, 'asset category');
        },

        getCategoryFieldEntries(categoryId) {
            const fields = this.getCategoryFields(categoryId) || {};
            return Object.entries(fields).map(([name, config]) => ({
                name,
                ...config,
                unit: this.getFieldUnit(name, config)
            }));
        },

        getAssetCategoryFieldEntries(categoryId) {
            const fields = this.getAssetCategoryFields(categoryId) || {};
            return Object.entries(fields).map(([name, config]) => ({
                name,
                ...config,
                unit: this.getFieldUnit(name, config)
            }));
        },

        extractUnitFromFieldName(fieldName) {
            const match = String(fieldName || '').match(/\(([^)]+)\)\s*$/);
            return match ? match[1].trim() : '';
        },

        getFieldUnit(fieldName, fieldConfig) {
            return (fieldConfig?.unit || '').trim() || this.extractUnitFromFieldName(fieldName);
        },

        splitAssetSpecsByCategory(categoryId, specs) {
            const categoryFields = this.getAssetCategoryFields(categoryId) || {};
            const categoryFieldNames = new Set(Object.keys(categoryFields));
            const categorySpecs = {};
            const extraSpecs = [];
            Object.entries(specs || {}).forEach(([key, value]) => {
                if (categoryFieldNames.has(key)) {
                    categorySpecs[key] = value;
                } else {
                    extraSpecs.push({
                        id: crypto.randomUUID(),
                        name: key,
                        value
                    });
                }
            });
            return { categorySpecs, extraSpecs };
        },

        formatSpecValue(value) {
            if (value === null || value === undefined || value === '') {
                return '-';
            }
            if (typeof value === 'boolean') {
                return value ? uiText('Ja') : uiText('Nein');
            }
            if (Array.isArray(value)) {
                const items = value
                    .map(item => this.formatSpecValue(item))
                    .filter(item => item && item !== '-');
                return items.length ? items.join(', ') : '-';
            }
            if (typeof value === 'object') {
                const items = Object.values(value || {})
                    .map(item => this.formatSpecValue(item))
                    .filter(item => item && item !== '-');
                return items.length ? items.join(', ') : '-';
            }
            return value;
        },

        formatSpecDisplayValue(value, fieldConfig, fieldName) {
            const normalized = this.formatSpecValue(value);
            if (normalized === '-') {
                return normalized;
            }
            const unit = this.getFieldUnit(fieldName, fieldConfig);
            if (!unit || fieldConfig?.type === 'checkbox') {
                return normalized;
            }
            return `${normalized} ${unit}`.trim();
        },

        buildSpecEntries(specs, fieldEntries) {
            const specObject = specs && typeof specs === 'object' ? specs : {};
            const orderedEntries = [];
            const seenKeys = new Set();

            fieldEntries.forEach((field) => {
                if (!Object.prototype.hasOwnProperty.call(specObject, field.name)) {
                    return;
                }
                seenKeys.add(field.name);
                orderedEntries.push({
                    key: field.name,
                    value: this.formatSpecDisplayValue(specObject[field.name], field, field.name)
                });
            });

            Object.entries(specObject).forEach(([key, value]) => {
                if (seenKeys.has(key)) {
                    return;
                }
                orderedEntries.push({
                    key,
                    value: this.formatSpecValue(value)
                });
            });

            return orderedEntries;
        },

        getDeviceSpecEntries(device) {
            if (!device) return [];
            let parsed;
            try {
                parsed = JSON.parse(device.specs || '{}');
            } catch (error) {
                console.error('Error parsing device specs:', error);
                return [];
            }
            return this.buildSpecEntries(parsed, this.getCategoryFieldEntries(device.category_id));
        },

        getAssetSpecEntries(asset) {
            if (!asset) return [];
            const specs = asset.specs && typeof asset.specs === 'object' ? asset.specs : {};
            return this.buildSpecEntries(specs, this.getAssetCategoryFieldEntries(asset.category_id));
        },

        formatDimensionValue(value) {
            if (value === null || value === undefined || value === '') {
                return '-';
            }
            const numeric = Number(value);
            if (Number.isNaN(numeric)) {
                return value;
            }
            return Number.isInteger(numeric) ? `${numeric}` : numeric.toFixed(1);
        },

        formatDimensionTriplet(dimensions) {
            if (!dimensions) {
                return '-';
            }
            return [
                this.formatDimensionValue(dimensions.width),
                this.formatDimensionValue(dimensions.height),
                this.formatDimensionValue(dimensions.depth)
            ].join(' × ');
        },

        binpackingCompletionPercent(preview) {
            const placed = Number(preview?.placed_count) || 0;
            const total = Number(preview?.total_count) || 0;
            if (!total) {
                return 0;
            }
            return Math.max(0, Math.min(100, Math.round((placed / total) * 100)));
        },

        binpackingProjectionStyle(container, projection = 'topdown') {
            const width = Math.max(Number(container?.width) || 1, 1);
            const depth = Math.max(Number(container?.depth) || 1, 1);
            const height = Math.max(Number(container?.height) || 1, 1);
            if (projection === 'elevation') {
                return `aspect-ratio: ${width} / ${height};`;
            }
            return `aspect-ratio: ${width} / ${depth};`;
        },

        binpackingPlacementStyle(placement, container, projection = 'topdown') {
            const containerWidth = Math.max(Number(container?.width) || 1, 1);
            const containerDepth = Math.max(Number(container?.depth) || 1, 1);
            const containerHeight = Math.max(Number(container?.height) || 1, 1);
            const left = (Number(placement?.x) / containerWidth) * 100;
            const width = Math.max((Number(placement?.width) / containerWidth) * 100, 8);
            let top = (Number(placement?.y) / containerDepth) * 100;
            let height = Math.max((Number(placement?.depth) / containerDepth) * 100, 12);
            const color = placement?.color || '#2563eb';
            if (projection === 'elevation') {
                top = 100 - (((Number(placement?.z) + Number(placement?.height)) / containerHeight) * 100);
                height = Math.max((Number(placement?.height) / containerHeight) * 100, 12);
            }
            return [
                `left:${left}%`,
                `top:${top}%`,
                `width:${width}%`,
                `height:${height}%`,
                `--placement-color:${color}`,
                `background:${color}`,
                `border-color:${color}`
            ].join(';');
        },

        binpackingPreviewPlacementStyle(placement, container, projection = 'topdown') {
            const baseStyle = this.binpackingPlacementStyle(placement, container, projection);
            const activeStep = Number(this.binpackingPreviewActiveStep);
            const isActive = !activeStep || Number(placement?.step) === activeStep;
            return [
                baseStyle,
                `opacity:${isActive ? 1 : 0.24}`,
                `transform:scale(${isActive ? 1.01 : 0.985})`,
                `z-index:${isActive ? 4 : 1}`,
                `border-width:${isActive ? 2 : 1}px`,
                `box-shadow:${isActive ? '0 28px 48px -28px rgba(15,23,42,0.82)' : '0 12px 26px -24px rgba(15,23,42,0.45)'}`
            ].join(';');
        },

        binpackingLayerLabel(layer, index) {
            if (!layer) {
                return uiText("Ebene {0}", [index + 1]);
            }
            const start = this.formatDimensionValue(layer.z);
            const height = this.formatDimensionValue(layer.height);
            return uiText("Ebene {0} · Start {1} · Höhe {2}", [index + 1, start, height]);
        },

        binpackingPlacementBadgeStyle(placement) {
            const color = placement?.color || '#2563eb';
            return `background:${color}; border-color:${color};`;
        },

        binpackingStepSummary(step) {
            if (!step) return '';
            return `${step.zone_label} · ${step.dimensions_label}`;
        },

        binpackingStepInstruction(step) {
            if (!step) return '';
            return uiText("{0} auf Ebene {1} {2} platzieren. Maße: {3}.", [step.asset_name, step.layer_index, step.zone_label, step.dimensions_label]);
        },

        async readErrorPayload(response, fallbackMessage) {
            const contentType = response.headers.get('content-type') || '';
            if (contentType.includes('application/json')) {
                try {
                    return await response.json();
                } catch (error) {
                    return { error: fallbackMessage };
                }
            }
            const text = await response.text();
            if (text && /<!doctype|<html/i.test(text)) {
                return { error: fallbackMessage };
            }
            return { error: text || fallbackMessage };
        },

        clearAssetFormState() {
            this.assetFormErrors = {};
            this.assetFormMessage = '';
        },

        clearDeviceFormState() {
            this.deviceFormErrors = {};
            this.deviceFormMessage = '';
        },

        getDeviceFieldError(fieldName) {
            return this.deviceFormErrors[fieldName] || '';
        },

        getDeviceSpecFieldError(fieldName) {
            return this.deviceFormErrors[`specs.${fieldName}`] || '';
        },

        getAssetFieldError(fieldName) {
            return this.assetFormErrors[fieldName] || '';
        },

        getAssetSpecFieldError(fieldName) {
            return this.assetFormErrors[`specs.${fieldName}`] || '';
        },

        getDevicesForCategory(categoryId) {
            return this.allDevices.filter(device => device.category_id === categoryId);
        },

		getCategoryColor(categoryName) {
			// 1. Definiere die festen Farben für bekannte Kategorien
			const predefinedColors = {
				'CPU': 'bg-blue-100 text-blue-800',
				'GPU': 'bg-purple-100 text-purple-800',
				'RAM': 'bg-green-100 text-green-800',
				'Storage': 'bg-yellow-100 text-yellow-800'
			};

			// 2. Wenn die Kategorie bekannt ist, gib ihre Farbe zurück
			if (predefinedColors[categoryName]) {
				return predefinedColors[categoryName];
			}

			// 3. Liste von FARBEN FÜR UNBEKANNTE KATEGORIEN (OHNE GRAU!)
			const dynamicColors = [
			  'bg-blue-100 text-blue-800',
			  'bg-red-100 text-red-800',
			  'bg-green-100 text-green-800',
			  'bg-yellow-100 text-yellow-800',
			  'bg-purple-100 text-purple-800',
			  'bg-pink-100 text-pink-800',
			  'bg-rose-100 text-rose-800',
			  'bg-fuchsia-100 text-fuchsia-800',
			  'bg-indigo-100 text-indigo-800',
			  'bg-cyan-100 text-cyan-800',
			  'bg-sky-100 text-sky-800',
			  'bg-amber-100 text-amber-800',
			  'bg-orange-100 text-orange-800',
			  'bg-lime-100 text-lime-800',
			  'bg-emerald-100 text-emerald-800',
			  'bg-teal-100 text-teal-800',
			  'bg-violet-100 text-violet-800',
			];

			// 4. Erzeuge einen stabilen Farbindex basierend auf dem Kategorienamen
			//    (sodass dieselbe Kategorie immer dieselbe Farbe bekommt)
			const hash = Array.from(categoryName).reduce(
				(hash, char) => (hash << 5) - hash + char.charCodeAt(0),
				0
			);
			const colorIndex = Math.abs(hash) % dynamicColors.length;

			// 5. Gib die zufällige Farbe zurück (NIEMALS GRAU!)
			return dynamicColors[colorIndex];
		}		
		
    }));
});
