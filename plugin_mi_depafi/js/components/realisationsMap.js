import Alpine from 'alpinejs';
import htmx from 'htmx.org';
import * as L from 'leaflet';
import 'leaflet/dist/leaflet.css';
import 'leaflet.markercluster';
import 'leaflet.markercluster/dist/MarkerCluster.css';
import 'leaflet.markercluster/dist/MarkerCluster.Default.css';
import _ from 'lodash';
import mapUtils from '@core/js/utils/map';
import { isPlural } from '@core/js/utils/isPlural';
import '@core/css/map.css';

function RealisationsMap(regionsData) {
  return {
    htmx,
    regions: JSON.parse(regionsData.textContent),
    realisations: [],
    realisationsByProject: [],
    selectedProjectId: null,
    selectedProject: null,
    projectLength: 0,
    searchQuery: '',
    selectedDepartments: [],
    labelSelectedDepartment: '',
    loading: false,
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

    async fetchData() {
      this.loading = true;
      const params = new URLSearchParams();
      if (this.searchQuery) {
        params.set('search', this.searchQuery);
        this.openPanel({mode: 'projectList'});
      }
      this.selectedDepartments.forEach((d) => params.append('departments', d));
      const res = await fetch(`/api/realisations/map/?${params}`);
      this.realisations = await res.json();
      this.realisationsByProject = {};
      this.projectLength = 0; 
      this.realisations.forEach((r) => {
        if (!this.realisationsByProject[r.project.id]) {
          this.realisationsByProject[r.project.id] = { ...r.project, count: 0 };
          this.projectLength++;
        }
        this.realisationsByProject[r.project.id].count++;
      });
      this.updateMarkers();
      this.loading = false;
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

    onSearch: _.debounce(async function () {
      await this.fetchData();
    }, 400),

    async onDepartmentsSelected(event) {
      this.selectedDepartments = event.detail || [];
      await this.fetchData();
    },
    
    onDisplayedLabel(event) {
      this.labelSelectedDepartment = event.detail;
    },

    openPanel(mode = {}) {
        this.panelConfig = {
          isOpen : true,
          ...mode
        };
    },

    closePanel() {
      if(this.panelConfig.mode == 'projectDetails') {
        this.panelConfig = {
          isOpen : false,
          mode: undefined
        };
        this.setMarkerFocus(null);
        this.selectedProject = null;
      }
    },
    
    onClickToggleGrey() {
      mapUtils.toggleGreyFilter(this.map);
    },
  };
}

Alpine.data('RealisationsMap', RealisationsMap);
