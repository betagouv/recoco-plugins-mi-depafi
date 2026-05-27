import Alpine from 'alpinejs';
import api from '@core/js/utils/api';

function realisationsUrl({
  search = '',
  departments = [],
  status = [],
  limit = 20,
  offset = 0,
} = {}) {
  const params = new URLSearchParams({ limit, offset });
  if (search) params.set('q', search);
  departments.forEach((d) => params.append('departments', d));
  status.forEach((s) => params.append('status', s));
  return `/api/crm/realisations/?${params.toString()}`;
}

Alpine.data('RealisationListCrm', () => ({
  dataLoaded: false,
  realisationsToDisplay: [],
  realisationsTotal: 0,
  backendSearch: {
    searchText: '',
    searchDepartment: [],
    searchStatus: [],
  },
  pagination: {
    currentPage: 1,
    limit: 20,
    total: 0,
  },
  options: [
    {
      value: 'draft',
      text: 'Brouillon',
      color: 'fr-badge--warning fr-badge fr-badge--no-icon',
    },
    {
      value: 'published',
      text: 'Publié',
      color: 'fr-badge--success fr-badge fr-badge--no-icon',
    },
  ],

  async init() {
    const response = await this.fetchRealisations();
    this.realisationsToDisplay = response.results;
    this.realisationsTotal = response.count;
    this.pagination.total = Math.ceil(response.count / this.pagination.limit);
    this.dataLoaded = true;
  },

  updateListAndPagination(response) {
    this.realisationsToDisplay = response.results;
    this.realisationsTotal = response.count;
    this.pagination.total = Math.ceil(response.count / this.pagination.limit);
    this.pagination.currentPage = 1;
  },

  async saveSelectedDepartment(event) {
    if (!event.detail) return;
    this.backendSearch.searchDepartment = [...event.detail];
    const response = await this.fetchRealisations();
    this.updateListAndPagination(response);
  },

  async saveSelectedStatus(event) {
    if (!event.detail) return;
    this.backendSearch.searchStatus = [...event.detail];
    const response = await this.fetchRealisations();
    this.updateListAndPagination(response);
  },

  async onSearch() {
    const response = await this.fetchRealisations();
    this.updateListAndPagination(response);
  },

  async onChangePage(pageNumber) {
    const offset = this.pagination.limit * (pageNumber - 1);
    const response = await this.fetchRealisations({ offset });
    this.realisationsToDisplay = response.results;
    this.pagination.currentPage = pageNumber;
  },

  async fetchRealisations({ offset = 0 } = {}) {
    const response = await api.get(
      realisationsUrl({
        search: this.backendSearch.searchText,
        departments: this.backendSearch.searchDepartment,
        status: this.backendSearch.searchStatus,
        limit: this.pagination.limit,
        offset,
      })
    );
    return response.data;
  },

  realisationsCountLabel() {
    if (this.realisationsTotal > 0) {
      return `${this.realisationsTotal} réalisation${this.realisationsTotal > 1 ? 's' : ''}`;
    }
    return 'Aucun résultat';
  },

  statusLabel(status) {
    return this.options.find((o) => o.value === status)?.text ?? status;
  },

  statusColor(status) {
    return status === 'published' ? 'fr-badge--success' : 'fr-badge--warning';
  },
}));
