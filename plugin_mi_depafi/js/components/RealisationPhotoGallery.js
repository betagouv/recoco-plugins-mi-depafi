import Alpine from "alpinejs";

Alpine.data("realisationPhotoGallery", () => ({
  photos: [],

  addPhotos(event) {
    const newFiles = Array.from(event.target.files);
    newFiles.forEach((file) => {
      const reader = new FileReader();
      reader.onload = (e) => {
        this.photos.push({ src: e.target.result, name: file.name, file });
      };
      reader.readAsDataURL(file);
    });
    // Merge new files into the existing FileList via DataTransfer
    const dt = new DataTransfer();
    this.photos.forEach((p) => dt.items.add(p.file));
    newFiles.forEach((f) => dt.items.add(f));
    this.$refs.fileInput.files = dt.files;
  },

  removePhoto(index) {
    this.photos.splice(index, 1);
    const dt = new DataTransfer();
    this.photos.forEach((p) => dt.items.add(p.file));
    this.$refs.fileInput.files = dt.files;
  },
}));
