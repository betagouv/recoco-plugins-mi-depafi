import Alpine from 'alpinejs';

Alpine.data('RealisationFormValidation', () => ({
    isFormValid: false,
    formData: {
        resource: '',
        location: '',
        date: '',
        description: '',
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
}));