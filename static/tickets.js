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
        selectedTicketIds: [],
        mergeModalOpen: false,
        mergeTargetTicketId: '',
        mergeTicketNote: '',
        mergeErrorMessage: '',
        ticketNotice: {
            message: '',
            type: 'info'
        },
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
        ticketFieldErrors: {},
        ticketSaving: false,
        newTicket: {
            title: '',
            description: '',
            category_id: '',
            priority: 'normal',
            requester_name: '',
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
            this.currentUsername = this.resolveCurrentUsername();
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

        resolveCurrentUsername() {
            const scriptUsername = window.inventoryUsername;
            if (typeof scriptUsername === 'string' && scriptUsername.trim()) {
                return scriptUsername.trim();
            }
            const bodyUsername = document.body?.dataset?.currentUsername;
            if (typeof bodyUsername === 'string' && bodyUsername.trim()) {
                return bodyUsername.trim();
            }
            const label = document.querySelector('[data-current-username-label]');
            if (label?.textContent?.trim()) {
                return label.textContent.trim();
            }
            return '';
        },

        canUpdateSelectedTicket() {
            if (!this.selectedTicket) return false;
            if (this.selectedTicket.access && typeof this.selectedTicket.access.can_update === 'boolean') {
                return this.selectedTicket.access.can_update;
            }
            return this.can('tickets.update') || this.can('tickets.update_own');
        },

        canDeleteSelectedTicket() {
            if (!this.selectedTicket) return false;
            if (this.selectedTicket.access && typeof this.selectedTicket.access.can_delete === 'boolean') {
                return this.selectedTicket.access.can_delete;
            }
            return this.can('tickets.delete') || this.can('tickets.delete_own');
        },

        canCommentSelectedTicket() {
            if (!this.selectedTicket) return false;
            if (this.selectedTicket.access && typeof this.selectedTicket.access.can_comment === 'boolean') {
                return this.selectedTicket.access.can_comment;
            }
            return this.can('tickets.comment') || this.can('tickets.comment_own');
        },

        openNewTicket() {
            this.ticketError = '';
            this.ticketFieldErrors = {};
            this.currentUsername = this.resolveCurrentUsername();
            this.ticketModalOpen = true;
            if (!this.newTicket.requester_name && this.currentUsername) {
                this.newTicket.requester_name = this.currentUsername;
            }
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
                this.selectedTicketIds = this.selectedTicketIds.filter((ticketId) =>
                    this.tickets.some((ticket) => String(ticket.id) === String(ticketId))
                );
                if (this.mergeTargetTicketId && !this.selectedTicketIds.includes(String(this.mergeTargetTicketId))) {
                    this.mergeTargetTicketId = this.selectedTicketIds[0] || '';
                }
            }
            this.$nextTick(() => feather.replace());
        },

        async loadAssets() {
            const response = await fetch('/api/asset-entries');
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
                this.currentUsername = this.resolveCurrentUsername();
                window.PONDSEC_AI_CONTEXT = { type: 'ticket', id: this.selectedTicket.id };
                if (!this.selectedTicket.asset_ids) {
                    this.selectedTicket.asset_ids = (this.selectedTicket.assets || []).map((asset) => asset.id);
                }
                this.newComment = '';
                this.internalComment = false;
                this.newWatcher = '';
                this.ticketError = '';
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
            this.ticketError = '';
        },

        isTicketSelected(ticketId) {
            return this.selectedTicketIds.includes(String(ticketId));
        },

        toggleTicketSelection(ticketId) {
            const normalizedId = String(ticketId);
            if (this.isTicketSelected(normalizedId)) {
                this.selectedTicketIds = this.selectedTicketIds.filter((id) => id !== normalizedId);
            } else {
                this.selectedTicketIds = [...this.selectedTicketIds, normalizedId];
            }
            if (!this.selectedTicketIds.length) {
                this.mergeTargetTicketId = '';
                this.mergeTicketNote = '';
                this.mergeModalOpen = false;
                return;
            }
            if (!this.mergeTargetTicketId || !this.selectedTicketIds.includes(String(this.mergeTargetTicketId))) {
                this.mergeTargetTicketId = this.selectedTicketIds[0];
            }
        },

        clearTicketSelection() {
            this.selectedTicketIds = [];
            this.mergeTargetTicketId = '';
            this.mergeTicketNote = '';
            this.mergeModalOpen = false;
        },

        selectedTicketsForMerge() {
            return this.tickets.filter((ticket) => this.isTicketSelected(ticket.id));
        },

        openMergeModal() {
            if (this.selectedTicketIds.length < 2) return;
            this.mergeTargetTicketId = this.mergeTargetTicketId || this.selectedTicketIds[0];
            this.mergeTicketNote = '';
            this.mergeErrorMessage = '';
            this.mergeModalOpen = true;
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
            return { error: text || fallbackMessage };
        },

        formatFieldErrors(fieldErrors) {
            if (!fieldErrors || typeof fieldErrors !== 'object') {
                return '';
            }
            return Object.values(fieldErrors)
                .filter(Boolean)
                .join(' | ');
        },

        async readServerError(response, fallbackMessage) {
            const payload = await this.readErrorPayload(response, fallbackMessage);
            const fieldMessage = this.formatFieldErrors(payload.field_errors);
            return {
                ...payload,
                message: [payload.error, fieldMessage].filter(Boolean).join(' | ') || fallbackMessage
            };
        },

        setTicketNotice(message, type = 'info') {
            this.ticketNotice = { message, type };
        },

        clearTicketNotice() {
            this.ticketNotice = { message: '', type: 'info' };
        },

        cloneTicketPayload(ticket) {
            return ticket ? JSON.parse(JSON.stringify(ticket)) : null;
        },

        async performTicketDelete(ticketId) {
            const response = await fetch(`/api/tickets/${ticketId}`, {
                method: 'DELETE'
            });
            if (!response.ok) {
                const error = await this.readErrorPayload(response, 'Ticket konnte nicht gelöscht werden.');
                return { ok: false, error: error.error || 'Ticket konnte nicht gelöscht werden.' };
            }
            return { ok: true };
        },

        async deleteTicket(ticketId = null) {
            const resolvedId = ticketId || this.selectedTicket?.id;
            if (!resolvedId) return;
            const confirmed = window.confirm(`Ticket #${resolvedId} wirklich löschen? Diese Aktion kann nicht rückgängig gemacht werden.`);
            if (!confirmed) return;

            const result = await this.performTicketDelete(resolvedId);
            if (!result.ok) {
                this.setTicketNotice(result.error, 'error');
                return;
            }

            if (this.selectedTicket && String(this.selectedTicket.id) === String(resolvedId)) {
                this.closeTicket();
            }
            this.selectedTicketIds = this.selectedTicketIds.filter((id) => String(id) !== String(resolvedId));
            await this.loadTickets();
            await this.loadStats();
            this.setTicketNotice(`Ticket #${resolvedId} wurde gelöscht.`, 'success');
        },

        async deleteSelectedTickets() {
            if (!this.selectedTicketIds.length) return;
            const confirmed = window.confirm(`${this.selectedTicketIds.length} ausgewählte Tickets wirklich löschen?`);
            if (!confirmed) return;

            const idsToDelete = [...this.selectedTicketIds];
            const failedDeletes = [];
            for (const ticketId of idsToDelete) {
                const result = await this.performTicketDelete(ticketId);
                if (!result.ok) {
                    failedDeletes.push(`#${ticketId}: ${result.error}`);
                } else if (this.selectedTicket && String(this.selectedTicket.id) === String(ticketId)) {
                    this.closeTicket();
                }
            }

            this.clearTicketSelection();
            await this.loadTickets();
            await this.loadStats();

            if (failedDeletes.length) {
                this.setTicketNotice(failedDeletes.join(' | '), 'error');
                return;
            }
            this.setTicketNotice(`${idsToDelete.length} Tickets wurden gelöscht.`, 'success');
        },

        async mergeSelectedTickets() {
            if (this.selectedTicketIds.length < 2) {
                this.mergeErrorMessage = 'Bitte mindestens zwei Tickets auswählen.';
                return;
            }
            const targetTicketId = Number.parseInt(this.mergeTargetTicketId, 10);
            if (!Number.isInteger(targetTicketId)) {
                this.mergeErrorMessage = 'Bitte ein Ziel-Ticket auswählen.';
                return;
            }

            const sourceTicketIds = this.selectedTicketIds
                .filter((ticketId) => String(ticketId) !== String(targetTicketId))
                .map((ticketId) => Number.parseInt(ticketId, 10))
                .filter((ticketId) => Number.isInteger(ticketId));

            if (!sourceTicketIds.length) {
                this.mergeErrorMessage = 'Mindestens ein Quell-Ticket muss übrig bleiben.';
                return;
            }

            this.mergeErrorMessage = '';
            const response = await fetch('/api/tickets/merge', {
                method: 'POST',
                headers: { 'Content-Type': 'application/json' },
                body: JSON.stringify({
                    target_ticket_id: targetTicketId,
                    source_ticket_ids: sourceTicketIds,
                    note: this.mergeTicketNote
                })
            });

            if (!response.ok) {
                const error = await this.readErrorPayload(response, 'Tickets konnten nicht zusammengeführt werden.');
                this.mergeErrorMessage = error.error || 'Tickets konnten nicht zusammengeführt werden.';
                return;
            }

            this.mergeModalOpen = false;
            this.mergeTicketNote = '';
            this.mergeTargetTicketId = '';
            this.mergeErrorMessage = '';
            this.selectedTicketIds = [];
            await this.loadTickets();
            await this.loadStats();
            await this.selectTicket({ id: targetTicketId });
            this.setTicketNotice(`Tickets wurden in Ticket #${targetTicketId} zusammengeführt.`, 'success');
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
            if (!this.canUpdateSelectedTicket()) {
                this.setTicketNotice('Dieses Ticket kann mit deinem aktuellen Zugriff nicht bearbeitet werden.', 'error');
                return;
            }
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
                this.setTicketNotice(`Ticket #${this.selectedTicket.id} wurde aktualisiert.`, 'success');
                return;
            }
            const error = await this.readServerError(response, 'Ticket konnte nicht aktualisiert werden.');
            this.setTicketNotice(error.message, 'error');
            await this.selectTicket({ id: this.selectedTicket.id });
        },

        async createTicket() {
            this.ticketError = '';
            this.ticketFieldErrors = {};
            this.currentUsername = this.resolveCurrentUsername();
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
                const created = await response.json();
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
                    asset_ids: [],
                    requester_name: this.currentUsername
                };
                await this.loadTickets();
                await this.loadStats();
                if (created?.id) {
                    await this.selectTicket({ id: created.id });
                }
                this.setTicketNotice(created?.id ? `Ticket #${created.id} wurde erstellt.` : 'Ticket wurde erstellt.', 'success');
            } else {
                const error = await this.readServerError(response, 'Ticket konnte nicht erstellt werden.');
                this.ticketFieldErrors = error.field_errors || {};
                this.ticketError = error.message;
            }
        },

        async addComment() {
            if (!this.newComment || !this.selectedTicket) return;
            if (!this.canCommentSelectedTicket()) {
                this.setTicketNotice('Kommentare sind für dieses Ticket mit deinem Zugriff nicht erlaubt.', 'error');
                return;
            }
            const response = await fetch(`/api/tickets/${this.selectedTicket.id}/comments`, {
                method: 'POST',
                headers: { 'Content-Type': 'application/json' },
                body: JSON.stringify({ body: this.newComment, is_internal: this.internalComment })
            });
            if (response.ok) {
                await this.selectTicket(this.selectedTicket);
                await this.loadTickets();
            } else {
                const error = await this.readServerError(response, 'Kommentar konnte nicht gespeichert werden.');
                this.setTicketNotice(error.message, 'error');
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
            } else {
                const error = await this.readServerError(response, 'Beobachter konnte nicht hinzugefügt werden.');
                this.setTicketNotice(error.message, 'error');
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
