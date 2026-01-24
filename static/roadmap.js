document.addEventListener('alpine:init', () => {
    Alpine.data('roadmapApp', () => ({
        roadmaps: [],
        selectedRoadmap: null,
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
            const params = new URLSearchParams(window.location.search);
            this.preselectedTicketId = params.get('ticket_id');
            await this.loadRoadmaps();
            if (this.preselectedTicketId) {
                const match = this.roadmaps.find((roadmap) => String(roadmap.ticket_id) === String(this.preselectedTicketId));
                if (match) {
                    await this.selectRoadmap(match);
                }
            }
            this.$nextTick(() => feather.replace());
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
            const params = new URLSearchParams();
            if (this.filters.status) params.append('status', this.filters.status);
            if (this.filters.search) params.append('search', this.filters.search);
            if (this.filters.mine) params.append('mine', '1');
            if (this.filters.owner) params.append('owner', this.filters.owner);
            if (this.filters.month) params.append('month', this.filters.month);
            if (this.preselectedTicketId) params.append('ticket_id', this.preselectedTicketId);

            const response = await fetch(`/api/roadmaps?${params.toString()}`);
            if (response.ok) {
                this.roadmaps = await response.json();
                this.updateOverview();
            }
            this.$nextTick(() => feather.replace());
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
            const response = await fetch(`/api/roadmaps/${roadmap.id}`);
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
            this.$nextTick(() => feather.replace());
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
            const response = await fetch(`/api/roadmaps/${this.selectedRoadmap.id}`, {
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
            const response = await fetch(`/api/roadmaps/${this.selectedRoadmap.id}/steps`, {
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
            const response = await fetch(`/api/roadmaps/${this.selectedRoadmap.id}/steps/${step.id}`, {
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
            const response = await fetch(`/api/roadmaps/${this.selectedRoadmap.id}/steps/${step.id}`, {
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
            const response = await fetch('/api/roadmaps', {
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
        }
    }));
});
