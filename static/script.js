document.addEventListener('alpine:init', () => {
    Alpine.data('app', () => ({
        // State
        categories: [],
        locations: [],
        devices: [],
        filteredDevices: [],
        allDevices: [],
        assets: [],
        activeCategory: null,
        searchQuery: '',
        sortDropdownOpen: false,
        featureFlags: {
            pro_enabled: false,
            pro_features: [],
            free_features: []
        },
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
        deviceTags: [],
        deviceNotes: [],
        maintenanceTasks: [],
        newTag: '',
        newNote: '',
        newMaintenance: {
            title: '',
            due_date: ''
        },
        currentSort: { field: null, direction: null },
        
        // Modals
        isCategoryModalOpen: false,
        isDeviceModalOpen: false,
        isAssetModalOpen: false,
        editingCategory: null,
        editingDevice: null,
        editingAsset: null,
        categoryMenuOpen: null,  // Geändert von openCategoryId zu categoryMenuOpen für Konsistenz
        openDeviceId: null,
        
        // Current Items
        currentCategory: {
            id: null,
            name: '',
            icon: 'cpu',
            fields: []
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
            notes: '',
            specs: [],
            device_ids: []
        },

        // Initialization
        async init() {
            await this.loadCategories();
            await this.loadLocations();
            await this.loadAllDevices();
            await this.loadDevices();
            await this.loadAssets();
            await this.loadFeatureFlags();
            await this.loadMaintenanceSummary();
            await this.loadActivityFeed();
            this.$watch('searchQuery', () => this.searchDevices());
            feather.replace();
            this.startLiveRefresh();
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

        startLiveRefresh() {
            setInterval(async () => {
                await this.loadActivityFeed();
                await this.loadMaintenanceSummary();
            }, 15000);
        },
		
        // Data Loading
        async loadCategories() {
            const response = await fetch('/api/categories');
            if (response.ok) {
                this.categories = await response.json();
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
            const url = categoryId 
                ? `/api/devices?category_id=${categoryId}`
                : '/api/devices';
            
            const response = await fetch(url);
            if (response.ok) {
                this.devices = await response.json();
                this.filteredDevices = this.devices;
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

        async loadAssets() {
            const response = await fetch('/api/assets');
            if (response.ok) {
                this.assets = await response.json();
            }
        },

        // Search and Sort
        searchDevices() {
            if (!this.searchQuery) {
                this.filteredDevices = [...this.devices];
            } else {
                const query = this.searchQuery.toLowerCase();
                this.filteredDevices = this.devices.filter(device => 
                    device.name.toLowerCase().includes(query) ||
                    (device.serial_number && device.serial_number.toLowerCase().includes(query)) ||
                    JSON.stringify(device.specs).toLowerCase().includes(query)
                );
            }
            
            // Apply current sort if one is active
            if (this.currentSort.field) {
                this.sortDevices(this.currentSort.field, this.currentSort.direction);
            }
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
                fields: []
            };
            this.isCategoryModalOpen = true;
            this.categoryMenuOpen = null; // Menü schließen beim Öffnen des Modals
        },

		editCategoryModal(category) {  // <-- Parameter korrekt entgegennehmen
            const fieldsObject = JSON.parse(category.fields || '{}');
			this.editingCategory = true;
			this.currentCategory = {
				id: category.id,
				name: category.name,
				icon: category.icon,
				fields: Object.entries(fieldsObject).map(([fieldName, fieldConfig]) => {
                    if (typeof fieldConfig === 'string') {
                        return {
                            id: crypto.randomUUID(),
                            name: fieldName,
                            type: fieldConfig,
                            options: [],
                            optionsText: ''
                        };
                    }

                    const options = Array.isArray(fieldConfig?.options) ? fieldConfig.options : [];
                    return {
                        id: crypto.randomUUID(),
                        name: fieldName,
                        type: fieldConfig?.type || 'text',
                        options,
                        optionsText: options.join(', ')
                    };
                })
			};
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
                optionsText: ''
            });
        },

        removeCategoryField(fieldId) {
            this.currentCategory.fields = this.currentCategory.fields.filter(field => field.id !== fieldId);
        },

        async saveCategory() {
            try {
                const fields = {};
                for (const field of this.currentCategory.fields) {
                    const trimmedName = field.name.trim();
                    if (!trimmedName) continue;
                    if (field.type === 'select') {
                        const options = (field.optionsText || '')
                            .split(',')
                            .map(option => option.trim())
                            .filter(Boolean);
                        fields[trimmedName] = {
                            type: field.type,
                            options
                        };
                    } else {
                        fields[trimmedName] = field.type;
                    }
                }

                const categoryData = {
                    name: this.currentCategory.name,
                    icon: this.currentCategory.icon,
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

        toggleCategoryMenu(categoryId) {
            this.categoryMenuOpen = this.categoryMenuOpen === categoryId ? null : categoryId;
            // Schließe das Geräte-Menü, wenn ein Kategorie-Menü geöffnet wird
            if (this.categoryMenuOpen !== null) {
                this.openDeviceId = null;
            }
        },

        // Device Methods
        openAddDeviceModal() {
            this.editingDevice = false;
            this.currentDevice = {
                id: null,
                name: '',
                category_id: this.activeCategory,
                serial_number: '',
                location_id: '',
                specs: {},
                extraSpecs: []
            };
            this.isDeviceModalOpen = true;
        },

        openEditDeviceModal(device) {
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

        async saveDevice() {
            try {
                const specs = { ...this.currentDevice.specs };
                this.currentDevice.extraSpecs.forEach((spec) => {
                    const trimmedName = spec.name.trim();
                    if (!trimmedName) return;
                    specs[trimmedName] = spec.value;
                });

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
                    const error = await response.json();
                    throw new Error(error.error || 'Failed to save device');
                }

                await this.loadDevices(this.activeCategory);
                await this.loadAllDevices();
                this.closeDeviceModal();
                await this.loadActivityFeed();
            } catch (error) {
                console.error('Error saving device:', error);
                alert('Error saving device: ' + error.message);
            }
        },

        async deleteDevice(deviceId) {
            if (confirm('Are you sure you want to delete this device?')) {
                const response = await fetch(`/api/devices/${deviceId}`, {
                    method: 'DELETE'
                });
                if (response.ok) {
                    await this.loadDevices(this.activeCategory);
                    await this.loadAllDevices();
                    await this.loadActivityFeed();
                } else {
                    const error = await response.json();
                    alert('Error deleting device: ' + (error.error || 'Unknown error'));
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

        formatActivity(item) {
            const name = item.details?.name || item.details?.tag || '';
            const label = `${item.action} ${item.entity_type}`.replace('_', ' ');
            return `${label}${name ? ` • ${name}` : ''}`;
        },

        // Asset Methods
        async openAddAssetModal() {
            this.editingAsset = false;
            this.currentAsset = {
                id: null,
                name: '',
                notes: '',
                specs: [],
                device_ids: []
            };
            if (this.allDevices.length === 0) {
                await this.loadAllDevices();
            }
            this.isAssetModalOpen = true;
        },

        async openEditAssetModal(asset) {
            try {
                const response = await fetch(`/api/assets/${asset.id}`);
                if (!response.ok) {
                    throw new Error('Asset konnte nicht geladen werden');
                }
                const data = await response.json();
                this.editingAsset = true;
                this.currentAsset = {
                    id: data.id,
                    name: data.name,
                    notes: data.notes || '',
                    specs: Object.entries(data.specs || {}).map(([key, value]) => ({
                        id: crypto.randomUUID(),
                        name: key,
                        value
                    })),
                    device_ids: (data.devices || []).map(device => device.id)
                };
                this.isAssetModalOpen = true;
            } catch (error) {
                console.error('Error loading asset:', error);
                alert(error.message);
            }
        },

        closeAssetModal() {
            this.isAssetModalOpen = false;
        },

        addAssetSpec() {
            this.currentAsset.specs.push({
                id: crypto.randomUUID(),
                name: '',
                value: ''
            });
        },

        removeAssetSpec(specId) {
            this.currentAsset.specs = this.currentAsset.specs.filter(spec => spec.id !== specId);
        },

        async saveAsset() {
            try {
                const specs = {};
                this.currentAsset.specs.forEach((spec) => {
                    const trimmedName = spec.name.trim();
                    if (!trimmedName) return;
                    specs[trimmedName] = spec.value;
                });

                const payload = {
                    name: this.currentAsset.name,
                    notes: this.currentAsset.notes,
                    specs,
                    device_ids: this.currentAsset.device_ids
                };

                let response;
                if (this.editingAsset) {
                    response = await fetch(`/api/assets/${this.currentAsset.id}`, {
                        method: 'PUT',
                        headers: { 'Content-Type': 'application/json' },
                        body: JSON.stringify(payload)
                    });
                } else {
                    response = await fetch('/api/assets', {
                        method: 'POST',
                        headers: { 'Content-Type': 'application/json' },
                        body: JSON.stringify(payload)
                    });
                }

                if (!response.ok) {
                    const error = await response.json();
                    throw new Error(error.error || 'Asset konnte nicht gespeichert werden');
                }

                await this.loadAssets();
                this.closeAssetModal();
                await this.loadActivityFeed();
            } catch (error) {
                console.error('Error saving asset:', error);
                alert('Error saving asset: ' + error.message);
            }
        },

        async deleteAsset(assetId) {
            if (!confirm('Möchten Sie dieses Asset wirklich löschen?')) {
                return;
            }
            const response = await fetch(`/api/assets/${assetId}`, {
                method: 'DELETE'
            });
            if (response.ok) {
                await this.loadAssets();
                await this.loadActivityFeed();
            } else {
                const error = await response.json();
                alert(error.error || 'Asset konnte nicht gelöscht werden');
            }
        },

        async openAssetDetail(asset) {
            try {
                const response = await fetch(`/api/assets/${asset.id}`);
                if (!response.ok) {
                    throw new Error('Asset konnte nicht geladen werden');
                }
                this.selectedAsset = await response.json();
                this.assetDetailOpen = true;
            } catch (error) {
                console.error('Error loading asset detail:', error);
                alert(error.message);
            }
        },

        closeAssetDetail() {
            this.assetDetailOpen = false;
            this.selectedAsset = null;
        },

        // Helper Methods
        getCategoryById(categoryId) {
            return this.categories.find(c => c.id === categoryId) || null;
        },

        getCategoryName(categoryId) {
            const category = this.getCategoryById(categoryId);
            return category ? category.name : 'Unknown';
        },

        getCategoryFields(categoryId) {
            const category = this.getCategoryById(categoryId);
            if (!category) return null;
            let parsed;
            try {
                parsed = JSON.parse(category.fields || '{}');
            } catch (error) {
                console.error('Error parsing category fields:', error);
                return null;
            }

            return Object.fromEntries(
                Object.entries(parsed).map(([fieldName, fieldConfig]) => {
                    if (typeof fieldConfig === 'string') {
                        return [fieldName, { type: fieldConfig, options: [] }];
                    }
                    return [
                        fieldName,
                        {
                            type: fieldConfig?.type || 'text',
                            options: Array.isArray(fieldConfig?.options) ? fieldConfig.options : []
                        }
                    ];
                })
            );
        },

        formatSpecValue(value) {
            if (value === null || value === undefined || value === '') {
                return '-';
            }
            if (typeof value === 'boolean') {
                return value ? 'Ja' : 'Nein';
            }
            return value;
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
            return Object.entries(parsed).map(([key, value]) => ({
                key,
                value: this.formatSpecValue(value)
            }));
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
