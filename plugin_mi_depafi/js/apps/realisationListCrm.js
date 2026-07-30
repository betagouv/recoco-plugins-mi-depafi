// TODO(import-map): this plugin now builds independently, so @core/css/*
// can no longer be resolved at build time. projectList styles are missing
// until core exposes a shared import map for its stylesheets.
// import "@core/css/crm/projectList.scss";
import "../components/RealisationListCrm";
// TODO(import-map): left as an external bare import - resolves at runtime
// once core exposes an import map entry for "@core/js/components/MultiSelect2.js".
import "@core/js/components/MultiSelect2.js";
