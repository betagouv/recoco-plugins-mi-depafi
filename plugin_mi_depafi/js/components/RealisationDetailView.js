import Alpine from "alpinejs";

Alpine.data("realisationDetailView", (initialView = "detail") => ({
  currentView: initialView,
  photos: [],
  photoToDisplay: null,

  init() {
    const photosData = document.getElementById("realisation-photos-data").textContent;
    this.photos = JSON.parse(photosData);
    this.photos.forEach((photo, index) => {
      photo.number = index + 1;
      photo.prev = this.photos[index - 1] || null;
      photo.next = this.photos[index + 1] || null;
    });
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
    this.photoToDisplay = this.photos.find((photo) => photo.id === photoId) || null;
    return this.photoToDisplay;
  },

  nextPic() {
    if (this.photoToDisplay?.next) {
      this.photoToDisplay = this.photoToDisplay.next;
    }
  },

  previousPic() {
    if (this.photoToDisplay?.prev) {
      this.photoToDisplay = this.photoToDisplay.prev;
    }
  },

  isSelected(element) {
    if (this.currentView == 'detail') {
      return element === 'detail';
    }
    else if (this.currentView == 'photos') {
      return this.photoToDisplay !== null && element === this.photoToDisplay.id;
    }
    return false;
  },

}));
