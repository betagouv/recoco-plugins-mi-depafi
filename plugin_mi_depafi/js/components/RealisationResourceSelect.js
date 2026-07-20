import Alpine from "alpinejs";
import Select from "@core/js/utils/select-a11y";

Alpine.data("realisationResourceSelect", () => ({
  init() {
    new Select(this.$el.querySelector("select"));
  },
}));
