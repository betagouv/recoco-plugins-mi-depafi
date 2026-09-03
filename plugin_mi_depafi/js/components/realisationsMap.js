import Alpine from 'alpinejs';
import htmx from 'htmx.org';
import * as L from 'leaflet';
import 'leaflet/dist/leaflet.css';
import 'leaflet.markercluster';
import 'leaflet.markercluster/dist/MarkerCluster.css';
import 'leaflet.markercluster/dist/MarkerCluster.Default.css';

import realisationsFeed from '../utils/realisationsFeed';

function RealisationsMap(regionsData) {
  return {
    ...realisationsFeed(),
    htmx,
    regions: JSON.parse(regionsData.textContent),
    selectedProjectId: null,
    map: null,
    clusterGroup: null,
    markersByProject: {},
    //panel management
    panelConfig: {
      isOpen : false,
      mode : undefined, // undefined || 'projectDetails' || 'projectList' 
    },

    get sidebarRealisations() {
      if (!this.selectedProjectId) return this.realisations;
      return this.realisations.filter((r) => r.project.id === this.selectedProjectId);
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

      this.map.on('click', () => {
        this.setMarkerFocus(null);
      });
    },

    afterFetch() {
      this.updateMarkers();
    },

    updateMarkers() {
      if (!this.map) return;
      this.clusterGroup.clearLayers();
      this.markersByProject = {};
      this.selectedProjectId = null;

      const byProject = {};
      this.realisations.forEach((r) => {
        if (!byProject[r.project.id]) {
          byProject[r.project.id] = { project: r.project, count: 0 };
        }
        byProject[r.project.id].count++;
      });

      Object.values(byProject).forEach(({ project, count }) => {
        const lat = project.latitude ?? project.commune?.latitude;
        const lng = project.longitude ?? project.commune?.longitude;
        if (!lat || !lng) return;

        const marker = L.marker([lat, lng], { icon: mapUtils.ICONS.default });
        marker.on('click', () => {
          this.selectedProject = {...project, realisationsCount: count};
          this.setMarkerFocus(project.id);
          this.panelConfig = {
            isOpen : true,
            mode: 'projectDetails'
          }
        });
        this.markersByProject[project.id] = marker;
        this.clusterGroup.addLayer(marker);
      });
    },

    clearProjectFilter() {
      this.setMarkerFocus(null);
      this.selectedProject = null;
    },
    
    onClickToggleGrey() {
      mapUtils.toggleGreyFilter(this.map);
    },
  };
}

Alpine.data('RealisationsMap', RealisationsMap);
