import Alpine from 'alpinejs';

Alpine.data('RealisationFormValidation', () => ({
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
            focusSelector: '.select-a11y > button.fr-select',
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
        this.formData.resource.value = formFields.resource.value;
        this.formData.location.value = formFields.location.value;
        this.formData.date.value = formFields.date.value;
        this.$watch('$store.editor.currentMessage', (value) => {
            this.setValueAndError('description', value);
        });
    },
    onSubmit(event) {
        const isPublishing = event.submitter?.value === 'published';

        this.formErrors.resource = this.isEmpty('resource');

        if (isPublishing) {
            this.formErrors.location = this.isEmpty('location');
            this.formErrors.date = this.isEmpty('date');
            this.formErrors.description = this.isEmpty('description');
        } else {
            this.formErrors.location = false;
            this.formErrors.date = false;
            this.formErrors.description = false;
        }

        const firstError = ['resource', 'location', 'date', 'description'].find((name) => this.formErrors[name]);
        if (firstError) {
            event.preventDefault();
            document.querySelector(this.formData[firstError].focusSelector)?.focus();
        }
    },
    isEmpty(name) {
        return !this.formData[name].value.trim();
    },
    updateField(event) {
        const { name, value } = event.target;
        if (name in this.formData) {
            this.setValueAndError(name, value);
        }
    },
    syncResourceSelect() {
        this.setValueAndError('resource', document.getElementById('id_resource').value);
    },
    setValueAndError(name, value) {
        this.formData[name].value = value;
        if (value.trim()) {
            this.formErrors[name] = false;
        }
    }
}));
