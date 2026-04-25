import { createStore } from "/js/AlpineStore.js";
import * as API from "/js/api.js";

const STATS_API = "/plugins/memex/memex_memory_stats";

export const store = createStore("memexDashboard", {
    loading: false,
    error: null,

    decay: null,
    session: null,
    nudge: null,
    portrait: null,
    skills: null,
    chapters: null,
    availableSubdirs: [],
    selectedSubdir: null,

    async onOpen() {
        await this.refresh();
    },

    async refresh() {
        this.loading = true;
        this.error = null;
        try {
            const body = this.selectedSubdir ? { memory_subdir: this.selectedSubdir } : {};
            const res = await API.callJsonApi(STATS_API, body);
            if (res?.ok) {
                this.availableSubdirs = res.available_subdirs || [];
                this.decay    = res.decay    || null;
                this.session  = res.session  || null;
                this.nudge    = res.nudge    || null;
                this.portrait = res.portrait || null;
                this.skills   = res.skills   || null;
                this.chapters = res.chapters || null;
            } else {
                this.error = res?.error || "Unknown error";
            }
        } catch (e) {
            this.error = e.message || "Failed to load data";
        } finally {
            this.loading = false;
        }
    },

    selectSubdir(subdir) {
        this.selectedSubdir = this.selectedSubdir === subdir ? null : subdir;
        this.refresh();
    },

    subsystemsTotal() {
        return (this.decay?.total                   || 0)
             + (this.session?.sessions              || 0)
             + (this.nudge?.insights_generated      || 0)
             + (this.portrait?.traits               || 0)
             + (this.skills?.total                  || 0)
             + (this.chapters?.total                || 0);
    },

    formatTokens(n) {
        if (!n) return "0";
        if (n >= 1_000_000) return (n / 1_000_000).toFixed(1) + "M";
        if (n >= 1_000) return Math.round(n / 1_000) + "K";
        return String(n);
    },

    cleanup() {
        this.decay    = null;
        this.session  = null;
        this.nudge    = null;
        this.portrait = null;
        this.skills   = null;
        this.chapters = null;
    },

    formatDate(iso) {
        if (!iso) return "—";
        const d = new Date(iso);
        return isNaN(d.getTime()) ? iso : d.toLocaleString();
    },

    subdirLabel(sd) {
        return sd.startsWith("projects/") ? sd.slice(9) : sd;
    },
});
