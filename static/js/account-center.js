/* Uddokta Dokan — Account Center helpers (scoped to .ud-profile-page) */
(function () {
  'use strict';

  function page() {
    return document.querySelector('.ud-profile-page');
  }
  if (!page()) return;

  function fireConfirm(message, next) {
    if (window.Swal) {
      window.Swal.fire({
        title: 'Are you sure?',
        text: message,
        icon: 'warning',
        showCancelButton: true,
        confirmButtonColor: '#8a2be2',
        cancelButtonColor: '#6b7280',
        confirmButtonText: 'Yes, continue',
        cancelButtonText: 'Cancel',
      }).then(function (result) {
        if (result.isConfirmed) next();
      });
    } else if (window.confirm(message)) {
      next();
    }
  }

  function copyText(text) {
    if (navigator.clipboard && navigator.clipboard.writeText) {
      navigator.clipboard.writeText(text).then(function () {
        if (window.Swal) {
          window.Swal.fire({ title: 'Copied', icon: 'success', timer: 1400, showConfirmButton: false });
        }
      });
      return;
    }
    var ta = document.createElement('textarea');
    ta.value = text;
    ta.style.position = 'fixed';
    ta.style.opacity = '0';
    document.body.appendChild(ta);
    ta.select();
    try { document.execCommand('copy'); } catch (e) { /* noop */ }
    document.body.removeChild(ta);
  }

  document.addEventListener('click', function (e) {
    var confirmBtn = e.target.closest('[data-confirm]');
    if (confirmBtn) {
      var msg = confirmBtn.getAttribute('data-confirm');
      e.preventDefault();
      fireConfirm(msg, function () { confirmBtn.closest('form').submit(); });
      return;
    }

    var toggle = e.target.closest('[data-toggle]');
    if (toggle) {
      var id = toggle.getAttribute('data-toggle');
      var el = document.getElementById(id);
      if (el) {
        var wasHidden = el.style.display === 'none' || !el.style.display;
        el.style.display = wasHidden ? 'block' : 'none';
        toggle.textContent = wasHidden ? '− Cancel' : '+ Add new address';
      }
      return;
    }

    var editBtn = e.target.closest('[data-edit-address]');
    if (editBtn) {
      var pk = editBtn.getAttribute('data-edit-address');
      var form = document.querySelector('[data-edit-address-form="' + pk + '"]');
      if (form) form.style.display = 'block';
      return;
    }

    var cancelBtn = e.target.closest('[data-cancel-edit-address]');
    if (cancelBtn) {
      var pk2 = cancelBtn.getAttribute('data-cancel-edit-address');
      var form2 = document.querySelector('[data-edit-address-form="' + pk2 + '"]');
      if (form2) form2.style.display = 'none';
      return;
    }

    var copy = e.target.closest('[data-copy]');
    if (copy) {
      copyText(copy.getAttribute('data-copy'));
      return;
    }

    var copyAll = e.target.closest('[data-copy-all]');
    if (copyAll) {
      copyText(copyAll.getAttribute('data-copy-all'));
    }
  });
})();