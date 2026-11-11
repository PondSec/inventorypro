document.addEventListener('alpine:init', () => {
    Alpine.data('procurementApp', () => ({
        activeTab: 'vendors',
        vendors: [],
        contracts: [],
        purchaseOrders: [],
        renewals: {
            days: 90,
            contracts: [],
            warranties: []
        },
        overview: {
            vendors: 0,
            contracts: 0,
            orders: 0,
            renewals: 0
        },
        vendorModalOpen: false,
        contractModalOpen: false,
        orderModalOpen: false,
        editingVendor: false,
        editingContract: false,
        editingOrder: false,
        currentVendor: {
            id: null,
            name: '',
            vendor_type: '',
            contact_name: '',
            email: '',
            phone: '',
            website: '',
            address: '',
            rating: 3,
            notes: ''
        },
        currentContract: {
            id: null,
            name: '',
            vendor_id: '',
            contract_type: '',
            status: 'active',
            start_date: '',
            end_date: '',
            renewal_type: 'manual',
            renewal_notice_days: 30,
            cost: '',
            currency: 'EUR',
            owner: '',
            service_level: '',
            notes: ''
        },
        currentOrder: {
            id: null,
            po_number: '',
            vendor_id: '',
            status: 'draft',
            order_date: '',
            expected_date: '',
            received_date: '',
            requester: '',
            approver: '',
            cost_center: '',
            tax: '',
            currency: 'EUR',
            notes: '',
            items: []
        },

        async init() {
            await this.loadVendors();
            await this.loadContracts();
            await this.loadOrders();
            await this.refreshRenewals();
            this.updateOverview();
            this.$nextTick(() => {
                if (window.feather) {
                    feather.replace();
                }
            });
        },

        can(permissionKey) {
            return window.inventoryIsSuperuser || (window.inventoryPermissions || []).includes(permissionKey);
        },

        updateOverview() {
            this.overview.vendors = this.vendors.length;
            this.overview.contracts = this.contracts.length;
            this.overview.orders = this.purchaseOrders.length;
            this.overview.renewals = (this.renewals.contracts || []).length + (this.renewals.warranties || []).length;
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

        async loadVendors() {
            const response = await fetch('/api/vendors');
            if (response.ok) {
                this.vendors = await response.json();
            }
        },

        async loadContracts() {
            const response = await fetch('/api/contracts');
            if (response.ok) {
                this.contracts = await response.json();
            }
        },

        async loadOrders() {
            const response = await fetch('/api/purchase-orders');
            if (response.ok) {
                this.purchaseOrders = await response.json();
            }
        },

        async refreshRenewals() {
            const response = await fetch('/api/procurement/renewals');
            if (response.ok) {
                this.renewals = await response.json();
                this.updateOverview();
            }
        },

        openVendorModal(vendor = null) {
            this.editingVendor = !!vendor;
            this.vendorModalOpen = true;
            this.currentVendor = vendor ? { ...vendor } : {
                id: null,
                name: '',
                vendor_type: '',
                contact_name: '',
                email: '',
                phone: '',
                website: '',
                address: '',
                rating: 3,
                notes: ''
            };
        },

        closeVendorModal() {
            this.vendorModalOpen = false;
        },

        async saveVendor() {
            const payload = { ...this.currentVendor };
            let response;
            if (this.editingVendor) {
                response = await fetch(`/api/vendors/${this.currentVendor.id}`, {
                    method: 'PUT',
                    headers: { 'Content-Type': 'application/json' },
                    body: JSON.stringify(payload)
                });
            } else {
                response = await fetch('/api/vendors', {
                    method: 'POST',
                    headers: { 'Content-Type': 'application/json' },
                    body: JSON.stringify(payload)
                });
            }
            if (response.ok) {
                await this.loadVendors();
                this.updateOverview();
                this.closeVendorModal();
            } else {
                const error = await response.json();
                alert(error.error || 'Lieferant konnte nicht gespeichert werden');
            }
        },

        async deleteVendor(id) {
            if (!confirm('Lieferant wirklich loeschen?')) return;
            const response = await fetch(`/api/vendors/${id}`, { method: 'DELETE' });
            if (response.ok) {
                await this.loadVendors();
                this.updateOverview();
            } else {
                const error = await response.json();
                alert(error.error || 'Lieferant konnte nicht geloescht werden');
            }
        },

        openContractModal(contract = null) {
            this.editingContract = !!contract;
            this.contractModalOpen = true;
            this.currentContract = contract ? { ...contract } : {
                id: null,
                name: '',
                vendor_id: '',
                contract_type: '',
                status: 'active',
                start_date: '',
                end_date: '',
                renewal_type: 'manual',
                renewal_notice_days: 30,
                cost: '',
                currency: 'EUR',
                owner: '',
                service_level: '',
                notes: ''
            };
        },

        closeContractModal() {
            this.contractModalOpen = false;
        },

        async saveContract() {
            const payload = { ...this.currentContract };
            let response;
            if (this.editingContract) {
                response = await fetch(`/api/contracts/${this.currentContract.id}`, {
                    method: 'PUT',
                    headers: { 'Content-Type': 'application/json' },
                    body: JSON.stringify(payload)
                });
            } else {
                response = await fetch('/api/contracts', {
                    method: 'POST',
                    headers: { 'Content-Type': 'application/json' },
                    body: JSON.stringify(payload)
                });
            }
            if (response.ok) {
                await this.loadContracts();
                this.updateOverview();
                await this.refreshRenewals();
                this.closeContractModal();
            } else {
                const error = await response.json();
                alert(error.error || 'Vertrag konnte nicht gespeichert werden');
            }
        },

        async deleteContract(id) {
            if (!confirm('Vertrag wirklich loeschen?')) return;
            const response = await fetch(`/api/contracts/${id}`, { method: 'DELETE' });
            if (response.ok) {
                await this.loadContracts();
                this.updateOverview();
                await this.refreshRenewals();
            } else {
                const error = await response.json();
                alert(error.error || 'Vertrag konnte nicht geloescht werden');
            }
        },

        openOrderModal(order = null) {
            this.editingOrder = !!order;
            this.orderModalOpen = true;
            if (order) {
                this.fetchOrder(order.id);
            } else {
                this.currentOrder = {
                    id: null,
                    po_number: '',
                    vendor_id: '',
                    status: 'draft',
                    order_date: '',
                    expected_date: '',
                    received_date: '',
                    requester: '',
                    approver: '',
                    cost_center: '',
                    tax: '',
                    currency: 'EUR',
                    notes: '',
                    items: []
                };
            }
        },

        closeOrderModal() {
            this.orderModalOpen = false;
        },

        async fetchOrder(id) {
            const response = await fetch(`/api/purchase-orders/${id}`);
            if (response.ok) {
                const data = await response.json();
                this.currentOrder = {
                    id: data.id,
                    po_number: data.po_number || '',
                    vendor_id: data.vendor_id || '',
                    status: data.status || 'draft',
                    order_date: data.order_date || '',
                    expected_date: data.expected_date || '',
                    received_date: data.received_date || '',
                    requester: data.requester || '',
                    approver: data.approver || '',
                    cost_center: data.cost_center || '',
                    tax: data.tax ?? '',
                    currency: data.currency || 'EUR',
                    notes: data.notes || '',
                    items: (data.items || []).map(item => ({
                        id: item.id || crypto.randomUUID(),
                        item_type: item.item_type || 'asset',
                        item_name: item.item_name || '',
                        quantity: item.quantity || 1,
                        unit_cost: item.unit_cost || ''
                    }))
                };
            }
        },

        addOrderItem() {
            this.currentOrder.items.push({
                id: crypto.randomUUID(),
                item_type: 'asset',
                item_name: '',
                quantity: 1,
                unit_cost: ''
            });
        },

        removeOrderItem(id) {
            this.currentOrder.items = this.currentOrder.items.filter(item => item.id !== id);
        },

        async saveOrder() {
            const payload = {
                ...this.currentOrder,
                items: this.currentOrder.items.map(item => ({
                    item_type: item.item_type,
                    item_name: item.item_name,
                    quantity: item.quantity,
                    unit_cost: item.unit_cost
                }))
            };
            let response;
            if (this.editingOrder) {
                response = await fetch(`/api/purchase-orders/${this.currentOrder.id}`, {
                    method: 'PUT',
                    headers: { 'Content-Type': 'application/json' },
                    body: JSON.stringify(payload)
                });
            } else {
                response = await fetch('/api/purchase-orders', {
                    method: 'POST',
                    headers: { 'Content-Type': 'application/json' },
                    body: JSON.stringify(payload)
                });
            }
            if (response.ok) {
                await this.loadOrders();
                this.updateOverview();
                this.closeOrderModal();
            } else {
                const error = await response.json();
                alert(error.error || 'Bestellung konnte nicht gespeichert werden');
            }
        },

        async deleteOrder(id) {
            if (!confirm('Bestellung wirklich loeschen?')) return;
            const response = await fetch(`/api/purchase-orders/${id}`, { method: 'DELETE' });
            if (response.ok) {
                await this.loadOrders();
                this.updateOverview();
            } else {
                const error = await response.json();
                alert(error.error || 'Bestellung konnte nicht geloescht werden');
            }
        }
    }));
});
