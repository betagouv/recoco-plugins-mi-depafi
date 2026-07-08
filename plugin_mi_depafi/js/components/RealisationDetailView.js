import Alpine from "alpinejs";

Alpine.data("realisationDetailView", (initialView = "detail") => ({
  currentView: initialView,

  showView(view) {
    this.currentView = view;
  },

  isView(view) {
    return this.currentView === view;
  },
}));
