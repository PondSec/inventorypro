document.addEventListener('alpine:init', () => {
    Alpine.data('ticketAdmin', () => ({
        section: window.ticketAdminSection || 'general',
        userPermissions: window.inventoryPermissions || [],
        isSuperuser: window.inventoryIsSuperuser || false,
        categories: [],
        alerts: [],
        loading: false,
        saving: false,
        error: '',
        categoryModalOpen: false,
        alertModalOpen: false,
        categoryForm: { id: null, name: '', description: '', color: '#2563eb', sla_hours: 72, is_default: false },
        alertForm: { name: '', event_type: 'created', status_match: '', priority_match: '', category_id: '', recipient_emails: '', is_enabled: true },
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
        toasts: [],
        toastSequence: 0,
        iconRefreshTimer: null,
        navigation: [
            { key: 'general', label: uiText('Übersicht'), icon: 'layout', description: uiText('Aktive Konfiguration und verbindliche Workflow-Regeln.'), enabled: true, available: true },
            { key: 'categories', label: uiText('Kategorien'), icon: 'folder', description: uiText('Kategorien, Beschreibungen und Standard-SLAs.'), enabled: true, available: true },
            { key: 'workflows', label: uiText('Workflows & Reviews'), icon: 'git-pull-request', description: uiText('Statusübergänge und verpflichtende Change-Abnahmen.'), enabled: true, available: true },
            { key: 'priorities', label: uiText('Prioritäten'), icon: 'alert-circle', description: uiText('Verbindliche Bedeutung und Bearbeitungsreihenfolge.'), enabled: true, available: true },
            { key: 'slas', label: 'SLA-Regeln', icon: 'clock', description: uiText('Lösungsziele der aktiven Ticketkategorien.'), enabled: true, available: true },
            { key: 'automations', label: uiText('Automationen'), icon: 'zap', description: uiText('Ereignisbasierte Alerts und Aktionen.'), enabled: true, available: true },
            { key: 'email', label: uiText('E-Mail'), icon: 'mail', description: uiText('SMTP-Versand und Absenderkonfiguration.'), enabled: true, available: true },
            { key: 'permissions', label: uiText('Berechtigungen'), icon: 'shield', description: uiText('Rollen, Benutzer und Ticketrechte verwalten.'), enabled: true, available: true }
        ],

        async init() {
            await this.loadSection();
            this.refreshIcons();
        },

        get currentSection() {
            return this.navigation.find(item => item.key === this.section) || this.navigation[0];
        },

        can(permission) {
            return this.isSuperuser || this.userPermissions.includes(permission);
        },

        async api(url, options = {}) {
            const response = await fetch(url, options);
            const payload = await response.json().catch(() => null);
            if (!response.ok) throw new Error(payload?.error || uiText("Anfrage fehlgeschlagen ({0})", [response.status]));
            return payload;
        },

        async selectSection(event, item) {
            event.preventDefault();
            this.section = item.key;
            history.pushState({}, '', `/admin/tickets/${item.key}`);
            await this.loadSection();
            this.refreshIcons();
        },

        async loadSection() {
            this.loading = true;
            this.error = '';
            try {
                if (['categories', 'slas'].includes(this.section) && this.can('ticket_categories.manage')) await this.loadCategories();
                if (this.section === 'automations' && this.can('ticket_alerts.manage')) await this.loadAlerts();
                if (this.section === 'email' && this.can('notifications.manage')) await this.loadNotificationSettings();
            } catch (error) {
                this.error = error.message;
            } finally {
                this.loading = false;
                this.refreshIcons();
            }
        },

        async loadCategories() {
            this.categories = await this.api('/api/ticket-categories');
        },

        openCategory(category = null) {
            this.categoryForm = category
                ? {
                    id: category.id,
                    name: category.name,
                    description: category.description || '',
                    color: category.color || '#2563eb',
                    sla_hours: category.sla_hours || 72,
                    is_default: Boolean(category.is_default)
                }
                : { id: null, name: '', description: '', color: '#2563eb', sla_hours: 72, is_default: false };
            this.categoryModalOpen = true;
            this.refreshIcons();
        },

        async saveCategory() {
            const form = this.categoryForm;
            const url = form.id ? `/api/ticket-categories/${form.id}` : '/api/ticket-categories';
            try {
                await this.api(url, {
                    method: form.id ? 'PUT' : 'POST',
                    headers: { 'Content-Type': 'application/json' },
                    body: JSON.stringify(form)
                });
                this.categoryModalOpen = false;
                await this.loadCategories();
                this.showToast(form.id ? uiText('Kategorie aktualisiert.') : uiText('Kategorie erstellt.'));
            } catch (error) {
                this.showToast(error.message, 'error');
            }
        },

        async deleteCategory(category) {
            if (!window.confirm(uiText("Kategorie „{0}“ löschen? Verknüpfte Tickets behalten ihre Daten und werden ohne Kategorie geführt.", [category.name]))) return;
            try {
                await this.api(`/api/ticket-categories/${category.id}`, { method: 'DELETE' });
                await this.loadCategories();
                this.showToast(uiText('Kategorie gelöscht.'));
            } catch (error) {
                this.showToast(error.message, 'error');
            }
        },

        async loadAlerts() {
            this.alerts = await this.api('/api/ticket-alerts');
        },

        openAlert() {
            this.alertForm = { name: '', event_type: 'created', status_match: '', priority_match: '', category_id: '', recipient_emails: '', is_enabled: true };
            this.alertModalOpen = true;
            this.refreshIcons();
        },

        async saveAlert() {
            try {
                await this.api('/api/ticket-alerts', {
                    method: 'POST',
                    headers: { 'Content-Type': 'application/json' },
                    body: JSON.stringify(this.alertForm)
                });
                this.alertModalOpen = false;
                await this.loadAlerts();
                this.showToast(uiText('Alert erstellt.'));
            } catch (error) {
                this.showToast(error.message, 'error');
            }
        },

        async deleteAlert(alert) {
            if (!window.confirm(uiText("Alert „{0}“ löschen?", [alert.name]))) return;
            try {
                await this.api(`/api/ticket-alerts/${alert.id}`, { method: 'DELETE' });
                await this.loadAlerts();
                this.showToast(uiText('Alert gelöscht.'));
            } catch (error) {
                this.showToast(error.message, 'error');
            }
        },

        eventLabel(value) {
            return {
                created: uiText('Ticket erstellt'),
                updated: uiText('Ticket aktualisiert'),
                commented: uiText('Kommentar hinzugefügt'),
                status_changed: uiText('Status geändert')
            }[value] || value;
        },

        alertConditions(alert) {
            const conditions = [];
            if (alert.status_match) conditions.push(`Status: ${alert.status_match}`);
            if (alert.priority_match) conditions.push(uiText("Priorität: {0}", [alert.priority_match]));
            return conditions.join(' · ') || uiText('Ohne Bedingung');
        },

        async loadNotificationSettings() {
            const settings = await this.api('/api/notifications/settings');
            this.notificationSettings = { ...this.notificationSettings, ...settings, smtp_password: '' };
        },

        async saveNotificationSettings() {
            this.saving = true;
            try {
                const settings = await this.api('/api/notifications/settings', {
                    method: 'POST',
                    headers: { 'Content-Type': 'application/json' },
                    body: JSON.stringify(this.notificationSettings)
                });
                this.notificationSettings = { ...this.notificationSettings, ...settings, smtp_password: '' };
                this.showToast(uiText('E-Mail-Einstellungen gespeichert.'));
            } catch (error) {
                this.showToast(error.message, 'error');
            } finally {
                this.saving = false;
            }
        },

        async sendTestNotification() {
            const recipients = this.notificationSettings.default_recipients || this.notificationSettings.smtp_from;
            if (!recipients) {
                this.showToast(uiText('Bitte zuerst Standardempfänger oder Absenderadresse hinterlegen.'), 'error');
                return;
            }
            try {
                await this.api('/api/notifications/test', {
                    method: 'POST',
                    headers: { 'Content-Type': 'application/json' },
                    body: JSON.stringify({ recipients })
                });
                this.showToast(uiText('Test-E-Mail versendet.'));
            } catch (error) {
                this.showToast(error.message, 'error');
            }
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
                this.$nextTick(() => window.InventoryRefreshIcons?.());
            }, 16);
        }
    }));
});
