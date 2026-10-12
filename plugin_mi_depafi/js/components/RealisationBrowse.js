import Alpine from 'alpinejs';
import _ from 'lodash';
import api from "@core/js/utils/api";

const REALISATION_VIEWS_NAME = {
  MAP : "realisation-map",
  TABLE : "realisation-table"
};

Alpine.data('RealisationBrowse', (regionsData) => ({
  displayedViewName: REALISATION_VIEWS_NAME.MAP,
  viewsName : REALISATION_VIEWS_NAME,
  regions: JSON.parse(regionsData.textContent),
  realisations: [],
  searchQuery: '',
  labelSelectedDepartment: '',
  selectedDepartments: [],
  selectedPerimeter: '',
  loading: true,

  get hasActiveFilters() {
    return this.searchQuery !== '' || this.selectedDepartments.length > 0 || this.selectedPerimeter !== '';
  },

  async init() {
    this.urlParamInit();
    await this.fetchData();
  },

  urlParamInit() {
    const urlParams = new URLSearchParams(window.location.search);
    const view = urlParams.get('view');
    if(Object.values(this.viewsName).includes(view)) {
      this.displayedViewName = view;
    }
    this.$watch('displayedViewName', () => {
      urlParams.set("view", this.displayedViewName)
      history.replaceState(null, '', `${window.location.pathname}?${urlParams}`);
    })
  },

  async fetchData() {
    this.loading = true;
    const params = new URLSearchParams();
    if (this.searchQuery) params.set('search', this.searchQuery);
    this.selectedDepartments.forEach((d) => params.append('departments', d));
    if (this.selectedPerimeter) params.set('perimeter', this.selectedPerimeter);
    this.realisations = (await api.get(`/api/realisations/map/?${params}`)).data;
    this.loading = false;
  },

  onSearch: _.debounce(async function () {
    await this.fetchData();
  }, 400),

  async onPerimeterSelected() {
    await this.fetchData();
  },

  async onDepartmentsSelected(event) {
    this.selectedDepartments = event.detail || [];
    await this.fetchData();
  },

  onDisplayedLabel(event) {
    this.labelSelectedDepartment = event.detail;
  },

  onClickResetQuery() {
    this.searchQuery = '';
    // Clear the perimeter before resetting the departments selector: its
    // reset emits `selected-departments`, which triggers the fetch.
    this.selectedPerimeter = '';
    this.$dispatch('reset-departments-selector');
  },
}));
