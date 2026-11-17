import Alpine from 'alpinejs';

Alpine.data('RealisationFormValidation', () => ({
    isFormValid: false,
    formErrors: {
        resource: false,
        location: false,
        date: false,
        description: false,
    },
    formData: {
          resource: {
              value: '',
              message: "Sélectionnez l'action concernée dans la liste.",
              focusSelector: '.select-a11y .fr-select',
          },
          location: {
              value: '',
              message: 'Indiquez le ou les sites ou bâtiments concernés.',
              focusSelector: '#id_location',
          },
          date: {
              value: '',
              message: 'Indiquez la date de la réalisation.',
              focusSelector: '#id_date',
          },
          description: {
              value: '',
              message: "Décrivez comment l'action a été mise en œuvre.",
              focusSelector: '#comment-text-ref .ProseMirror',
          },
      },
    init() {
        const formFields = this.$el.querySelector('#realisation-form').elements;
        this.formData.resource = formFields.resource.value;
        this.formData.location = formFields.location.value;
        this.formData.date = formFields.date.value;
        this.$watch('$store.editor.currentMessage', (value) => {
            this.formData.description = value || '';
            this.validateForm();
        });
        this.validateForm();
    },
    validateForm() {
        if (!this.formData.resource || !this.formData.location || !this.formData.date || !this.formData.description) {
            this.isFormValid = false;
            return;
        }
        this.isFormValid = true;
    },
    updateField(event) {
        const { name, value } = event.target;
        this.formData[name] = value;
        this.validateForm();
    },
    syncResourceSelect() {
        this.formData.resource = document.getElementById('id_resource').value;
        this.validateForm();
    }
}));