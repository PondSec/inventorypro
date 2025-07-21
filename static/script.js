document.addEventListener('alpine:init', () => {
    Alpine.data('app', () => ({
        // State
        categories: [],
        devices: [],
        filteredDevices: [],
        activeCategory: null,
        searchQuery: '',
        sortDropdownOpen: false,
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
            await this.loadDevices();
            this.$watch('searchQuery', () => this.searchDevices());
            feather.replace();
        },
		
        // Data Loading
        async loadCategories() {
            const response = await fetch('/api/categories');
            this.categories = await response.json();
        },

        async loadDevices(categoryId = null) {
            this.activeCategory = categoryId;
            const url = categoryId 
                ? `/api/devices?category_id=${categoryId}`
                : '/api/devices';
            
            const response = await fetch(url);
            this.devices = await response.json();
            this.filteredDevices = this.devices;
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

