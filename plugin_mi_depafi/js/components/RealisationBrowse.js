import Alpine from 'alpinejs';
import _ from 'lodash';
import api from "@core/js/utils/api";

const REALISATION_VIEWS_NAME = {
  MAP : "realisation-map",
  TABLE : "realisation-table"
};

Alpine.data('RealisationBrowse', () => ({
  displayedViewName: REALISATION_VIEWS_NAME.MAP,
  viewsName : REALISATION_VIEWS_NAME,
  
  async init() {
    await this.fetchData();
  },

  realisations: [],
  searchQuery: '',
  selectedDepartments: [],
  loading: true,

  async fetchData() {
    this.loading = true;
    const params = new URLSearchParams();
    if (this.searchQuery) params.set('search', this.searchQuery);
    this.selectedDepartments.forEach((d) => params.append('departments', d));
    this.realisations = (await api.get(`/api/realisations/map/?${params}`)).data;
    this.loading = false;
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

  onClickResetQuery() {
    this.searchQuery = '';
    this.$dispatch('reset-departments-selector');
  },
}));
