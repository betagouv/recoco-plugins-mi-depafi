import Alpine from 'alpinejs';
import htmx from 'htmx.org';

import '@core/css/crm/table.scss';
import '@core/css/crm/projectList.scss';

import realisationsFeed from '../utils/realisationsFeed';

Alpine.data('RealisationTable', () => ({
  ...realisationsFeed(),
  htmx,

  async init() {
    await this.fetchData();
  },

  countLabel() {
    const count = this.realisations.length;
    if (count === 0) return 'Aucun résultat';
    return `${count} réalisation${count > 1 ? 's' : ''}`;
  },

  locationLabel(realisation) {
    const commune = realisation.project?.commune;
    if (!commune) return '—';
    const code = commune.department?.code;
    return code ? `${commune.name} (${code})` : commune.name;
  },

  dateLabel(realisation) {
    const value = realisation.date ?? realisation.updated_at;
    return value ? new Date(value).toLocaleDateString('fr-FR') : '—';
  },
}));
