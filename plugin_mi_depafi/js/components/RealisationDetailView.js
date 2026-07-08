import Alpine from "alpinejs";

Alpine.data("realisationDetailView", (initialView = "detail") => ({
  currentView: initialView,
  photos: [],
  photoToDisplay: null,

  init() {
    const photosData = document.getElementById("realisation-photos-data").textContent;
    this.photos = JSON.parse(photosData);
  },

  showView(view) {
    if (view === "photos" && this.photos.length) {
      this.getPhotoToDisplay(this.photos[0].id);
    }
    this.currentView = view;
  },

  isView(view) {
    return this.currentView === view;
  },

  getPhotoToDisplay(photoId) {
    if (this.currentView != "photos") {
      this.currentView = "photos";
    }
    const index = this.photos.findIndex((photo) => photo.id === photoId);
    this.photoToDisplay =
      index === -1 ? null : { ...this.photos[index], number: index + 1 };
    return this.photoToDisplay;
  },
}));
