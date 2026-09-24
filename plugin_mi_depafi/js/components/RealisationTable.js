import Alpine from 'alpinejs';
import htmx from 'htmx.org';
import _ from 'lodash';

import '@core/css/crm/table.scss';
import '@core/css/crm/projectList.scss';

Alpine.data('RealisationTable', () => ({
  htmx,
  realisationsGroupedBySite : {},

  get realisationsDataTable () {
    return this.realisations;
  },

  get realisationsGroupedBySite () {
    return _.groupBy(this.realisationsDataTable, 'project.id');;
  },

  countLabel() {
    const count = this.realisationsDataTable.length;
    if (count === 0) return 'Aucun résultat';
    return `${count} réalisation${count > 1 ? 's' : ''}`;
  },

  locationLabel(project) {
    const commune = project?.commune;
    if (!commune) return '—';
    const code = commune.department?.code;
    return code ? `${commune.name} (${code})` : commune.name;
  },

  queryLabel() {
    const realisationCount = this.realisationsDataTable.length;
    const siteCount = Object.values(this.realisationsGroupedBySite).length;
    if (siteCount === 0) return 'Aucun résultat';
    return `${siteCount} site${siteCount > 1 ? 's' : ''} ayant ${realisationCount} réalisation${realisationCount > 1 ? 's' : ''} correspondante${realisationCount > 1 ? 's' : ''}`
  },

  realisationLabel(site) {
    const realisationCount = site.length
    if (realisationCount === 0) return 'Aucune correspondance';
    return `${realisationCount} correspondante${realisationCount > 1 ? 's' : ''}`
  },

  dateLabel(realisation) {
    const value = realisation.date ?? realisation.updated_at;
    return value ? new Date(value).toLocaleDateString('fr-FR') : '—';
  },
}));
