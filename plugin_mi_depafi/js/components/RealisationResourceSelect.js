import Alpine from "alpinejs";
// TODO(import-map): left as an external bare import - resolves at runtime
// once core exposes an import map entry for "@core/js/utils/select-a11y".
import Select from "@core/js/utils/select-a11y";

Alpine.data("realisationResourceSelect", () => ({
  init() {
    new Select(this.$el.querySelector("select"));
  },
}));
