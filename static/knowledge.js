document.addEventListener('alpine:init', () => {
    Alpine.data('knowledgeApp', () => ({
        categories: [],
        entries: [],
        selectedEntry: null,
        selectedCategoryId: '',
        searchQuery: '',
        listPage: 1, listPages: 1, listTotal: 0, listLoading: false, listError: '',
        listRequestId: 0,
        entryModalOpen: false,
        categoryModalOpen: false,
        entryError: '',
        categoryError: '',
        entryForm: {
            id: null,
            title: '',
            summary: '',
            content: '',
            category_id: '',
            related_ticket_id: ''
        },
        categoryForm: {
            id: null,
            name: '',
            description: ''
        },
        userPermissions: window.inventoryPermissions || [],
        isSuperuser: window.inventoryIsSuperuser || false,

        async init() {
            await this.loadCategories();
            await this.loadEntries();
            const params = new URLSearchParams(window.location.search);
            const entryId = params.get('entry_id');
            const ticketId = params.get('ticket_id');
            if (ticketId) {
                this.entryForm.related_ticket_id = ticketId;
            }
            if (entryId) {
                await this.selectEntry({ id: entryId });
            }
            this.$nextTick(() => feather.replace());
        },

        can(permissionKey) {
            return this.isSuperuser || this.userPermissions.includes(permissionKey);
        },

        async loadCategories() {
            const response = await fetch('/api/knowledge/categories');
            if (response.ok) {
                this.categories = await response.json();
            }
        },

        async loadEntries(page = 1) {
            const requestId = ++this.listRequestId;
            this.listLoading = true;
            this.listError = '';
            const params = new URLSearchParams({paginated: '1', page: String(page)});
            if (this.selectedCategoryId) params.set('category_id', this.selectedCategoryId);
            if (this.searchQuery) params.set('search', this.searchQuery);
            try {
                const response = await fetch(`/api/knowledge/entries?${params.toString()}`);
                if (!response.ok) throw new Error('Wissenseinträge konnten nicht geladen werden.');
                const data = await response.json();
                if (requestId !== this.listRequestId) return;
                this.entries = data.items;
                this.listPage = data.page;
                this.listPages = data.pages;
                this.listTotal = data.total;
            } catch (error) {
                if (requestId === this.listRequestId) this.listError = error.message || 'Verbindung fehlgeschlagen.';
            } finally {
                if (requestId === this.listRequestId) this.listLoading = false;
            }
        },

        async selectEntry(entry) {
            const response = await fetch(`/api/knowledge/entries/${entry.id}`);
            if (response.ok) {
                this.selectedEntry = await response.json();
            }
            this.$nextTick(() => feather.replace());
        },

        clearSelectedEntry() {
            this.selectedEntry = null;
        },

        setCategoryFilter(categoryId) {
            this.selectedCategoryId = categoryId;
            this.loadEntries();
        },

        openEntryModal(entry = null) {
            this.entryError = '';
            if (entry) {
                this.entryForm = {
                    id: entry.id,
                    title: entry.title,
                    summary: entry.summary || '',
                    content: entry.content || '',
                    category_id: entry.category_id || '',
                    related_ticket_id: entry.related_ticket_id || ''
                };
            } else {
                this.entryForm = {
                    id: null,
                    title: '',
                    summary: '',
                    content: '',
                    category_id: this.selectedCategoryId || '',
                    related_ticket_id: this.entryForm.related_ticket_id || ''
                };
            }
            this.entryModalOpen = true;
        },

        closeEntryModal() {
            this.entryModalOpen = false;
        },

        async saveEntry() {
            this.entryError = '';
            const payload = {
                title: this.entryForm.title,
                summary: this.entryForm.summary,
                content: this.entryForm.content,
                category_id: this.entryForm.category_id || null,
                related_ticket_id: this.entryForm.related_ticket_id || null
            };
            const url = this.entryForm.id ? `/api/knowledge/entries/${this.entryForm.id}` : '/api/knowledge/entries';
            const method = this.entryForm.id ? 'PUT' : 'POST';
            const response = await fetch(url, {
                method,
                headers: { 'Content-Type': 'application/json' },
                body: JSON.stringify(payload)
            });
            if (response.ok) {
                await this.loadEntries();
                if (this.entryForm.id) {
                    await this.selectEntry({ id: this.entryForm.id });
                }
                this.entryModalOpen = false;
            } else {
                const data = await response.json();
                this.entryError = data.error || 'Ein Fehler ist aufgetreten.';
            }
        },

        async deleteEntry(entry) {
            if (!entry || !confirm('Diesen Wissenseintrag wirklich löschen?')) return;
            const response = await fetch(`/api/knowledge/entries/${entry.id}`, { method: 'DELETE' });
            if (response.ok) {
                if (this.selectedEntry && this.selectedEntry.id === entry.id) {
                    this.selectedEntry = null;
                }
                await this.loadEntries();
            }
        },

        openCategoryModal(category = null) {
            this.categoryError = '';
            if (category) {
                this.categoryForm = {
                    id: category.id,
                    name: category.name,
                    description: category.description || ''
                };
            } else {
                this.categoryForm = {
                    id: null,
                    name: '',
                    description: ''
                };
            }
            this.categoryModalOpen = true;
        },

        closeCategoryModal() {
            this.categoryModalOpen = false;
        },

        async saveCategory() {
            this.categoryError = '';
            const payload = {
                name: this.categoryForm.name,
                description: this.categoryForm.description
            };
            const url = this.categoryForm.id ? `/api/knowledge/categories/${this.categoryForm.id}` : '/api/knowledge/categories';
            const method = this.categoryForm.id ? 'PUT' : 'POST';
            const response = await fetch(url, {
                method,
                headers: { 'Content-Type': 'application/json' },
                body: JSON.stringify(payload)
            });
            if (response.ok) {
                await this.loadCategories();
                await this.loadEntries();
                this.categoryModalOpen = false;
            } else {
                const data = await response.json();
                this.categoryError = data.error || 'Ein Fehler ist aufgetreten.';
            }
        }
    }));
});
