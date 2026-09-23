import Alpine from 'alpinejs';

const REALISATION_VIEWS_NAME = {
  MAP : "realisation-map",
  TABLE : "realisation-table"
};

Alpine.data('RealisationBrowse', () => ({
  displayedViewName: REALISATION_VIEWS_NAME.MAP,
  viewsName : REALISATION_VIEWS_NAME,
}));
