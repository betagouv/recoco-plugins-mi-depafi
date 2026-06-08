window.addEventListener('task:done', (event) => {
  const { projectId, resourceId } = event.detail ?? {};
  if (!projectId) return;

  const modal = document.getElementById('realisation-invite-modal');
  const cta = document.getElementById('realisation-invite-modal-cta');
  if (!modal || !cta) return;

  let url = `/project/${projectId}/realisations/creer/`;
  if (resourceId) {
    url += `?resource_id=${encodeURIComponent(resourceId)}`;
  }
  cta.href = url;

  window.dsfr(modal).modal.disclose();
});
