document.addEventListener('alpine:init', () => {
    Alpine.data('procurementApp', () => ({
        activeTab: 'vendors',
        listSearch:'',listPage:1,perPage:10,selectedRecord:null,workspaceError:'',saving:false,modalSnapshots:{},orderLoaded:true,
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
            for(const name of ['loadVendors','loadContracts','loadOrders','refreshRenewals','fetchOrder','saveVendor','saveContract','saveOrder','deleteVendor','deleteContract','deleteOrder']) {
                const operation=this[name].bind(this);
                this[name]=async (...args)=>{
                    const write=name.startsWith('save') || name.startsWith('delete');
                    if(write && this.saving)return;if(write)this.saving=true;
                    this.workspaceError='';
                    try{return await operation(...args);}catch(error){this.workspaceError=error.message || 'Verbindung fehlgeschlagen. Ihre Eingaben bleiben erhalten.';}
                    finally{if(write)this.saving=false;}
                };
            }
            window.addEventListener('beforeunload',event=>{if(['Vendor','Contract','Order'].some(kind=>this[kind.toLowerCase()+'ModalOpen'] && this.formDirty(kind))){event.preventDefault();event.returnValue='';}});
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

        formDirty(kind){return this.modalSnapshots[kind]!==undefined && this.modalSnapshots[kind]!==JSON.stringify(this['current'+kind]);},
        rememberForm(kind){this.modalSnapshots[kind]=JSON.stringify(this['current'+kind]);},
        async request(url,options={}) {
            const response=await fetch(url,options);
            if(response.redirected)throw new Error(uiText('Die Sitzung ist abgelaufen. Bitte erneut anmelden.'));
            if(!response.ok){const data=await response.json().catch(()=>({}));throw new Error(data.error || uiText('Die Änderung konnte nicht gespeichert werden. Ihre Eingaben bleiben erhalten.'));}
            return response;
        },
        filteredRows(tab=this.activeTab) {
            const rows=tab==='vendors' ? this.vendors : tab==='contracts' ? this.contracts : this.purchaseOrders;
            const query=this.listSearch.trim().toLocaleLowerCase('de');
            return query ? rows.filter(row=>Object.values(row).filter(value=>typeof value==='string' || typeof value==='number').join(' ').toLocaleLowerCase('de').includes(query)) : rows;
        },
        listPages(){return Math.max(1,Math.ceil(this.filteredRows().length/this.perPage));},
        pageRows(tab=this.activeTab){const page=Math.min(this.listPage,Math.max(1,Math.ceil(this.filteredRows(tab).length/this.perPage)));return this.filteredRows(tab).slice((page-1)*this.perPage,page*this.perPage);},
        showRecord(kind,data){this.selectedRecord={kind,data};},
        editSelected(){const {kind,data}=this.selectedRecord;if(kind==='vendor')this.openVendorModal(data);else if(kind==='contract')this.openContractModal(data);else this.openOrderModal(data);},
        recordFields(){
            if(!this.selectedRecord)return [];
            const {kind,data}=this.selectedRecord;
            const fields=kind==='vendor' ? {vendor_type:uiText('Typ'),contact_name:uiText('Kontakt'),email:uiText('E-Mail'),phone:uiText('Telefon'),website:'Website',address:uiText('Adresse'),rating:'Bewertung',notes:uiText('Notizen')} : kind==='contract' ? {vendor_name:uiText('Lieferant'),contract_type:uiText('Typ'),status:'Status',start_date:'Start',end_date:uiText('Ende'),renewal_type:uiText('Verlängerung'),renewal_notice_days:uiText('Kündigungsfrist in Tagen'),cost:uiText('Kosten'),currency:uiText('Währung'),owner:uiText('Verantwortlich'),service_level:uiText('Service-Level'),notes:uiText('Notizen')} : {vendor_name:uiText('Lieferant'),status:'Status',order_date:'Bestellt am',expected_date:'Erwartete Lieferung',received_date:'Erhalten am',requester:uiText('Angefragt von'),approver:'Freigabe',cost_center:uiText('Kostenstelle'),tax:uiText('Steuer'),total:uiText('Gesamt'),currency:uiText('Währung'),item_count:uiText('Positionen'),notes:uiText('Notizen')};
            return Object.entries(fields).map(([key,label])=>[label,data[key] ?? uiText('Nicht erfasst')]);
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
            const response = await this.request('/api/vendors');
            if (response.ok) {
                this.vendors = await response.json();
            }
        },

        async loadContracts() {
            const response = await this.request('/api/contracts');
            if (response.ok) {
                this.contracts = await response.json();
            }
        },

        async loadOrders() {
            const response = await this.request('/api/purchase-orders');
            if (response.ok) {
                this.purchaseOrders = await response.json();
            }
        },

        async refreshRenewals() {
            const response = await this.request('/api/procurement/renewals');
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
            this.rememberForm('Vendor');
        },

        closeVendorModal(force=false) {
            if(!force && (this.saving || (this.formDirty('Vendor') && !confirm(uiText('Nicht gespeicherte Änderungen verwerfen?')))))return;
            this.vendorModalOpen = false;
        },

        async saveVendor() {
            const payload = { ...this.currentVendor };
            let response;
            if (this.editingVendor) {
                response = await this.request(`/api/vendors/${this.currentVendor.id}`, {
                    method: 'PUT',
                    headers: { 'Content-Type': 'application/json' },
                    body: JSON.stringify(payload)
                });
            } else {
                response = await this.request('/api/vendors', {
                    method: 'POST',
                    headers: { 'Content-Type': 'application/json' },
                    body: JSON.stringify(payload)
                });
            }
            if (response.ok) {
                await this.loadVendors();
                this.updateOverview();
                this.closeVendorModal(true);
            } else {
                const error = await response.json();
                alert(error.error || uiText('Lieferant konnte nicht gespeichert werden'));
            }
        },

        async deleteVendor(id) {
            if (!confirm(uiText('Lieferant wirklich loeschen?'))) return;
            const response = await this.request(`/api/vendors/${id}`, { method: 'DELETE' });
            if (response.ok) {
                await this.loadVendors();
                this.updateOverview();
            } else {
                const error = await response.json();
                alert(error.error || uiText('Lieferant konnte nicht geloescht werden'));
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
            this.rememberForm('Contract');
        },

        closeContractModal(force=false) {
            if(!force && (this.saving || (this.formDirty('Contract') && !confirm(uiText('Nicht gespeicherte Änderungen verwerfen?')))))return;
            this.contractModalOpen = false;
        },

        async saveContract() {
            const payload = { ...this.currentContract };
            let response;
            if (this.editingContract) {
                response = await this.request(`/api/contracts/${this.currentContract.id}`, {
                    method: 'PUT',
                    headers: { 'Content-Type': 'application/json' },
                    body: JSON.stringify(payload)
                });
            } else {
                response = await this.request('/api/contracts', {
                    method: 'POST',
                    headers: { 'Content-Type': 'application/json' },
                    body: JSON.stringify(payload)
                });
            }
            if (response.ok) {
                await this.loadContracts();
                this.updateOverview();
                await this.refreshRenewals();
                this.closeContractModal(true);
            } else {
                const error = await response.json();
                alert(error.error || uiText('Vertrag konnte nicht gespeichert werden'));
            }
        },

        async deleteContract(id) {
            if (!confirm(uiText('Vertrag wirklich loeschen?'))) return;
            const response = await this.request(`/api/contracts/${id}`, { method: 'DELETE' });
            if (response.ok) {
                await this.loadContracts();
                this.updateOverview();
                await this.refreshRenewals();
            } else {
                const error = await response.json();
                alert(error.error || uiText('Vertrag konnte nicht geloescht werden'));
            }
        },

        async openOrderModal(order = null) {
            this.orderLoaded=!order;
            this.editingOrder = !!order;
            this.orderModalOpen = true;
            if (order) {
                await this.fetchOrder(order.id);
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
            this.rememberForm('Order');
        },

        closeOrderModal(force=false) {
            if(!force && (this.saving || (this.formDirty('Order') && !confirm(uiText('Nicht gespeicherte Änderungen verwerfen?')))))return;
            this.orderModalOpen = false;
        },

        async fetchOrder(id) {
            const response = await this.request(`/api/purchase-orders/${id}`);
            if (response.ok) {
                const data = await response.json();
                this.orderLoaded=true;
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
            if(!this.orderLoaded)throw new Error(uiText('Die Bestellung konnte nicht geladen werden. Bitte erneut öffnen.'));
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
                response = await this.request(`/api/purchase-orders/${this.currentOrder.id}`, {
                    method: 'PUT',
                    headers: { 'Content-Type': 'application/json' },
                    body: JSON.stringify(payload)
                });
            } else {
                response = await this.request('/api/purchase-orders', {
                    method: 'POST',
                    headers: { 'Content-Type': 'application/json' },
                    body: JSON.stringify(payload)
                });
            }
            if (response.ok) {
                await this.loadOrders();
                this.updateOverview();
                this.closeOrderModal(true);
            } else {
                const error = await response.json();
                alert(error.error || uiText('Bestellung konnte nicht gespeichert werden'));
            }
        },

        async deleteOrder(id) {
            if (!confirm(uiText('Bestellung wirklich loeschen?'))) return;
            const response = await this.request(`/api/purchase-orders/${id}`, { method: 'DELETE' });
            if (response.ok) {
                await this.loadOrders();
                this.updateOverview();
            } else {
                const error = await response.json();
                alert(error.error || uiText('Bestellung konnte nicht geloescht werden'));
            }
        }
    }));
});
