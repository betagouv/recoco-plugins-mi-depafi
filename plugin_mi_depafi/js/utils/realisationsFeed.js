import _ from 'lodash';
import api from "@core/js/utils/api";

export default function realisationsFeed() {
  return {
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
      this.afterFetch();
    },

    /** To override in consummer */
    afterFetch() {},

    onSearch: _.debounce(async function () {
      await this.fetchData();
    }, 400),

    async onDepartmentsSelected(event) {
      this.selectedDepartments = event.detail || [];
      await this.fetchData();
    },
  };
}
