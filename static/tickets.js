document.addEventListener('alpine:init', () => {
    Alpine.data('ticketsApp', () => ({
        tickets: [],
        categories: [],
        alerts: [],
        assets: [],
        selectedTicket: null,
        ticketAttachments: [],
        ticketAttachmentError: '',
        knowledgeSuggestions: [],
        knowledgeLoading: false,
        userPermissions: window.inventoryPermissions || [],
        isSuperuser: window.inventoryIsSuperuser || false,
        currentUsername: window.inventoryUsername || '',
        filters: {
            status: '',
            priority: '',
            category_id: '',
            mine: false,
            search: ''
        },
        statusOptions: ['open', 'in_progress', 'pending', 'resolved', 'closed'],
        statusLabels: {
            open: 'Offen',
            in_progress: 'In Bearbeitung',
            pending: 'Wartet',
            resolved: 'Gelöst',
            closed: 'Geschlossen'
        },
        roadmapStatusLabels: {
            planned: 'Geplant',
            in_progress: 'In Arbeit',
            blocked: 'Blockiert',
            done: 'Erledigt'
        },
        priorityOptions: ['low', 'normal', 'high', 'urgent'],
        stats: {
            open: 0,
            in_progress: 0,
            pending: 0,
            resolved: 0
        },
        ticketModalOpen: false,
        ticketError: '',
        newTicket: {
            title: '',
            description: '',
            category_id: '',
            priority: 'normal',
            assignee: '',
            assignee_email: '',
            due_date: '',
            tags: '',
            custom_fields: [],
            asset_ids: []
        },
        newComment: '',
        internalComment: false,
        newWatcher: '',
        activeAdminTab: 'categories',
        newCategory: {
            name: '',
            description: '',
            color: '#2563eb',
            sla_hours: 72,
            is_default: false
        },
        newAlert: {
            name: '',
            event_type: 'created',
            status_match: '',
            priority_match: '',
            category_id: '',
            recipient_emails: '',
            is_enabled: true
        },
        notificationSettings: {
            enabled: false,
            smtp_host: '',
            smtp_port: 587,
            smtp_username: '',
            smtp_password: '',
            smtp_from: '',
            use_tls: true,
            default_recipients: ''
        },
        notificationMessage: '',
        testRecipients: '',

        async init() {
            await this.loadCategories();
            await this.loadAssets();
            await this.loadTickets();
            if (this.can('ticket_alerts.manage')) {
                await this.loadAlerts();
            }
            if (this.can('notifications.manage')) {
                await this.loadNotificationSettings();
            }
            await this.loadStats();
            const params = new URLSearchParams(window.location.search);
            const ticketId = params.get('ticket_id');
            if (ticketId) {
                await this.selectTicket({ id: ticketId });
            }
            this.$nextTick(() => feather.replace());
        },

        can(permissionKey) {
            return this.isSuperuser || this.userPermissions.includes(permissionKey);
        },

        openNewTicket() {
            this.ticketError = '';
            this.ticketModalOpen = true;
        },

        addCustomField() {
            this.newTicket.custom_fields.push({ key: '', value: '' });
        },

        removeCustomField(index) {
            this.newTicket.custom_fields.splice(index, 1);
        },

        async loadCategories() {
            const response = await fetch('/api/ticket-categories');
            if (response.ok) {
                this.categories = await response.json();
            }
        },

        async loadTickets() {
            const params = new URLSearchParams();
            if (this.filters.status) params.append('status', this.filters.status);
            if (this.filters.priority) params.append('priority', this.filters.priority);
            if (this.filters.category_id) params.append('category_id', this.filters.category_id);
            if (this.filters.mine) params.append('mine', '1');
            if (this.filters.search) params.append('search', this.filters.search);

            const response = await fetch(`/api/tickets?${params.toString()}`);
            if (response.ok) {
                this.tickets = await response.json();
            }
            this.$nextTick(() => feather.replace());
        },

        async loadAssets() {
            const response = await fetch('/api/assets');
            if (response.ok) {
                this.assets = await response.json();
            }
        },

        async loadStats() {
            const response = await fetch('/api/tickets');
            if (!response.ok) return;
            const allTickets = await response.json();
            const counts = { open: 0, in_progress: 0, pending: 0, resolved: 0 };
            allTickets.forEach((ticket) => {
                if (counts[ticket.status] !== undefined) {
                    counts[ticket.status] += 1;
                }
            });
            this.stats = counts;
        },

        async selectTicket(ticket) {
            const response = await fetch(`/api/tickets/${ticket.id}`);
            if (response.ok) {
                this.selectedTicket = await response.json();
                window.PONDSEC_AI_CONTEXT = { type: 'ticket', id: this.selectedTicket.id };
                if (!this.selectedTicket.asset_ids) {
                    this.selectedTicket.asset_ids = (this.selectedTicket.assets || []).map((asset) => asset.id);
                }
                this.newComment = '';
                this.internalComment = false;
                this.newWatcher = '';
                await this.loadKnowledgeSuggestions();
                if (this.can('attachment.download')) {
                    await this.loadTicketAttachments(this.selectedTicket.id);
                } else {
                    this.ticketAttachments = [];
                }
                this.$nextTick(() => feather.replace());
            }
        },

        closeTicket() {
            this.selectedTicket = null;
            window.PONDSEC_AI_CONTEXT = { type: 'tickets' };
            this.knowledgeSuggestions = [];
            this.ticketAttachments = [];
            this.ticketAttachmentError = '';
        },

        formatFileSize(bytes) {
            if (!bytes && bytes !== 0) return '-';
            if (bytes < 1024) return `${bytes} B`;
            const kb = bytes / 1024;
            if (kb < 1024) return `${kb.toFixed(1)} KB`;
            const mb = kb / 1024;
            return `${mb.toFixed(1)} MB`;
        },

        async loadTicketAttachments(ticketId) {
            const response = await fetch(`/attachments?entity_type=ticket&entity_id=${ticketId}`);
            if (response.ok) {
                this.ticketAttachments = await response.json();
            }
        },

        async uploadTicketAttachment(event) {
            if (!this.selectedTicket) return;
            const file = event.target.files?.[0];
            if (!file) return;
            const formData = new FormData();
            formData.append('entity_type', 'ticket');
            formData.append('entity_id', this.selectedTicket.id);
            formData.append('file', file);
            this.ticketAttachmentError = '';
            const response = await fetch('/attachments/upload', {
                method: 'POST',
                body: formData
            });
            if (response.ok) {
                await this.loadTicketAttachments(this.selectedTicket.id);
            } else {
                const error = await response.json();
                this.ticketAttachmentError = error.error || 'Upload fehlgeschlagen';
            }
            event.target.value = '';
        },

        async deleteTicketAttachment(attachmentId) {
            if (!confirm('Anhang wirklich löschen?')) return;
            const response = await fetch(`/attachments/${attachmentId}/delete`, { method: 'POST' });
            if (response.ok && this.selectedTicket) {
                await this.loadTicketAttachments(this.selectedTicket.id);
            }
        },

        async loadKnowledgeSuggestions() {
            if (!this.selectedTicket) return;
            if (!(this.can('knowledge.view') || this.can('knowledge.manage'))) {
                this.knowledgeSuggestions = [];
                return;
            }
            this.knowledgeLoading = true;
            const queryParts = [this.selectedTicket.title, this.selectedTicket.description].filter(Boolean).join(' ');
            const params = new URLSearchParams();
            if (queryParts) params.append('query', queryParts);
            if (this.selectedTicket.id) params.append('ticket_id', this.selectedTicket.id);
            const response = await fetch(`/api/knowledge/suggestions?${params.toString()}`);
            if (response.ok) {
                this.knowledgeSuggestions = await response.json();
            } else {
                this.knowledgeSuggestions = [];
            }
            this.knowledgeLoading = false;
        },

        async updateTicket() {
            if (!this.selectedTicket) return;
            const payload = {
                title: this.selectedTicket.title,
                description: this.selectedTicket.description,
                category_id: this.selectedTicket.category_id,
                priority: this.selectedTicket.priority,
                status: this.selectedTicket.status,
                requester_name: this.selectedTicket.requester_name,
                requester_email: this.selectedTicket.requester_email,
                assignee: this.selectedTicket.assignee,
                assignee_email: this.selectedTicket.assignee_email,
                due_date: this.selectedTicket.due_date,
                tags: this.selectedTicket.tags,
                custom_fields: this.selectedTicket.custom_fields,
                asset_ids: this.selectedTicket.asset_ids
            };
            const response = await fetch(`/api/tickets/${this.selectedTicket.id}`, {
                method: 'PUT',
                headers: { 'Content-Type': 'application/json' },
                body: JSON.stringify(payload)
            });
            if (response.ok) {
                await this.selectTicket(this.selectedTicket);
                await this.loadTickets();
                await this.loadStats();
            }
        },

        async createTicket() {
            this.ticketError = '';
            const tags = this.newTicket.tags
                ? this.newTicket.tags.split(',').map((tag) => tag.trim()).filter(Boolean)
                : [];
            const customFields = (this.newTicket.custom_fields || []).filter((field) => field.key || field.value);

            const payload = {
                title: this.newTicket.title,
                description: this.newTicket.description,
                category_id: this.newTicket.category_id || null,
                priority: this.newTicket.priority,
                assignee: this.newTicket.assignee,
                assignee_email: this.newTicket.assignee_email,
                due_date: this.newTicket.due_date,
                tags,
                custom_fields: customFields,
                asset_ids: this.newTicket.asset_ids
            };

            const response = await fetch('/api/tickets', {
                method: 'POST',
                headers: { 'Content-Type': 'application/json' },
                body: JSON.stringify(payload)
            });

            if (response.ok) {
                this.ticketModalOpen = false;
                this.newTicket = {
                    title: '',
                    description: '',
                    category_id: '',
                    priority: 'normal',
                    assignee: '',
                    assignee_email: '',
                    due_date: '',
                    tags: '',
                    custom_fields: [],
                    asset_ids: []
                };
                await this.loadTickets();
                await this.loadStats();
            } else {
                const error = await response.json();
                this.ticketError = error.error || 'Ticket konnte nicht erstellt werden.';
            }
        },

        async addComment() {
            if (!this.newComment || !this.selectedTicket) return;
            const response = await fetch(`/api/tickets/${this.selectedTicket.id}/comments`, {
                method: 'POST',
                headers: { 'Content-Type': 'application/json' },
                body: JSON.stringify({ body: this.newComment, is_internal: this.internalComment })
            });
            if (response.ok) {
                await this.selectTicket(this.selectedTicket);
                await this.loadTickets();
            }
        },

        async addWatcher() {
            if (!this.newWatcher || !this.selectedTicket) return;
            const response = await fetch(`/api/tickets/${this.selectedTicket.id}/watchers`, {
                method: 'POST',
                headers: { 'Content-Type': 'application/json' },
                body: JSON.stringify({ email: this.newWatcher })
            });
            if (response.ok) {
                await this.selectTicket(this.selectedTicket);
                this.newWatcher = '';
            }
        },

        defaultRoadmapSteps() {
            return [
                { title: 'Analyse & Scope', description: 'Ziele, Anforderungen und Erfolgskriterien definieren.', status: 'planned' },
                { title: 'Konzept & Design', description: 'Architektur, UI/UX und technische Umsetzung planen.', status: 'planned' },
                { title: 'Implementierung', description: 'Features entwickeln und integrieren.', status: 'planned' },
                { title: 'Qualitätssicherung', description: 'Tests, Review und Abnahme durchführen.', status: 'planned' },
                { title: 'Rollout & Monitoring', description: 'Deployment, Dokumentation und Monitoring vorbereiten.', status: 'planned' }
            ];
        },

        async createRoadmapForTicket() {
            if (!this.selectedTicket) return;
            const payload = {
                ticket_id: this.selectedTicket.id,
                steps: this.defaultRoadmapSteps()
            };
            const response = await fetch('/api/roadmaps', {
                method: 'POST',
                headers: { 'Content-Type': 'application/json' },
                body: JSON.stringify(payload)
            });
            if (response.ok) {
                await this.selectTicket(this.selectedTicket);
            }
        },

        selectedAssetsForNewTicket() {
            const selectedIds = new Set(this.newTicket.asset_ids || []);
            return this.assets.filter((asset) => selectedIds.has(asset.id));
        },

        async removeWatcher(watcherId) {
            if (!this.selectedTicket) return;
            const response = await fetch(`/api/tickets/${this.selectedTicket.id}/watchers/${watcherId}`, {
                method: 'DELETE'
            });
            if (response.ok) {
                await this.selectTicket(this.selectedTicket);
            }
        },

        async loadAlerts() {
            const response = await fetch('/api/ticket-alerts');
            if (response.ok) {
                this.alerts = await response.json();
            }
        },

        async createCategory() {
            const payload = { ...this.newCategory };
            const response = await fetch('/api/ticket-categories', {
                method: 'POST',
                headers: { 'Content-Type': 'application/json' },
                body: JSON.stringify(payload)
            });
            if (response.ok) {
                this.newCategory = { name: '', description: '', color: '#2563eb', sla_hours: 72, is_default: false };
                await this.loadCategories();
            }
        },

        async deleteCategory(category) {
            if (!category) return;
            const confirmed = window.confirm(
                `Kategorie "${category.name}" löschen? Tickets werden danach ohne Kategorie geführt.`
            );
            if (!confirmed) return;
            const response = await fetch(`/api/ticket-categories/${category.id}`, {
                method: 'DELETE'
            });
            if (response.ok) {
                await this.loadCategories();
                await this.loadTickets();
                if (this.selectedTicket) {
                    await this.selectTicket(this.selectedTicket);
                }
            } else {
                const error = await response.json();
                alert(error.error || 'Kategorie konnte nicht gelöscht werden.');
            }
        },

        async createAlert() {
            const payload = { ...this.newAlert };
            const response = await fetch('/api/ticket-alerts', {
                method: 'POST',
                headers: { 'Content-Type': 'application/json' },
                body: JSON.stringify(payload)
            });
            if (response.ok) {
                this.newAlert = {
                    name: '',
                    event_type: 'created',
                    status_match: '',
                    priority_match: '',
                    category_id: '',
                    recipient_emails: '',
                    is_enabled: true
                };
                await this.loadAlerts();
            }
        },

        async deleteAlert(alertId) {
            const response = await fetch(`/api/ticket-alerts/${alertId}`, {
                method: 'DELETE'
            });
            if (response.ok) {
                await this.loadAlerts();
            }
        },

        async loadNotificationSettings() {
            const response = await fetch('/api/notifications/settings');
            if (response.ok) {
                this.notificationSettings = await response.json();
            }
        },

        async saveNotificationSettings() {
            const response = await fetch('/api/notifications/settings', {
                method: 'POST',
                headers: { 'Content-Type': 'application/json' },
                body: JSON.stringify(this.notificationSettings)
            });
            if (response.ok) {
                this.notificationSettings = await response.json();
                this.notificationMessage = 'Einstellungen gespeichert.';
            } else {
                this.notificationMessage = 'Einstellungen konnten nicht gespeichert werden.';
            }
        },

        async sendTestEmail() {
            this.notificationMessage = '';
            const response = await fetch('/api/notifications/test', {
                method: 'POST',
                headers: { 'Content-Type': 'application/json' },
                body: JSON.stringify({ recipients: this.testRecipients })
            });
            if (response.ok) {
                this.notificationMessage = 'Test-E-Mail wurde versendet.';
            } else {
                const error = await response.json();
                this.notificationMessage = error.error || 'Test-E-Mail fehlgeschlagen.';
            }
        }
    }));
});
