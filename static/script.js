document.addEventListener('alpine:init', () => {
    Alpine.data('app', () => ({
        // State
        categories: [],
        locations: [],
        devices: [],
        filteredDevices: [],
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
		
		showSortMenu: false,
		currentSort: null,
		sortOptions: [
			{ value: 'clock_asc', label: 'Clock ▲', field: 'clock', order: 'asc' },
			{ value: 'clock_desc', label: 'Clock ▼', field: 'clock', order: 'desc' },
			{ value: 'name_asc', label: 'Name A-Z', field: 'name', order: 'asc' },
			{ value: 'name_desc', label: 'Name Z-A', field: 'name', order: 'desc' },
			{ value: 'none', label: 'No sorting' }
		],
        
        // Modals
        isCategoryModalOpen: false,
        isDeviceModalOpen: false,
        editingCategory: null,
        editingDevice: null,
        categoryMenuOpen: null,  // Geändert von openCategoryId zu categoryMenuOpen für Konsistenz
        openDeviceId: null,
        
        // Current Items
        currentCategory: {
            id: null,
            name: '',
            icon: 'cpu',
            fields: '{}'
        },
        currentDevice: {
            id: null,
            name: '',
            category_id: null,
            serial_number: '',
            specs: {}
        },

        // Initialization
        async init() {
            await this.loadCategories();
            await this.loadLocations();
            await this.loadDevices();
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

        async loadActivityFeed() {
            try {
                const response = await fetch('/api/activity?limit=6');
                if (response.ok) {
                    this.activityFeed = await response.json();
                }
            } catch (error) {
                console.error('Error loading activity feed:', error);
            }
        },

        async loadOverview() {
            try {
                const response = await fetch('/api/dashboard/overview');
                if (response.ok) {
                    this.overview = await response.json();
                    this.updateLiveChart();
                }
            } catch (error) {
                console.error('Error loading dashboard overview:', error);
            }
        },

        startLiveRefresh() {
            setInterval(async () => {
                await this.loadActivityFeed();
                await this.loadMaintenanceSummary();
                await this.loadOverview();
            }, 15000);
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
                const response = await fetch('/api/activity?limit=6');
                if (response.ok) {
                    this.activityFeed = await response.json();
                }
            } catch (error) {
                console.error('Error loading activity feed:', error);
            }
        },
		
        // Data Loading
        async loadCategories() {
            const response = await fetch('/api/categories');
            this.categories = await response.json();
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
            this.devices = await response.json();
            this.filteredDevices = this.devices;
            if (this.selectedDevice) {
                const updated = this.devices.find(device => device.id === this.selectedDevice.id);
                if (updated) {
                    this.selectedDevice = updated;
                }
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
                fields: '{}'
            };
            this.isCategoryModalOpen = true;
            this.categoryMenuOpen = null; // Menü schließen beim Öffnen des Modals
        },

		editCategoryModal(category) {  // <-- Parameter korrekt entgegennehmen
			this.editingCategory = true;
			this.currentCategory = {
				id: category.id,
				name: category.name,
				icon: category.icon,
				fields: JSON.stringify(JSON.parse(category.fields), null, 2)
			};
			this.isCategoryModalOpen = true;
			this.categoryMenuOpen = null; // Menü schließen beim Öffnen des Modals
		},

        closeCategoryModal() {
            this.isCategoryModalOpen = false;
        },

        async saveCategory() {
            try {
                const categoryData = {
                    name: this.currentCategory.name,
                    icon: this.currentCategory.icon,
                    fields: JSON.parse(this.currentCategory.fields)
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

                if (response.ok) {
                    await this.loadCategories();
                    this.closeCategoryModal();
                    await this.loadActivityFeed();
                } else {
                    const error = await response.json();
                    throw new Error(error.error || 'Failed to save category');
                }
            } catch (error) {
                console.error('Error saving category:', error);
                alert('Error saving category: ' + error.message);
            }
        },

        async deleteCategory(categoryId) {
            if (confirm('Are you sure you want to delete this category and all its devices?')) {
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
                } else {
                    const error = await response.json();
                    alert('Error deleting category: ' + (error.error || 'Unknown error'));
                }
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
                specs: {}
            };
            this.isDeviceModalOpen = true;
        },

        openEditDeviceModal(device) {
            this.editingDevice = true;
            this.currentDevice = {
                id: device.id,
                name: device.name,
                category_id: device.category_id,
                serial_number: device.serial_number,
                location_id: device.location_id || '',
                specs: JSON.parse(device.specs || '{}')
            };
            this.isDeviceModalOpen = true;
        },

        closeDeviceModal() {
            this.isDeviceModalOpen = false;
        },

        async saveDevice() {
            try {
                const deviceData = {
                    name: this.currentDevice.name,
                    category_id: this.currentDevice.category_id || this.activeCategory,
                    serial_number: this.currentDevice.serial_number,
                    location_id: this.currentDevice.location_id || null,
                    specs: this.currentDevice.specs
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

                if (response.ok) {
                    await this.loadDevices(this.activeCategory);
                    this.closeDeviceModal();
                    await this.loadActivityFeed();
                } else {
                    const error = await response.json();
                    throw new Error(error.error || 'Failed to save device');
                }
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

            if (this.featureFlags.pro_enabled) {
                try {
                    const maintenanceRes = await fetch(`/api/maintenance?device_id=${deviceId}`);
                    if (maintenanceRes.ok) {
                        this.maintenanceTasks = await maintenanceRes.json();
                    }
                } catch (error) {
                    console.error('Error loading maintenance tasks:', error);
                }
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
            if (!this.featureFlags.pro_enabled || !this.selectedDevice) return;
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
            if (!this.featureFlags.pro_enabled) return;
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

        // Helper Methods
        getCategoryName(categoryId) {
            const category = this.categories.find(c => c.id === categoryId);
            return category ? category.name : 'Unknown';
        },

        getCategoryFields(categoryId) {
            const category = this.categories.find(c => c.id === categoryId);
            return category ? JSON.parse(category.fields || '{}') : null;
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
