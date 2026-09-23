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
  realisations: [],
  searchQuery: '',
  selectedDepartments: [],
  loading: true,

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
