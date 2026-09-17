/* Uddokta Dokan — Store Editor interactions (scoped, dependency-free) */
(function () {
  'use strict';

  var page = document.querySelector('.ud-store-page');
  if (!page) return;

  var form = page.querySelector('#sdStoreForm');
  if (!form) return;

  var unsaved = page.querySelector('.sd-unsaved');
  var dirty = false;

  function markDirty() {
    if (dirty) return;
    dirty = true;
    if (unsaved) unsaved.classList.add('sd-show');
  }

  /* ── Live image previews ──────────────────────────────────────── */
  var previewConfig = [
    { input: 'logo', preview: 'sdPrevLogo', wrap: 'sdWrapLogo' },
    { input: 'profile_image', preview: 'sdPrevProfile', wrap: 'sdWrapProfile' },
    { input: 'banner', preview: 'sdPrevBanner', wrap: 'sdWrapBanner' },
    { input: 'new_banners', preview: 'sdPrevNewBanners', wrap: 'sdWrapNewBanners' }
  ];

  previewConfig.forEach(function (cfg) {
    var input = form.querySelector('input[name="' + cfg.input + '"]');
    if (!input) return;
    input.addEventListener('change', function () {
      var preview = page.querySelector('#' + cfg.preview);
      var wrap = page.querySelector('#' + cfg.wrap);
      if (!preview) return;
      var remove = page.querySelector('[data-sd-remove="' + cfg.input + '"]');
      /* picking a new file cancels the "remove" flag for that field */
      if (remove) {
        var box = page.querySelector('#' + remove.getAttribute('data-sd-box'));
        if (box) {
          box.checked = false;
          remove.classList.remove('is-active');
        }
        setMark(remove, false);
      }
      if (input.files && input.files.length) {
        preview.src = URL.createObjectURL(input.files[0]);
        if (wrap) wrap.classList.remove('ud-marked');
        if (cfg.input === 'new_banners') renderNewBannerPreviews(input.files);
      }
      markDirty();
    });
    /* drag highlight */
    input.addEventListener('dragover', function () { wrap && wrap.classList.add('sd-drag'); });
    input.addEventListener('dragleave', function () { wrap && wrap.classList.remove('sd-drag'); });
    input.addEventListener('drop', function () { wrap && wrap.classList.remove('sd-drag'); });

    var removeBtn = page.querySelector('[data-sd-remove="' + cfg.input + '"]');
    if (removeBtn && cfg.input !== 'new_banners') {
      removeBtn.addEventListener('click', function () {
        var box = page.querySelector('#' + removeBtn.getAttribute('data-sd-box'));
        if (!box) return;
        box.checked = !box.checked;
        removeBtn.classList.toggle('is-active', box.checked);
        setMark(removeBtn, box.checked);
        if (wrap) wrap.classList.toggle('ud-marked', box.checked);
        /* if user removes while a new file was picked, clear the new file */
        if (box.checked && input.files && input.files.length) {
          input.value = '';
          var preview = page.querySelector('#' + cfg.preview);
          if (preview && preview.dataset.current) preview.src = preview.dataset.current;
        }
        markDirty();
      });
    }
  });

  /* mark container "to be removed" (dim + strikethrough text) */
  function setMark(btn, active) {
    var target = btn && btn.getAttribute('data-sd-target');
    var el = target && page.querySelector(target);
    if (el) el.classList.toggle('ud-marked', active);
  }

  /* remove buttons for existing extra banners */
  page.querySelectorAll('[data-sd-banner-remove]').forEach(function (btn) {
    btn.addEventListener('click', function () {
      var box = page.querySelector('#' + btn.getAttribute('data-sd-banner-remove'));
      if (!box) return;
      box.checked = !box.checked;
      btn.classList.toggle('is-active', box.checked);
      var row = btn.closest('.sd-banner-item');
      if (row) row.classList.toggle('ud-marked', box.checked);
      markDirty();
    });
  });

  /* render previews for newly added extra banners */
  function renderNewBannerPreviews(files) {
    var container = page.querySelector('#sdNewBannerPreviews');
    if (!container) return;
    container.innerHTML = '';
    Array.prototype.forEach.call(files, function (f) {
      if (!f.type.match(/^image\//)) return;
      var img = document.createElement('img');
      img.src = URL.createObjectURL(f);
      img.style.maxHeight = '70px';
      img.style.borderRadius = '8px';
      img.style.border = '1px solid #e6e4ec';
      container.appendChild(img);
    });
    container.classList.add('sd-show-inline');
  }

  /* ── Character counter (description) ──────────────────────────── */
  var desc = form.querySelector('#sdDescription');
  var counter = page.querySelector('#sdDescriptionCounter');
  if (desc && counter) {
    function updateCounter() {
      counter.textContent = desc.value.length.toLocaleString('en-US') + ' characters';
    }
    desc.addEventListener('input', function () {
      updateCounter();
      markDirty();
    });
    updateCounter();
  }

  /* ── Dirty state tracking ─────────────────────────────────────── */
  form.addEventListener('input', markDirty);
  form.addEventListener('change', markDirty);

  window.addEventListener('beforeunload', function (e) {
    if (!dirty) return;
    e.preventDefault();
    e.returnValue = '';
  });

  /* hide the unsaved chip right after a successful submit */
  form.addEventListener('submit', function () {
    dirty = false;
    if (unsaved) unsaved.classList.remove('sd-show');
  });

  /* scroll-spy for the section nav */
  var navLinks = page.querySelectorAll('.sd-nav a[data-sd-scroll]');
  if (navLinks.length) {
    var sections = Array.prototype.map.call(navLinks, function (a) {
      return page.querySelector(a.getAttribute('data-sd-scroll'));
    }).filter(Boolean);

    var spy = function () {
      var pos = window.pageYOffset + 130;
      var current = sections[0];
      sections.forEach(function (sec) {
        if (sec && sec.offsetTop <= pos) current = sec;
      });
      navLinks.forEach(function (a) {
        a.classList.toggle('sd-nav-active', a.getAttribute('data-sd-scroll') === '#' + current.id);
      });
    };
    window.addEventListener('scroll', spy, { passive: true });
    spy();

    navLinks.forEach(function (a) {
      a.addEventListener('click', function (e) {
        var target = page.querySelector(a.getAttribute('data-sd-scroll'));
        if (!target) return;
        e.preventDefault();
        var top = target.getBoundingClientRect().top + window.pageYOffset - 90;
        window.scrollTo({ top: top, behavior: 'smooth' });
      });
    });
  }

  /* focus first invalid control on manual submit if browser misses it */
  form.addEventListener('submit', function () {
    if (!form.checkValidity()) {
      var first = form.querySelector(':invalid');
      if (first) first.focus();
    }
  });
})();