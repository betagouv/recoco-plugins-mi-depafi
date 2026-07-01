import Alpine from "alpinejs";

Alpine.data("realisationDocumentList", () => ({
  documents: [],

  addDocuments(event) {
    const newFiles = Array.from(event.target.files);
    newFiles.forEach((file) => {
      this.documents.push({ name: file.name, size: file.size, file });
    });
    this.syncInput();
  },

  removeDocument(index) {
    this.documents.splice(index, 1);
    this.syncInput();
  },

  syncInput() {
    const dt = new DataTransfer();
    this.documents.forEach((d) => dt.items.add(d.file));
    this.$refs.documentInput.files = dt.files;
  },
}));
