document.addEventListener('alpine:init', () => {
    Alpine.data('serviceDesk', () => ({
        tickets: [],
        categories: [],
        savedViews: [],
        queueCounts: {},
        selectedTicket: null,
        selectedIds: [],
        attachments: [],
        assetOptions: [],
        assetSelection: [],
        reviewableChanges: [],
        userPermissions: window.inventoryPermissions || [],
        isSuperuser: window.inventoryIsSuperuser || false,
        currentUsername: window.inventoryUsername || '',
        loading: true,
        detailLoading: false,
        assetLoading: false,
        reviewChangesLoading: false,
        saving: false,
        deletingTickets: false,
        error: '',
        createError: '',
        queuesCollapsed: false,
        mobileQueuesOpen: false,
        metadataCollapsed: false,
        filterOpen: false,
        createOpen: false,
        assetPickerOpen: false,
        saveViewOpen: false,
        showShortcuts: false,
        detailTab: 'conversation',
        assetPickerTarget: 'create',
        assetSearch: '',
        changeSearch: '',
        iconRefreshTimer: null,
        keyboardIndex: -1,
        newComment: '',
        internalComment: false,
        toasts: [],
        toastSequence: 0,
        focusReturnStack: [],
        activeQueue: 'my-work',
        sort: { key: 'updated_at', direction: 'desc' },
        filters: { search: '', status: '', priority: '', category_id: '', assignee: '', mine: false },
        draftFilters: { search: '', status: '', priority: '', category_id: '', assignee: '', mine: false },
        pagination: { page: 1, per_page: 25, total: 0, pages: 1 },
        newView: { name: '', is_favorite: false, is_default: false },
        newTicket: {
            title: '',
            description: '',
            type: 'incident',
            category_id: '',
            priority: 'normal',
            assignee: '',
            due_date: '',
            asset_ids: [],
            change_ticket_id: ''
        },
        bulkDialog: { open: false, field: '', value: '', title: '' },
        queues: [
            { key: 'my-work', label: 'Meine Arbeit', icon: 'briefcase' },
            { key: 'unassigned', label: 'Nicht zugewiesen', icon: 'user-x' },
            { key: 'mine', label: 'Meine offenen Tickets', icon: 'user-check' },
            { key: 'all-open', label: 'Alle offenen Tickets', icon: 'inbox' },
            { key: 'waiting', label: 'Wartend', icon: 'pause-circle' },
            { key: 'sla-risk', label: 'SLA gefährdet', icon: 'clock' },
            { key: 'overdue', label: 'Überfällig', icon: 'alert-triangle' },
            { key: 'escalated', label: 'Eskaliert', icon: 'arrow-up-circle' },
            { key: 'due-today', label: 'Heute fällig', icon: 'calendar' },
            { key: 'recently-closed', label: 'Kürzlich geschlossen', icon: 'check-circle' }
        ],
        statuses: [
            { value: 'open', label: 'Offen' },
            { value: 'in_progress', label: 'In Bearbeitung' },
            { value: 'pending', label: 'Wartend' },
            { value: 'resolved', label: 'Gelöst' },
            { value: 'closed', label: 'Geschlossen' }
        ],
        priorities: [
            { value: 'low', label: 'Niedrig' },
            { value: 'normal', label: 'Normal' },
            { value: 'high', label: 'Hoch' },
            { value: 'urgent', label: 'Kritisch' }
        ],
        columns: [
            { key: 'id', label: 'Ticket', className: 'id-column' },
            { key: 'status', label: 'Status', className: 'status-column' },
            { key: 'priority', label: 'Priorität', className: 'priority-column' },
            { key: 'title', label: 'Titel', className: 'title-column' },
            { key: 'requester', label: 'Anfragender' },
            { key: 'assignee', label: 'Zuständig' },
            { key: 'category', label: 'Kategorie' },
            { key: 'assets', label: 'Assets' },
            { key: 'sla', label: 'SLA', className: 'sla-column' },
            { key: 'updated_at', label: 'Aktualisiert' },
            { key: 'due_date', label: 'Fällig' }
        ],
        detailTabs: [
            { key: 'conversation', label: 'Konversation' },
            { key: 'knowledge', label: 'Wissen & ähnliche Fälle' },
            { key: 'activity', label: 'Aktivitäten' },
            { key: 'attachments', label: 'Anhänge' }
        ],

        async init() {
            this.restoreStateFromUrl();
            window.addEventListener('popstate', () => this.handleHistory());
            window.addEventListener('online', () => this.showToast('Verbindung wiederhergestellt.'));
            window.addEventListener('offline', () => this.showToast('Du bist offline. Änderungen können nicht gespeichert werden.', 'error'));
            await Promise.all([this.loadCategories(), this.loadQueueCounts(), this.loadSavedViews()]);
            await this.loadTickets();
            if (window.initialTicketId) {
                await this.loadTicket(window.initialTicketId, false);
                this.syncUrl();
            }
            this.refreshIcons();
        },

        rememberFocus() {
            const activeElement = document.activeElement;
            if (activeElement instanceof HTMLElement) this.focusReturnStack.push(activeElement);
        },

        restoreFocus() {
            const previousElement = this.focusReturnStack.pop();
            this.$nextTick(() => {
                if (previousElement?.isConnected) previousElement.focus();
            });
        },

        focusDialog(dialogSelector = '[role="dialog"]') {
            this.$nextTick(() => {
                const dialogs = [...document.querySelectorAll(dialogSelector)]
                    .filter(dialog => dialog.offsetParent !== null);
                const dialog = dialogs.at(-1);
                const target = dialog?.querySelector(
                    'button:not([disabled]), input:not([disabled]), select:not([disabled]), textarea:not([disabled]), [tabindex]:not([tabindex="-1"])'
                );
                target?.focus();
            });
        },

        trapFocus(event) {
            if (event.key !== 'Tab') return;
            const dialog = event.currentTarget.querySelector('[role="dialog"]');
            if (!dialog) return;
            const focusable = [...dialog.querySelectorAll(
                'a[href], button:not([disabled]), input:not([disabled]), select:not([disabled]), textarea:not([disabled]), [tabindex]:not([tabindex="-1"])'
            )].filter(element => element.offsetParent !== null);
            if (!focusable.length) return;
            const first = focusable[0];
            const last = focusable.at(-1);
            if (event.shiftKey && document.activeElement === first) {
                event.preventDefault();
                last.focus();
            } else if (!event.shiftKey && document.activeElement === last) {
                event.preventDefault();
                first.focus();
            }
        },

        get visibleColumns() {
            return this.columns;
        },

        get activeQueueLabel() {
            return this.queues.find(queue => queue.key === this.activeQueue)?.label || 'Tickets';
        },

        get activeFilterCount() {
            return ['status', 'priority', 'category_id', 'assignee'].filter(key => Boolean(this.filters[key])).length + (this.filters.mine ? 1 : 0);
        },

        get allVisibleSelected() {
            return this.tickets.length > 0 && this.tickets.every(ticket => this.selectedIds.includes(ticket.id));
        },

        get pageStart() {
            return this.pagination.total ? ((this.pagination.page - 1) * this.pagination.per_page) + 1 : 0;
        },

        get pageEnd() {
            return Math.min(this.pagination.page * this.pagination.per_page, this.pagination.total);
        },

        get newTicketCategoryName() {
            return this.categoryLabel(this.newTicket.category_id);
        },

        get creatingReview() {
            return this.newTicketCategoryName.toLowerCase() === 'review';
        },

        get creatingChange() {
            return this.newTicketCategoryName.toLowerCase() === 'change';
        },

        can(permission) {
            return this.isSuperuser || this.userPermissions.includes(permission);
        },

        canManageTickets() {
            return this.can('ticket_categories.manage') || this.can('ticket_alerts.manage') || this.can('notifications.manage');
        },

        canUpdateTicket() {
            return this.can('tickets.update') || this.can('tickets.update_own');
        },

        canDeleteSelection() {
            if (!this.selectedIds.length) return false;
            if (this.can('tickets.delete')) return true;
            if (!this.can('tickets.delete_own')) return false;
            const selectedTickets = this.tickets.filter(ticket => this.selectedIds.includes(ticket.id));
            return selectedTickets.length === this.selectedIds.length
                && selectedTickets.every(ticket => ticket.created_by === this.currentUsername);
        },

        async api(url, options = {}) {
            const response = await fetch(url, options);
            const contentType = response.headers.get('content-type') || '';
            const payload = contentType.includes('application/json') ? await response.json() : null;
            if (!response.ok) {
                const message = payload?.error || `Anfrage fehlgeschlagen (${response.status})`;
                const apiError = new Error(message);
                apiError.status = response.status;
                apiError.code = payload?.code;
                apiError.payload = payload;
                throw apiError;
            }
            return payload;
        },

        async loadTickets() {
            this.loading = true;
            this.error = '';
            const params = new URLSearchParams({
                page: this.pagination.page,
                per_page: this.pagination.per_page,
                sort: this.sort.key,
                direction: this.sort.direction,
                queue: this.activeQueue
            });
            Object.entries(this.filters).forEach(([key, value]) => {
                if (value) params.set(key, value === true ? '1' : value);
            });
            try {
                const result = await this.api(`/api/tickets?${params}`);
                this.tickets = result.items || [];
                this.pagination = {
                    page: result.page,
                    per_page: result.per_page,
                    total: result.total,
                    pages: result.pages
                };
                this.selectedIds = this.selectedIds.filter(id => this.tickets.some(ticket => ticket.id === id));
                this.syncUrl();
            } catch (error) {
                this.error = error.message;
            } finally {
                this.loading = false;
                this.refreshIcons();
            }
        },

        async loadCategories() {
            try {
                this.categories = await this.api('/api/ticket-categories');
            } catch (error) {
                this.showToast(error.message, 'error');
            }
        },

        async loadReviewableChanges() {
            this.reviewChangesLoading = true;
            try {
                const params = new URLSearchParams();
                if (this.changeSearch.trim()) params.set('search', this.changeSearch.trim());
                this.reviewableChanges = await this.api(`/api/tickets/reviewable-changes?${params}`);
            } catch (error) {
                this.reviewableChanges = [];
                this.showToast(error.message, 'error');
            } finally {
                this.reviewChangesLoading = false;
            }
        },

        async loadQueueCounts() {
            try {
                this.queueCounts = await this.api('/api/tickets/queues');
            } catch (error) {
                this.queueCounts = {};
            }
        },

        async loadSavedViews() {
            try {
                this.savedViews = await this.api('/api/ticket-views');
            } catch (error) {
                this.savedViews = [];
            }
        },

        async selectQueue(queue) {
            this.activeQueue = queue.key;
            this.pagination.page = 1;
            this.selectedIds = [];
            await this.loadTickets();
        },

        async searchChanged() {
            this.pagination.page = 1;
            await this.loadTickets();
        },

        sortBy(key) {
            if (this.sort.key === key) {
                this.sort.direction = this.sort.direction === 'asc' ? 'desc' : 'asc';
            } else {
                this.sort = { key, direction: 'asc' };
            }
            this.pagination.page = 1;
            this.loadTickets();
        },

        sortIcon(key) {
            if (this.sort.key !== key) return 'more-horizontal';
            return this.sort.direction === 'asc' ? 'chevron-up' : 'chevron-down';
        },

        sortAria(key) {
            if (this.sort.key !== key) return 'none';
            return this.sort.direction === 'asc' ? 'ascending' : 'descending';
        },

        iconSvg(name, size = 16) {
            const icon = window.feather?.icons?.[name];
            if (!icon) return '';
            return icon.toSvg({ width: size, height: size, 'aria-hidden': 'true' });
        },

        goToPage(page) {
            if (page < 1 || page > this.pagination.pages || page === this.pagination.page) return;
            this.pagination.page = page;
            this.loadTickets();
        },

        toggleAllVisible(event) {
            const visibleIds = this.tickets.map(ticket => ticket.id);
            if (event.target.checked) {
                this.selectedIds = [...new Set([...this.selectedIds, ...visibleIds])];
            } else {
                this.selectedIds = this.selectedIds.filter(id => !visibleIds.includes(id));
            }
        },

        clearFilter(key) {
            this.filters[key] = key === 'mine' ? false : '';
            this.pagination.page = 1;
            this.loadTickets();
        },

        resetFilters() {
            this.filters = { search: this.filters.search, status: '', priority: '', category_id: '', assignee: '', mine: false };
            this.draftFilters = { ...this.filters };
            this.pagination.page = 1;
            this.loadTickets();
        },

        resetDraftFilters() {
            this.draftFilters = { search: this.filters.search, status: '', priority: '', category_id: '', assignee: '', mine: false };
        },

        openMobileQueues() {
            this.rememberFocus();
            this.mobileQueuesOpen = true;
            this.focusDialog();
            this.refreshIcons();
        },

        closeMobileQueues() {
            if (!this.mobileQueuesOpen) return;
            this.mobileQueuesOpen = false;
            this.restoreFocus();
        },

        openFilter() {
            this.draftFilters = { ...this.filters };
            this.rememberFocus();
            this.filterOpen = true;
            this.focusDialog();
            this.refreshIcons();
        },

        closeFilter() {
            if (!this.filterOpen) return;
            this.filterOpen = false;
            this.restoreFocus();
        },

        openSaveView() {
            this.rememberFocus();
            this.saveViewOpen = true;
            this.focusDialog();
            this.refreshIcons();
        },

        closeSaveView() {
            if (!this.saveViewOpen) return;
            this.saveViewOpen = false;
            this.restoreFocus();
        },

        openShortcuts() {
            this.rememberFocus();
            this.showShortcuts = true;
            this.focusDialog();
            this.refreshIcons();
        },

        closeShortcuts() {
            if (!this.showShortcuts) return;
            this.showShortcuts = false;
            this.restoreFocus();
        },

        applyFilters() {
            this.filters = { ...this.draftFilters, search: this.filters.search };
            this.closeFilter();
            this.pagination.page = 1;
            this.loadTickets();
        },

        applySavedView(view) {
            this.filters = {
                search: '',
                status: '',
                priority: '',
                category_id: '',
                assignee: '',
                mine: false,
                ...(view.filters || {})
            };
            this.draftFilters = { ...this.filters };
            this.sort = {
                key: view.sort_by || 'updated_at',
                direction: view.sort_direction || 'desc'
            };
            this.pagination.page = 1;
            this.loadTickets();
        },

        async saveView() {
            if (!this.newView.name.trim()) {
                this.showToast('Bitte gib der Ansicht einen Namen.', 'error');
                return;
            }
            try {
                await this.api('/api/ticket-views', {
                    method: 'POST',
                    headers: { 'Content-Type': 'application/json' },
                    body: JSON.stringify({
                        ...this.newView,
                        filters: this.filters,
                        columns: this.visibleColumns.map(column => column.key),
                        sort_by: this.sort.key,
                        sort_direction: this.sort.direction
                    })
                });
                this.closeSaveView();
                this.newView = { name: '', is_favorite: false, is_default: false };
                await this.loadSavedViews();
                this.showToast('Ansicht gespeichert.');
            } catch (error) {
                this.showToast(error.message, 'error');
            }
        },

        async openTicket(ticket, event) {
            if (event?.metaKey || event?.ctrlKey) {
                this.openTicketInTab(ticket);
                return;
            }
            await this.loadTicket(ticket.id, true);
        },

        openTicketInTab(ticket) {
            window.open(`/tickets/${ticket.id}`, '_blank', 'noopener');
        },

        async loadTicket(ticketId, updateHistory = true) {
            this.detailLoading = true;
            this.detailTab = 'conversation';
            try {
                this.selectedTicket = await this.api(`/api/tickets/${ticketId}`);
                await this.loadAttachments(ticketId);
                if (updateHistory && window.location.pathname !== `/tickets/${ticketId}`) {
                    history.pushState({ ticketId }, '', `/tickets/${ticketId}${window.location.search}`);
                }
            } catch (error) {
                this.showToast(error.message, 'error');
                if (error.status === 404) this.closeTicket();
            } finally {
                this.detailLoading = false;
                this.refreshIcons();
            }
        },

        closeTicket(updateHistory = true) {
            this.selectedTicket = null;
            this.attachments = [];
            this.newComment = '';
            if (updateHistory && window.location.pathname !== '/tickets') {
                history.pushState({}, '', `/tickets${window.location.search}`);
            }
            this.refreshIcons();
        },

        async handleHistory() {
            const match = window.location.pathname.match(/^\/tickets\/(\d+)$/);
            if (match) await this.loadTicket(Number(match[1]), false);
            else this.closeTicket(false);
        },

        async updateTicketField(field, value) {
            if (!this.selectedTicket || !this.canUpdateTicket()) return;
            const ticket = this.selectedTicket;
            const payload = {
                title: ticket.title,
                description: ticket.description,
                category_id: ticket.category_id || null,
                priority: ticket.priority,
                status: ticket.status,
                requester_name: ticket.requester_name,
                requester_email: ticket.requester_email,
                assignee: ticket.assignee,
                assignee_email: ticket.assignee_email,
                due_date: ticket.due_date,
                updated_at: ticket.updated_at,
                tags: ticket.tags,
                custom_fields: ticket.custom_fields,
                asset_ids: ticket.asset_ids || [],
                change_ticket_id: ticket.review_relation?.role === 'review'
                    ? ticket.review_relation.change_ticket_id
                    : null
            };
            payload[field] = value;
            try {
                const result = await this.api(`/api/tickets/${ticket.id}`, {
                    method: 'PUT',
                    headers: { 'Content-Type': 'application/json' },
                    body: JSON.stringify(payload)
                });
                ticket.updated_at = result.updated_at || ticket.updated_at;
                const activeDetailTab = this.detailTab;
                this.selectedTicket = await this.api(`/api/tickets/${ticket.id}`);
                this.detailTab = activeDetailTab;
                this.showToast('Ticket aktualisiert.');
                await Promise.all([this.loadTickets(), this.loadQueueCounts()]);
            } catch (error) {
                this.showToast(error.message, 'error');
                if (error.code === 'change_review_required' && error.payload?.review_ticket_id) {
                    this.showToast(`Zuerst Review #${error.payload.review_ticket_id} abschließen.`, 'error');
                }
                if (error.code === 'ticket_update_conflict') {
                    this.showToast('Der aktuelle Ticketstand wurde geladen. Bitte Änderung erneut prüfen.', 'error');
                }
                await this.loadTicket(ticket.id, false);
            }
        },

        async addComment() {
            const body = this.newComment.trim();
            if (!body || !this.selectedTicket) return;
            this.saving = true;
            try {
                await this.api(`/api/tickets/${this.selectedTicket.id}/comments`, {
                    method: 'POST',
                    headers: { 'Content-Type': 'application/json' },
                    body: JSON.stringify({ body, is_internal: this.internalComment })
                });
                const ticketId = this.selectedTicket.id;
                this.newComment = '';
                await this.loadTicket(ticketId, false);
                this.showToast(this.internalComment ? 'Interne Notiz hinzugefügt.' : 'Antwort gesendet.');
            } catch (error) {
                this.showToast(error.message, 'error');
            } finally {
                this.saving = false;
            }
        },

        async loadAttachments(ticketId) {
            if (!this.can('attachment.download')) {
                this.attachments = [];
                return;
            }
            try {
                this.attachments = await this.api(`/attachments?entity_type=ticket&entity_id=${ticketId}`);
            } catch (error) {
                this.attachments = [];
            }
        },

        async uploadAttachment(event) {
            const file = event.target.files?.[0];
            if (!file || !this.selectedTicket) return;
            const form = new FormData();
            form.append('file', file);
            form.append('entity_type', 'ticket');
            form.append('entity_id', this.selectedTicket.id);
            try {
                await this.api('/attachments/upload', { method: 'POST', body: form });
                await this.loadAttachments(this.selectedTicket.id);
                this.detailTab = 'attachments';
                this.showToast('Anhang hochgeladen.');
            } catch (error) {
                this.showToast(error.message, 'error');
            } finally {
                event.target.value = '';
                this.refreshIcons();
            }
        },

        async openCreateTicket() {
            this.createError = '';
            if (!this.newTicket.category_id) await this.ticketTypeChanged();
            this.rememberFocus();
            this.createOpen = true;
            await this.$nextTick();
            this.$refs.createTitle?.focus();
            this.refreshIcons();
        },

        closeCreateTicket() {
            if ((this.newTicket.title || this.newTicket.description) && !window.confirm('Entwurf verwerfen?')) return;
            this.createOpen = false;
            this.restoreFocus();
        },

        async ticketTypeChanged() {
            const categoryNames = {
                incident: 'Incident',
                service_request: 'Service Request',
                change: 'Change',
                review: 'Review',
                improvement: 'Verbesserungen',
                inquiry: 'Allgemein'
            };
            const categoryName = categoryNames[this.newTicket.type];
            const category = this.categories.find(
                item => item.name.toLowerCase() === String(categoryName || '').toLowerCase()
            );
            if (category) this.newTicket.category_id = category.id;
            await this.ticketCategoryChanged();
        },

        async ticketCategoryChanged() {
            this.newTicket.change_ticket_id = '';
            this.changeSearch = '';
            this.reviewableChanges = [];
            if (this.creatingReview) await this.loadReviewableChanges();
        },

        async createTicket() {
            if (!this.newTicket.title.trim() || !this.newTicket.description.trim()) {
                this.createError = 'Titel und Beschreibung sind erforderlich.';
                return;
            }
            if (this.creatingReview && !this.newTicket.change_ticket_id) {
                this.createError = 'Für ein Review muss ein zugehöriger Change ausgewählt werden.';
                return;
            }
            this.saving = true;
            this.createError = '';
            try {
                const result = await this.api('/api/tickets', {
                    method: 'POST',
                    headers: { 'Content-Type': 'application/json' },
                    body: JSON.stringify({
                        ...this.newTicket,
                        category_id: this.newTicket.category_id || null
                    })
                });
                const ticketId = result.id;
                this.newTicket = {
                    title: '',
                    description: '',
                    type: 'incident',
                    category_id: '',
                    priority: 'normal',
                    assignee: '',
                    due_date: '',
                    asset_ids: [],
                    change_ticket_id: ''
                };
                this.createOpen = false;
                this.restoreFocus();
                await Promise.all([this.loadTickets(), this.loadQueueCounts()]);
                await this.loadTicket(ticketId, true);
                if (result.review_ticket_id) {
                    this.showToast(`Change #${ticketId} und Review #${result.review_ticket_id} erstellt.`);
                } else if (result.change_ticket_id) {
                    this.showToast(`Review #${ticketId} mit Change #${result.change_ticket_id} verknüpft.`);
                } else {
                    this.showToast(`Ticket #${ticketId} erstellt.`);
                }
            } catch (error) {
                this.createError = error.message;
            } finally {
                this.saving = false;
            }
        },

        async openAssetPicker(target) {
            this.rememberFocus();
            this.assetPickerTarget = target;
            this.assetSearch = '';
            this.assetSelection = target === 'detail'
                ? [...(this.selectedTicket?.asset_ids || [])]
                : [...this.newTicket.asset_ids];
            this.assetPickerOpen = true;
            await this.loadAssetOptions();
            this.$nextTick(() => this.$refs.assetSearch?.focus());
        },

        closeAssetPicker() {
            if (!this.assetPickerOpen) return;
            this.assetPickerOpen = false;
            this.restoreFocus();
        },

        async loadAssetOptions() {
            this.assetLoading = true;
            try {
                const params = new URLSearchParams({ page: 1, per_page: 50, search: this.assetSearch });
                const result = await this.api(`/api/ticket-assets/search?${params}`);
                this.assetOptions = result.items || [];
            } catch (error) {
                this.showToast(error.message, 'error');
                this.assetOptions = [];
            } finally {
                this.assetLoading = false;
                this.refreshIcons();
            }
        },

        toggleAsset(assetId) {
            this.assetSelection = this.assetSelection.includes(assetId)
                ? this.assetSelection.filter(id => id !== assetId)
                : [...this.assetSelection, assetId];
        },

        async applyAssetSelection() {
            if (this.assetPickerTarget === 'create') {
                this.newTicket.asset_ids = [...this.assetSelection];
                this.closeAssetPicker();
                return;
            }
            if (!this.selectedTicket) return;
            this.selectedTicket.asset_ids = [...this.assetSelection];
            this.closeAssetPicker();
            await this.updateTicketField('asset_ids', this.assetSelection);
            await this.loadTicket(this.selectedTicket.id, false);
        },

        async unlinkAsset(assetId) {
            if (!this.selectedTicket) return;
            const assetIds = (this.selectedTicket.asset_ids || []).filter(id => id !== assetId);
            this.selectedTicket.asset_ids = assetIds;
            await this.updateTicketField('asset_ids', assetIds);
            await this.loadTicket(this.selectedTicket.id, false);
        },

        openBulk(field) {
            const labels = { assignee: 'Tickets zuweisen', status: 'Status ändern', priority: 'Priorität ändern' };
            const defaults = { assignee: '', status: 'in_progress', priority: 'normal' };
            this.rememberFocus();
            this.bulkDialog = { open: true, field, value: defaults[field], title: labels[field] };
            this.focusDialog();
            this.refreshIcons();
        },

        closeBulk() {
            if (!this.bulkDialog.open) return;
            this.bulkDialog.open = false;
            this.restoreFocus();
        },

        async applyBulk() {
            if (!this.selectedIds.length || !this.bulkDialog.value) return;
            try {
                await this.api('/api/tickets/bulk', {
                    method: 'PATCH',
                    headers: { 'Content-Type': 'application/json' },
                    body: JSON.stringify({
                        ticket_ids: this.selectedIds,
                        changes: { [this.bulkDialog.field]: this.bulkDialog.value }
                    })
                });
                const count = this.selectedIds.length;
                this.closeBulk();
                this.selectedIds = [];
                await Promise.all([this.loadTickets(), this.loadQueueCounts()]);
                this.showToast(`${count} Tickets aktualisiert.`);
            } catch (error) {
                this.showToast(error.message, 'error');
            }
        },

        async deleteSelected() {
            if (!this.canDeleteSelection() || this.deletingTickets) return;
            const ticketIds = [...this.selectedIds];
            const message = ticketIds.length === 1
                ? 'Das ausgewählte Ticket endgültig löschen?'
                : `${ticketIds.length} ausgewählte Tickets endgültig löschen?`;
            if (!window.confirm(`${message}\n\nKommentare und Verknüpfungen werden ebenfalls entfernt.`)) return;

            this.deletingTickets = true;
            try {
                await Promise.all(ticketIds.map(ticketId => this.api(`/api/tickets/${ticketId}`, { method: 'DELETE' })));
                if (this.selectedTicket && ticketIds.includes(this.selectedTicket.id)) this.closeTicket();
                this.selectedIds = [];
                await Promise.all([this.loadTickets(), this.loadQueueCounts()]);
                this.showToast(ticketIds.length === 1 ? 'Ticket gelöscht.' : `${ticketIds.length} Tickets gelöscht.`);
            } catch (error) {
                await Promise.all([this.loadTickets(), this.loadQueueCounts()]);
                this.showToast(error.message, 'error');
            } finally {
                this.deletingTickets = false;
            }
        },

        exportSelected() {
            const rows = this.tickets.filter(ticket => this.selectedIds.includes(ticket.id));
            const header = ['Ticket', 'Status', 'Priorität', 'Titel', 'Anfragender', 'Zuständig', 'Kategorie', 'Aktualisiert'];
            const escape = value => `"${String(value ?? '').replaceAll('"', '""')}"`;
            const csv = [
                header,
                ...rows.map(ticket => [
                    ticket.id,
                    this.statusLabel(ticket.status),
                    this.priorityLabel(ticket.priority),
                    ticket.title,
                    ticket.requester_name || ticket.created_by,
                    ticket.assignee,
                    ticket.category_name,
                    ticket.updated_at
                ])
            ].map(row => row.map(escape).join(';')).join('\n');
            const url = URL.createObjectURL(new Blob([`\ufeff${csv}`], { type: 'text/csv;charset=utf-8' }));
            const link = document.createElement('a');
            link.href = url;
            link.download = `tickets-${new Date().toISOString().slice(0, 10)}.csv`;
            link.click();
            URL.revokeObjectURL(url);
        },

        handleShortcut(event) {
            const target = event.target;
            const typing = ['INPUT', 'TEXTAREA', 'SELECT'].includes(target?.tagName) || target?.isContentEditable;
            if (event.key === 'Escape') {
                if (this.showShortcuts) this.closeShortcuts();
                else if (this.assetPickerOpen) this.closeAssetPicker();
                else if (this.createOpen) this.closeCreateTicket();
                else if (this.filterOpen) this.closeFilter();
                else if (this.saveViewOpen) this.closeSaveView();
                else if (this.bulkDialog.open) this.closeBulk();
                else if (this.mobileQueuesOpen) this.closeMobileQueues();
                else if (this.selectedTicket) this.closeTicket();
                return;
            }
            if (typing) return;
            if (event.key === '/') {
                event.preventDefault();
                this.$refs.search?.focus();
            } else if (event.key.toLowerCase() === 'c' && this.can('tickets.create')) {
                event.preventDefault();
                this.openCreateTicket();
            } else if (event.key === '?') {
                event.preventDefault();
                this.openShortcuts();
            } else if (event.key.toLowerCase() === 'j') {
                this.moveKeyboardSelection(1);
            } else if (event.key.toLowerCase() === 'k') {
                this.moveKeyboardSelection(-1);
            } else if (event.key === 'Enter' && this.keyboardIndex >= 0) {
                this.loadTicket(this.tickets[this.keyboardIndex].id, true);
            } else if (event.key.toLowerCase() === 'r' && this.selectedTicket) {
                this.detailTab = 'conversation';
                this.internalComment = false;
                this.$nextTick(() => this.$refs.comment?.focus());
            } else if (event.key.toLowerCase() === 'n' && this.selectedTicket && this.can('tickets.comment_internal')) {
                this.detailTab = 'conversation';
                this.internalComment = true;
                this.$nextTick(() => this.$refs.comment?.focus());
            }
        },

        moveKeyboardSelection(direction) {
            if (!this.tickets.length) return;
            this.keyboardIndex = Math.max(0, Math.min(this.tickets.length - 1, this.keyboardIndex + direction));
            document.querySelector(`[data-ticket-index="${this.keyboardIndex}"]`)?.focus();
        },

        restoreStateFromUrl() {
            const params = new URLSearchParams(window.location.search);
            if (params.has('queue')) this.activeQueue = params.get('queue');
            ['search', 'status', 'priority', 'category_id', 'assignee'].forEach(key => {
                if (params.has(key)) this.filters[key] = params.get(key);
            });
            this.filters.mine = params.get('mine') === '1';
            if (params.has('sort')) this.sort.key = params.get('sort');
            if (params.has('direction')) this.sort.direction = params.get('direction') === 'asc' ? 'asc' : 'desc';
            if (params.has('page')) this.pagination.page = Math.max(1, Number(params.get('page')) || 1);
            this.draftFilters = { ...this.filters };
        },

        syncUrl() {
            const params = new URLSearchParams();
            if (this.activeQueue !== 'my-work') params.set('queue', this.activeQueue);
            Object.entries(this.filters).forEach(([key, value]) => {
                if (value) params.set(key, value === true ? '1' : value);
            });
            if (this.sort.key !== 'updated_at') params.set('sort', this.sort.key);
            if (this.sort.direction !== 'desc') params.set('direction', this.sort.direction);
            if (this.pagination.page > 1) params.set('page', this.pagination.page);
            const query = params.toString();
            const path = this.selectedTicket ? `/tickets/${this.selectedTicket.id}` : '/tickets';
            history.replaceState(history.state || {}, '', `${path}${query ? `?${query}` : ''}`);
        },

        statusLabel(value) {
            return this.statuses.find(item => item.value === value)?.label || value || 'Unbekannt';
        },

        priorityLabel(value) {
            return this.priorities.find(item => item.value === value)?.label || value || 'Normal';
        },

        categoryLabel(id) {
            return this.categories.find(category => Number(category.id) === Number(id))?.name || 'Ohne Kategorie';
        },

        isClosedStatus(value) {
            return ['closed', 'resolved', 'done'].includes(String(value || '').toLowerCase());
        },

        statusOptionDisabled(value) {
            if (!this.selectedTicket || !this.isClosedStatus(value)) return false;
            if (this.categoryLabel(this.selectedTicket.category_id).toLowerCase() !== 'change') return false;
            return !this.selectedTicket.review_relation?.approved;
        },

        reviewGateLabel(ticket = this.selectedTicket) {
            const relation = ticket?.review_relation;
            if (!relation) return 'Kein Review verknüpft';
            if (relation.role === 'review') {
                return `Change #${relation.change_ticket_id}`;
            }
            return relation.approved
                ? `Review #${relation.review_ticket_id} freigegeben`
                : `Review #${relation.review_ticket_id} ausstehend`;
        },

        activityIcon(action) {
            return {
                create: 'plus-circle',
                update: 'edit-3',
                bulk_update: 'layers',
                comment: 'message-circle',
                watch: 'eye',
                unwatch: 'eye-off',
                merge: 'git-merge'
            }[action] || 'activity';
        },

        activitySummary(activity) {
            const details = activity?.details || {};
            if (details.preview) {
                return `${details.is_internal ? 'Interne Notiz' : 'Kommentar'}: ${details.preview}`;
            }
            if (details.email) return `E-Mail: ${details.email}`;
            if (details.title) return details.title;
            if (details.merged_into) return `Zusammengeführt in Ticket #${details.merged_into}`;
            return '';
        },

        isOverdue(ticket) {
            if (!ticket.due_date || ['closed', 'resolved'].includes(ticket.status)) return false;
            return new Date(`${ticket.due_date}T23:59:59`) < new Date();
        },

        slaState(ticket) {
            if (['closed', 'resolved'].includes(ticket.status)) return { state: 'met', icon: 'check-circle', label: 'SLA abgeschlossen' };
            if (!ticket.due_date) return { state: 'neutral', icon: 'clock', label: 'Kein Ziel' };
            const remaining = new Date(`${ticket.due_date}T23:59:59`) - new Date();
            if (remaining < 0) return { state: 'breached', icon: 'alert-octagon', label: `Verletzt seit ${this.durationLabel(Math.abs(remaining))}` };
            if (remaining < 4 * 3600000) return { state: 'critical', icon: 'alert-triangle', label: `${this.durationLabel(remaining)} verbleibend` };
            if (remaining < 24 * 3600000) return { state: 'warning', icon: 'clock', label: `${this.durationLabel(remaining)} verbleibend` };
            return { state: 'neutral', icon: 'clock', label: `${this.durationLabel(remaining)} verbleibend` };
        },

        durationLabel(milliseconds) {
            const minutes = Math.max(1, Math.round(milliseconds / 60000));
            const days = Math.floor(minutes / 1440);
            const hours = Math.floor((minutes % 1440) / 60);
            const rest = minutes % 60;
            if (days) return `${days} T ${hours} Std`;
            if (hours) return `${hours} Std ${rest} Min`;
            return `${rest} Min`;
        },

        formatDate(value) {
            if (!value) return '—';
            const date = new Date(`${String(value).slice(0, 10)}T12:00:00`);
            return Number.isNaN(date.getTime()) ? value : new Intl.DateTimeFormat('de-DE', { day: '2-digit', month: '2-digit', year: 'numeric' }).format(date);
        },

        formatDateTime(value) {
            if (!value) return '—';
            const date = new Date(String(value).replace(' ', 'T') + (String(value).includes('Z') ? '' : 'Z'));
            return Number.isNaN(date.getTime()) ? value : new Intl.DateTimeFormat('de-DE', { dateStyle: 'medium', timeStyle: 'short' }).format(date);
        },

        formatRelative(value) {
            if (!value) return '—';
            const date = new Date(String(value).replace(' ', 'T') + (String(value).includes('Z') ? '' : 'Z'));
            if (Number.isNaN(date.getTime())) return value;
            const seconds = Math.round((date - new Date()) / 1000);
            const formatter = new Intl.RelativeTimeFormat('de-DE', { numeric: 'auto' });
            if (Math.abs(seconds) < 3600) return formatter.format(Math.round(seconds / 60), 'minute');
            if (Math.abs(seconds) < 86400) return formatter.format(Math.round(seconds / 3600), 'hour');
            if (Math.abs(seconds) < 604800) return formatter.format(Math.round(seconds / 86400), 'day');
            return this.formatDate(value);
        },

        formatFileSize(bytes) {
            if (bytes === null || bytes === undefined) return '—';
            if (bytes < 1024) return `${bytes} B`;
            if (bytes < 1048576) return `${(bytes / 1024).toFixed(1)} KB`;
            return `${(bytes / 1048576).toFixed(1)} MB`;
        },

        initials(name) {
            return String(name || '?').split(/\s+/).slice(0, 2).map(part => part[0]).join('').toUpperCase();
        },

        tabCount(key) {
            if (!this.selectedTicket) return 0;
            if (key === 'conversation') return (this.selectedTicket.comments || []).length;
            if (key === 'knowledge') {
                const context = this.selectedTicket.work_context || {};
                return (context.knowledge_entries || []).length + (context.similar_resolved_tickets || []).length;
            }
            if (key === 'attachments') return this.attachments.length;
            if (key === 'activity') return (this.selectedTicket.activity || []).length;
            return 0;
        },

        copyTicketLink() {
            navigator.clipboard?.writeText(window.location.href);
            this.showToast('Ticket-Link kopiert.');
        },

        showToast(message, type = 'success') {
            const id = ++this.toastSequence;
            this.toasts.push({ id, message, type });
            window.setTimeout(() => {
                this.toasts = this.toasts.filter(toast => toast.id !== id);
            }, 4500);
            this.refreshIcons();
        },

        refreshIcons() {
            window.clearTimeout(this.iconRefreshTimer);
            this.iconRefreshTimer = window.setTimeout(() => {
                this.$nextTick(() => {
                    try {
                        window.feather?.replace({ width: 16, height: 16 });
                    } catch {
                        // A delayed Alpine update can remove an icon while Feather is replacing it.
                    }
                });
            }, 40);
        }
    }));
});
