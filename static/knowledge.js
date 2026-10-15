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
        saving:false,entrySnapshot:'',categorySnapshot:'',
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
                await this.selectEntry({ id: entryId },false);
            }
            window.addEventListener('beforeunload',event=>{if(this.saving || this.entryModalOpen && JSON.stringify(this.entryForm)!==this.entrySnapshot || this.categoryModalOpen && JSON.stringify(this.categoryForm)!==this.categorySnapshot){event.preventDefault();event.returnValue='';}});
            window.addEventListener('popstate',()=>{const id=new URLSearchParams(location.search).get('entry_id');if(id)this.selectEntry({id},false);else this.selectedEntry=null;});
            this.$nextTick(() => feather.replace());
        },

        formatDate(value) { const date=new Date(String(value || '').replace(' ','T'));return Number.isNaN(date.valueOf()) ? '—' : date.toLocaleDateString('de-DE'); },

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

        async selectEntry(entry,push=true) {
            if (!/^[1-9]\d*$/.test(String(entry.id))) return;
            try {
                const response=await fetch(`/api/knowledge/entries/${entry.id}`);
                if (!response.ok || response.redirected) throw new Error('Der Artikel konnte nicht geöffnet werden. Bitte erneut versuchen.');
                this.selectedEntry=await response.json();
                if (push) {const url=new URL(location.href);url.searchParams.set('entry_id',entry.id);history.pushState({},'',url);}
                this.$nextTick(()=>feather.replace());
            } catch(error) {this.listError=error.message || 'Verbindung fehlgeschlagen.';}
        },

        clearSelectedEntry() {
            if (!this.selectedEntry) return;
            this.selectedEntry=null;
            const url=new URL(location.href);url.searchParams.delete('entry_id');history.pushState({},'',url);
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
            this.entrySnapshot=JSON.stringify(this.entryForm);
            this.entryModalOpen = true;
        },

        closeEntryModal() {
            if(this.saving || JSON.stringify(this.entryForm)!==this.entrySnapshot && !confirm('Ungespeicherte Eingaben verwerfen?'))return;
            this.entryModalOpen = false;
        },

        async write(url,method,payload) {
            const controller=new AbortController(),timer=setTimeout(()=>controller.abort(),15000);
            try {
                const response=await fetch(url,{method,headers:{'Content-Type':'application/json'},body:JSON.stringify(payload),signal:controller.signal});
                if (response.redirected) throw new Error('Die Sitzung ist abgelaufen. Bitte erneut anmelden.');
                const data=await response.json();
                if (!response.ok) throw new Error(data.error || 'Speichern fehlgeschlagen. Ihre Eingaben bleiben erhalten.');
                return data;
            } finally {clearTimeout(timer);}
        },

        async saveEntry() {
            if(this.saving)return;
            this.entryError='';
            if(!this.entryForm.title.trim()){this.entryError='Bitte einen Titel eingeben.';return;}
            this.saving=true;
            try {
                await this.write(this.entryForm.id ? `/api/knowledge/entries/${this.entryForm.id}` : '/api/knowledge/entries',this.entryForm.id ? 'PUT':'POST',{
                    title:this.entryForm.title,summary:this.entryForm.summary,content:this.entryForm.content,
                    category_id:this.entryForm.category_id || null,related_ticket_id:this.entryForm.related_ticket_id || null});
                await this.loadEntries();
                if(this.entryForm.id)await this.selectEntry({id:this.entryForm.id},false);
                this.entryModalOpen=false;
            } catch(error) {this.entryError=error.name==='AbortError' ? 'Zeitüberschreitung. Prüfen Sie vor erneutem Speichern, ob der Artikel bereits gespeichert wurde.' : error.message || 'Verbindung fehlgeschlagen. Ihre Eingaben bleiben erhalten.';}
            finally {this.saving=false;}
        },

        async deleteEntry(entry) {
            if (!entry || !confirm('Diesen Wissenseintrag wirklich löschen?')) return;
            const response = await fetch(`/api/knowledge/entries/${entry.id}`, { method: 'DELETE' });
            if (response.ok) {
                if (this.selectedEntry && this.selectedEntry.id === entry.id) {
                    this.clearSelectedEntry();
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
            this.categorySnapshot=JSON.stringify(this.categoryForm);
            this.categoryModalOpen = true;
        },

        closeCategoryModal() {
            if(this.saving || JSON.stringify(this.categoryForm)!==this.categorySnapshot && !confirm('Ungespeicherte Eingaben verwerfen?'))return;
            this.categoryModalOpen = false;
        },

        async saveCategory() {
            if(this.saving)return;
            this.categoryError='';
            if(!this.categoryForm.name.trim()){this.categoryError='Bitte einen Namen eingeben.';return;}
            this.saving=true;
            try {
                await this.write(this.categoryForm.id ? `/api/knowledge/categories/${this.categoryForm.id}` : '/api/knowledge/categories',this.categoryForm.id ? 'PUT':'POST',{
                    name:this.categoryForm.name,description:this.categoryForm.description});
                await this.loadCategories();await this.loadEntries();
                if(this.selectedEntry)await this.selectEntry({id:this.selectedEntry.id},false);
                this.categoryModalOpen=false;
            } catch(error) {this.categoryError=error.name==='AbortError' ? 'Zeitüberschreitung. Bitte prüfen Sie, ob die Kategorie bereits gespeichert wurde.' : error.message || 'Verbindung fehlgeschlagen. Ihre Eingaben bleiben erhalten.';}
            finally {this.saving=false;}
        }
    }));
});
