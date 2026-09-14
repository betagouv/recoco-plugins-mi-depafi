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

    get panelProjectListTitle() {
      const realisationLength = this.realisations.length;

      return `${this.projectLength} site${isPlural('', 's',this.projectLength)} et ${realisationLength} réalisation${isPlural('', 's',realisationLength)} trouvé${isPlural('', 's',this.projectLength+realisationLength)}`
    },

    sidebarRealisationsForProject(projectId) {
      return this.realisations.filter((r) => r.project.id === projectId);
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

      Object.values(this.realisationsByProject).forEach((project, count ) => {
        const lat = project.latitude ?? project.commune?.latitude;
        const lng = project.longitude ?? project.commune?.longitude;
        if (!lat || !lng) return;

        const marker = L.marker([lat, lng], { icon: mapUtils.ICONS.default });
        marker.on('click', () => {
          this.selectedProject = {...project, realisationsCount: count};
          this.setMarkerFocus(project.id);
          this.openPanel({mode: 'projectDetails'});
        });
        this.markersByProject[project.id] = marker;
        this.clusterGroup.addLayer(marker);
      });
      console.log(this.realisationsByProject)
    },

    setMarkerFocus(projectId) {
      const previousMarker = this.markersByProject[this.selectedProjectId];
      const clickedMarker = this.markersByProject[projectId];
      mapUtils.setMarkerFocus(previousMarker, clickedMarker);

      this.selectedProjectId = projectId;
    },

    clearProjectFilter() {
      this.selectedProjectId = null;
    },
  };
}

Alpine.data('RealisationsMap', RealisationsMap);
