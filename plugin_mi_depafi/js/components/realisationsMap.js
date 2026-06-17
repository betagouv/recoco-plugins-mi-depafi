import Alpine from 'alpinejs';
import htmx from 'htmx.org';
import * as L from 'leaflet';
import 'leaflet/dist/leaflet.css';
import 'leaflet.markercluster';
import 'leaflet.markercluster/dist/MarkerCluster.css';
import 'leaflet.markercluster/dist/MarkerCluster.Default.css';
import _ from 'lodash';

window.htmx = htmx;

function RealisationsMap(regionsData) {
  return {
    regions: JSON.parse(regionsData.textContent),
    realisations: [],
    selectedProjectId: null,
    searchQuery: '',
    selectedDepartments: [],
    loading: false,
    map: null,
    clusterGroup: null,

    get sidebarRealisations() {
      if (!this.selectedProjectId) return this.realisations;
      return this.realisations.filter((r) => r.project.id === this.selectedProjectId);
    },

    get sidebarTitle() {
      if (!this.selectedProjectId) return `${this.realisations.length} Réalisation(s)`;
      const count = this.sidebarRealisations.length;
      const project = this.realisations.find((r) => r.project.id === this.selectedProjectId)?.project;
      return `${count} Réalisation(s) — ${project?.name ?? ''}`;
    },

    async init() {
      this.initMap();
      await this.fetchData();
    },

    initMap() {
      this.map = L.map('realisations-map').setView([46.5, 2.5], 6);
      L.tileLayer('https://{s}.tile.openstreetmap.fr/osmfr/{z}/{x}/{y}.png', {
        attribution:
          '&copy; <a href="https://www.openstreetmap.org/copyright">OpenStreetMap</a> contributors',
        maxZoom: 19,
      }).addTo(this.map);
      this.clusterGroup = L.markerClusterGroup();
      this.map.addLayer(this.clusterGroup);
    },

    async fetchData() {
      this.loading = true;
      const params = new URLSearchParams();
      if (this.searchQuery) params.set('search', this.searchQuery);
      this.selectedDepartments.forEach((d) => params.append('departments', d));
      const res = await fetch(`/api/realisations/map/?${params}`);
      this.realisations = await res.json();
      this.updateMarkers();
      this.loading = false;
    },

    updateMarkers() {
      if (!this.map) return;
      this.clusterGroup.clearLayers();
      this.selectedProjectId = null;

      const byProject = {};
      this.realisations.forEach((r) => {
        if (!byProject[r.project.id]) {
          byProject[r.project.id] = { project: r.project, count: 0 };
        }
        byProject[r.project.id].count++;
      });

      const icon = L.divIcon({ className: 'realisation-map-marker', iconSize: [12, 12] });

      Object.values(byProject).forEach(({ project, count }) => {
        const lat = project.latitude ?? project.commune?.latitude;
        const lng = project.longitude ?? project.commune?.longitude;
        if (!lat || !lng) return;

        const marker = L.marker([lat, lng], { icon });
        marker.bindPopup(
          `<strong>${project.name}</strong><br>${project.commune?.name ?? ''}<br>${count} réalisation(s)`
        );
        marker.on('click', () => {
          this.selectedProjectId = project.id;
        });
        this.clusterGroup.addLayer(marker);
      });
    },

    onSearch: _.debounce(async function () {
      await this.fetchData();
    }, 400),

    async onDepartmentsSelected(event) {
      this.selectedDepartments = event.detail || [];
      await this.fetchData();
    },

    clearProjectFilter() {
      this.selectedProjectId = null;
    },
  };
}

Alpine.data('RealisationsMap', RealisationsMap);
