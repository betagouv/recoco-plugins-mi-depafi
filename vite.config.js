import { resolve } from 'path';
import { defineConfig } from 'vite';

const jsRoot = resolve(__dirname, 'plugin_mi_depafi/js');

export default defineConfig({
  build: {
    outDir: resolve(__dirname, 'plugin_mi_depafi/static/plugin_mi_depafi/dist'),
    emptyOutDir: true,
    manifest: 'manifest.json',
    rollupOptions: {
      input: {
        'apps/realisationForm': resolve(jsRoot, 'apps/realisationForm.js'),
        'apps/realisationListCrm': resolve(jsRoot, 'apps/realisationListCrm.js'),
        'components/realisationsMap': resolve(jsRoot, 'components/realisationsMap.js'),
        'components/RealisationDetailView': resolve(
          jsRoot,
          'components/RealisationDetailView.js'
        ),
        'utils/RealisationInviteOnTaskDone': resolve(
          jsRoot,
          'utils/RealisationInviteOnTaskDone.js'
        ),
        'styles/realisation-form.css': resolve(jsRoot, 'styles/realisation-form.css.js'),
        'styles/realisation-list.css': resolve(jsRoot, 'styles/realisation-list.css.js'),
        'styles/fragments/realisation-modal.css': resolve(
          jsRoot,
          'styles/fragments/realisation-modal.css.js'
        ),
      },
      // Shared with core - must not be bundled a second time, or Alpine.data()
      // registrations / Leaflet layers silently attach to a dead instance.
      // Resolved at runtime via a browser import map once recoco's core
      // ships one (tracked separately - not yet available as of this build).
      external: (id) =>
        ['alpinejs', 'htmx.org', 'leaflet', 'lodash'].includes(id) ||
        id.startsWith('@core/js/'),
    },
  },
});
