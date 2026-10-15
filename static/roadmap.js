document.addEventListener('alpine:init', () => {
    Alpine.data('roadmapApp', () => ({
        roadmaps: [],
        selectedRoadmap: null,
        workspaceError:'',workspaceBusy:false,requestSequence:0,
        userPermissions: window.inventoryPermissions || [],
        isSuperuser: window.inventoryIsSuperuser || false,
        filters: {
            status: '',
            search: '',
            mine: false,
            owner: '',
            month: ''
        },
        roadmapStatuses: ['planned', 'in_progress', 'blocked', 'done'],
        roadmapStatusLabels: {
            planned: 'Geplant',
            in_progress: 'In Arbeit',
            blocked: 'Blockiert',
            done: 'Erledigt'
        },
        overview: {
            planned: 0,
            in_progress: 0,
            blocked: 0,
            done: 0
        },
        roadmapModalOpen: false,
        roadmapError: '',
        stepFormOpen: false,
        newRoadmap: {
            title: '',
            objective: '',
            status: 'planned',
            owner: '',
            start_date: '',
            target_date: '',
            ticket_id: ''
        },
        newStep: {
            title: '',
            description: '',
            status: 'planned',
            owner: '',
            due_date: ''
        },
        preselectedTicketId: null,

        async init() {
            // Every existing operation retains its API contract; failures become
            // visible and never silently discard the current form values.
            for (const name of ['loadRoadmaps','selectRoadmap','saveRoadmap','addStep','updateStep','deleteStep','createRoadmap']) {
                const operation=this[name].bind(this);
                this[name]=async (...args)=>{
                    const writing=!['loadRoadmaps','selectRoadmap'].includes(name);
                    if(writing && this.workspaceBusy)return;
                    if(writing)this.workspaceBusy=true;
                    this.workspaceError='';
                    try {return await operation(...args);}
                    catch(error){this.workspaceError=error.message || 'Verbindung fehlgeschlagen. Ihre Eingaben bleiben erhalten.';if(this.roadmapModalOpen)this.roadmapError=this.workspaceError;}
                    finally {if(writing)this.workspaceBusy=false;}
                };
            }
            const params = new URLSearchParams(window.location.search);
            this.preselectedTicketId = params.get('ticket_id');
            await this.loadRoadmaps();
            const roadmapId=params.get('roadmap_id');
            if (roadmapId && /^[1-9]\d*$/.test(roadmapId)) await this.selectRoadmap({id:roadmapId});
            if (this.preselectedTicketId) {
                const match = this.roadmaps.find((roadmap) => String(roadmap.ticket_id) === String(this.preselectedTicketId));
                if (match) {
                    await this.selectRoadmap(match);
                }
            }
            this.refreshIcons();
        },

        async request(url,options={}) {
            const response=await fetch(url,options);
            if(response.redirected)throw new Error('Die Sitzung ist abgelaufen. Bitte erneut anmelden.');
            if(!response.ok){const data=await response.json().catch(()=>({}));throw new Error(data.error || 'Die Änderung konnte nicht gespeichert werden. Ihre Eingaben bleiben erhalten.');}
            return response;
        },

        can(permissionKey) {
            return this.isSuperuser || this.userPermissions.includes(permissionKey);
        },

        openNewRoadmap() {
            this.roadmapError = '';
            this.roadmapModalOpen = true;
        },

        toggleStepForm() {
            this.stepFormOpen = !this.stepFormOpen;
        },

        async loadRoadmaps() {
            const sequence=++this.requestSequence;
            const params = new URLSearchParams();
            if (this.filters.status) params.append('status', this.filters.status);
            if (this.filters.search) params.append('search', this.filters.search);
            if (this.filters.mine) params.append('mine', '1');
            if (this.filters.owner) params.append('owner', this.filters.owner);
            if (this.filters.month) params.append('month', this.filters.month);
            if (this.preselectedTicketId) params.append('ticket_id', this.preselectedTicketId);

            const response = await this.request(`/api/roadmaps?${params.toString()}`);
            if (response.ok) {
                const result=await response.json();
                if(sequence!==this.requestSequence)return;
                this.roadmaps = result;
                this.updateOverview();
            }
            this.refreshIcons();
        },

        applyFilters() {
            this.loadRoadmaps();
        },

        updateOverview() {
            const counts = { planned: 0, in_progress: 0, blocked: 0, done: 0 };
            this.roadmaps.forEach((roadmap) => {
                if (counts[roadmap.status] !== undefined) {
                    counts[roadmap.status] += 1;
                }
            });
            this.overview = counts;
        },

        async selectRoadmap(roadmap) {
            const response = await this.request(`/api/roadmaps/${roadmap.id}`);
            if (response.ok) {
                const roadmapData = await response.json();
                if (Array.isArray(roadmapData.steps)) {
                    roadmapData.steps = roadmapData.steps.map((step) => ({
                        ...step,
                        ui_status: step.status
                    }));
                }
                this.selectedRoadmap = roadmapData;
                this.stepFormOpen = false;
            }
            this.refreshIcons();
        },

        closeRoadmap() {
            this.selectedRoadmap = null;
        },

        stepsByStatus(status) {
            if (!this.selectedRoadmap || !this.selectedRoadmap.steps) return [];
            return this.selectedRoadmap.steps.filter((step) => step.status === status);
        },

        async saveRoadmap() {
            if (!this.selectedRoadmap) return;
            const payload = {
                title: this.selectedRoadmap.title,
                objective: this.selectedRoadmap.objective,
                status: this.selectedRoadmap.status,
                owner: this.selectedRoadmap.owner,
                start_date: this.selectedRoadmap.start_date,
                target_date: this.selectedRoadmap.target_date
            };
            const response = await this.request(`/api/roadmaps/${this.selectedRoadmap.id}`, {
                method: 'PUT',
                headers: { 'Content-Type': 'application/json' },
                body: JSON.stringify(payload)
            });
            if (response.ok) {
                await this.loadRoadmaps();
                await this.selectRoadmap({ id: this.selectedRoadmap.id });
            }
        },

        async addStep() {
            if (!this.selectedRoadmap || !this.newStep.title) return;
            const payload = { ...this.newStep };
            const response = await this.request(`/api/roadmaps/${this.selectedRoadmap.id}/steps`, {
                method: 'POST',
                headers: { 'Content-Type': 'application/json' },
                body: JSON.stringify(payload)
            });
            if (response.ok) {
                this.newStep = {
                    title: '',
                    description: '',
                    status: 'planned',
                    owner: '',
                    due_date: ''
                };
                this.stepFormOpen = false;
                await this.selectRoadmap({ id: this.selectedRoadmap.id });
                await this.loadRoadmaps();
            }
        },

        async updateStep(step) {
            if (!this.selectedRoadmap) return;
            const payload = {
                title: step.title,
                description: step.description,
                status: step.ui_status || step.status,
                owner: step.owner,
                due_date: step.due_date,
                position: step.position
            };
            const response = await this.request(`/api/roadmaps/${this.selectedRoadmap.id}/steps/${step.id}`, {
                method: 'PUT',
                headers: { 'Content-Type': 'application/json' },
                body: JSON.stringify(payload)
            });
            if (response.ok) {
                await this.selectRoadmap({ id: this.selectedRoadmap.id });
                await this.loadRoadmaps();
            }
        },

        async deleteStep(step) {
            if (!this.selectedRoadmap) return;
            const response = await this.request(`/api/roadmaps/${this.selectedRoadmap.id}/steps/${step.id}`, {
                method: 'DELETE'
            });
            if (response.ok) {
                await this.selectRoadmap({ id: this.selectedRoadmap.id });
                await this.loadRoadmaps();
            }
        },

        async createRoadmap() {
            this.roadmapError = '';
            const payload = { ...this.newRoadmap };
            if (!payload.ticket_id) {
                delete payload.ticket_id;
            }
            const response = await this.request('/api/roadmaps', {
                method: 'POST',
                headers: { 'Content-Type': 'application/json' },
                body: JSON.stringify(payload)
            });
            if (response.ok) {
                this.roadmapModalOpen = false;
                this.newRoadmap = {
                    title: '',
                    objective: '',
                    status: 'planned',
                    owner: '',
                    start_date: '',
                    target_date: '',
                    ticket_id: ''
                };
                await this.loadRoadmaps();
            } else {
                const error = await response.json();
                this.roadmapError = error.error || 'Roadmap konnte nicht erstellt werden.';
            }
        },

        refreshIcons() {
            this.$nextTick(() => window.InventoryRefreshIcons?.());
        }
    }));
});
