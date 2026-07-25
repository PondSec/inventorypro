document.addEventListener('alpine:init', () => {
    Alpine.data('app', () => ({
        // State
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
                overview: 'Inventar',
                devices: this.activeCategory
                    ? this.getCategoryName(this.activeCategory)
                    : (this.locationFilter ? `Geräte in ${this.locationFilterName()}` : 'Geräte'),
                assets: this.selectedAssetCategory ? this.selectedAssetCategory.name : 'Assets',
                taxonomy: 'Struktur'
            };
            return titles[this.workspaceView] || 'Inventar';
        },

        workspaceDescription() {
            const descriptions = {
                overview: 'Überblick, nächste Aktionen und aktuelle Bewegung.',
                devices: 'Geräte suchen, filtern und präzise pflegen.',
                assets: 'Asset-Einträge, Komponenten, Zuweisungen und Lebenszyklus.',
                taxonomy: 'Kategorien und Asset-Profile verwalten.'
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
                console.error('Fehler beim Abrufen des 2FA-Status:', error);
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
                    const confirmed = confirm('2FA ist bereits aktiviert. Möchten Sie es deaktivieren?');
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
                            alert('Fehler beim Deaktivieren von 2FA.');
                        }
                    }
                    return;
                }

                this.otpSecret = data.secret;
                this.otpQrCode = data.qr_code;
                this.otpModalOpen = true;
            } catch (error) {
                console.error('Fehler:', error);
                alert('Ein Fehler ist aufgetreten');
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
            if (!confirm('Are you sure you want to delete this category and all its devices?')) {
                return false;
            }
            const response = await fetch(`/api/categories/${categoryId}`, {
                method: 'DELETE'
            });
            if (response.ok) {
                await this.loadCategories();
                if (this.activeCategory === categoryId) {
                    await this.loadDevices();
                }
                this.categoryMenuOpen = null; // Menü schließen nach Löschen
                await this.loadActivityFeed();
                return true;
            }
            const error = await response.json();
            alert('Error deleting category: ' + (error.error || 'Unknown error'));
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
                        throw new Error(messages || error.error || 'Asset-Kategorie konnte nicht gespeichert werden');
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
            if (!confirm('Möchten Sie diese Asset-Kategorie wirklich löschen? Zugeordnete Assets bleiben erhalten.')) {
                return false;
            }
            const response = await fetch(`/api/asset-categories/${categoryId}`, {
                method: 'DELETE'
            });
            if (response.ok) {
                await this.loadAssetCategories();
                await this.loadAssets();
                this.assetCategoryMenuOpen = null;
                await this.loadActivityFeed();
                return true;
            }
            const error = await response.json();
            alert('Error deleting asset category: ' + (error.error || 'Unknown error'));
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
                    this.deviceFormMessage = 'Bitte die markierten Felder prüfen.';
                    return;
                }

                if (!this.currentDevice.category_id) {
                    this.deviceFormErrors = { category_id: 'Kategorie ist erforderlich' };
                    this.deviceFormMessage = 'Bitte die markierten Felder prüfen.';
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
                    const error = await this.readErrorPayload(response, 'Gerät konnte nicht gespeichert werden');
                    this.deviceFormErrors = error.field_errors || {};
                    this.deviceFormMessage = error.error || 'Gerät konnte nicht gespeichert werden';
                    return;
                }

                await this.loadDevices(this.activeCategory);
                await this.loadAllDevices();
                this.closeDeviceModal();
                await this.loadActivityFeed();
            } catch (error) {
                console.error('Error saving device:', error);
                this.deviceFormMessage = error.message || 'Gerät konnte nicht gespeichert werden';
            }
        },

        async deleteDevice(deviceId) {
            if (confirm('Möchten Sie dieses Gerät wirklich löschen?')) {
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
                    alert(error.error || 'Gerät konnte nicht gelöscht werden');
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
                    alert(error.error || 'Tag konnte nicht gespeichert werden');
                }
            } catch (error) {
                console.error('Error adding tag:', error);
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
                console.error('Error removing tag:', error);
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
                    alert(error.error || 'Notiz konnte nicht gespeichert werden');
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
                    alert(error.error || 'Wartung konnte nicht gespeichert werden');
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
                this.maintenanceAttachmentErrors[taskId] = error.error || 'Upload fehlgeschlagen';
            }
            event.target.value = '';
        },

        async deleteMaintenanceAttachment(taskId, attachmentId) {
            if (!confirm('Anhang wirklich löschen?')) return;
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
                assigned: 'Zugewiesen',
                checked_out: 'Ausgegeben',
                checked_in: 'Eingecheckt',
                transferred: 'Übertragen',
                unassigned: 'Nicht zugewiesen'
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
                alert(error.error || 'Zuweisung konnte nicht gespeichert werden');
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
                this.assetAttachmentError = error.error || 'Upload fehlgeschlagen';
            }
            event.target.value = '';
        },

        async deleteAssetAttachment(attachmentId) {
            if (!confirm('Anhang wirklich löschen?')) return;
            const response = await fetch(`/attachments/${attachmentId}/delete`, { method: 'POST' });
            if (response.ok && this.selectedAsset) {
                await this.loadAssetAttachments(this.selectedAsset.id);
            }
        },

        // Asset Entry Methods
        async openAddAssetModal() {
            if (this.assetCategories.length === 0) {
                alert('Bitte zuerst eine Asset-Kategorie anlegen.');
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
            this.isAssetModalOpen = true;
        },

        async openEditAssetModal(asset) {
            try {
                this.clearAssetFormState();
                const response = await fetch(`/api/asset-entries/${asset.id}`);
                if (!response.ok) {
                    throw new Error('Asset konnte nicht geladen werden');
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
                this.isAssetModalOpen = true;
            } catch (error) {
                console.error('Error loading asset:', error);
                alert(error.message);
            }
        },

        closeAssetModal() {
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
                    this.assetFormMessage = 'Bitte die markierten Felder prüfen.';
                    return;
                }

                if (!this.currentAsset.category_id) {
                    this.assetFormErrors = { category_id: 'Kategorie ist erforderlich' };
                    this.assetFormMessage = 'Bitte die markierten Felder prüfen.';
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
                    const error = await this.readErrorPayload(response, 'Asset konnte nicht gespeichert werden');
                    this.assetFormErrors = error.field_errors || {};
                    this.assetFormMessage = error.error || 'Asset konnte nicht gespeichert werden';
                    return;
                }

                await this.loadAssets();
                await this.loadAssetEntryOptions();
                this.closeAssetModal();
                await this.loadActivityFeed();
            } catch (error) {
                console.error('Error saving asset:', error);
                this.assetFormMessage = error.message || 'Asset konnte nicht gespeichert werden';
            }
        },

        async deleteAsset(assetId) {
            if (!confirm('Möchten Sie dieses Asset wirklich löschen?')) {
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
                alert(error.error || 'Asset konnte nicht gelöscht werden');
            }
        },

        async openAssetDetail(asset) {
            try {
                const response = await fetch(`/api/asset-entries/${asset.id}`);
                if (!response.ok) {
                    throw new Error('Asset konnte nicht geladen werden');
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
            const yaw = (Number(this.binpackingRotationZ) || -38) * (Math.PI / 180);
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
            const yaw = (Number(this.binpackingRotationZ) || -38) * (Math.PI / 180);
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
                return value ? 'Ja' : 'Nein';
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
                return `Ebene ${index + 1}`;
            }
            const start = this.formatDimensionValue(layer.z);
            const height = this.formatDimensionValue(layer.height);
            return `Ebene ${index + 1} · Start ${start} · Höhe ${height}`;
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
            return `${step.asset_name} auf Ebene ${step.layer_index} ${step.zone_label} platzieren. Maße: ${step.dimensions_label}.`;
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
