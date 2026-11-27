import { generateTrackEvent } from "@core/js/utils/trackingMatomo";

export const trackOpenModalRealDetails = () => {
  generateTrackEvent('Click', 'Ouverture de modale de détails d\'une réalisation');
};

export const trackClickSitesAndRealisation = () => {
  generateTrackEvent('Click', 'Ouverture de la page sites et réalisations');
};

export const trackClickSitesAndRealisationTableView = () => {
  generateTrackEvent('Click', 'Ouverture de la vue tableau sur la page sites et réalisations');
};

export const trackClickGoToProject = () => {
  generateTrackEvent('Click', 'Afficher la page d\'un dossier');
};