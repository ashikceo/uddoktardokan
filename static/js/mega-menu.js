/* ============================================================
   Uddokta Dokan — CATEGORIES mega menu + mobile category drawer
   Vanilla JS, no globals. Data comes from #udCategoryTreeData
   (rendered by Django's json_script filter).
   ============================================================ */
(function () {
  'use strict';

  var OPEN_DELAY = 80;
  var CLOSE_DELAY = 200;

  function readTree() {
    var el = document.getElementById('udCategoryTreeData');
    if (!el) return [];
    try {
      return JSON.parse(el.textContent) || [];
    } catch (e) {
      return [];
    }
  }

  /* ---------------------------------------------------------
     Desktop mega menu
     --------------------------------------------------------- */
  function initDesktop() {
    var li = document.querySelector('.ud-mega-li');
    if (!li || li.getAttribute('data-udm-ready')) return;
    var trigger = li.querySelector('.ud-mega-trigger');
    var panel = li.querySelector('.ud-mega');
    if (!trigger || !panel) return;
    li.setAttribute('data-udm-ready', '1');

    var parents = Array.prototype.slice.call(panel.querySelectorAll('.ud-mega__parent'));
    var panels = Array.prototype.slice.call(panel.querySelectorAll('.ud-mega__panel'));
    var openTimer = null;
    var closeTimer = null;

    function setActive(index) {
      parents.forEach(function (p, i) { p.classList.toggle('is-active', i === index); });
      panels.forEach(function (p, i) { p.classList.toggle('is-active', i === index); });
    }
    function firstWithChildren() {
      for (var i = 0; i < parents.length; i++) {
        if (parents[i].getAttribute('data-udm-has-children') === '1') return i;
      }
      return parents.length ? 0 : -1;
    }
    function position() {
      panel.style.left = '0px';
      var rect = panel.getBoundingClientRect();
      var pad = 10;
      var shift = 0;
      if (rect.right > window.innerWidth - pad) shift = (window.innerWidth - pad) - rect.right;
      if (rect.left + shift < pad) shift = pad - rect.left;
      panel.style.left = shift + 'px';
    }
    function open() {
      clearTimeout(closeTimer);
      clearTimeout(openTimer);
      if (panel.classList.contains('is-open')) return;
      panel.classList.add('is-open');
      li.classList.add('is-open');
      trigger.setAttribute('aria-expanded', 'true');
      if (!panel.querySelector('.ud-mega__panel.is-active')) {
        var i = firstWithChildren();
        if (i >= 0) setActive(i);
      }
      position();
    }
    function close() {
      clearTimeout(openTimer);
      clearTimeout(closeTimer);
      panel.classList.remove('is-open');
      li.classList.remove('is-open');
      trigger.setAttribute('aria-expanded', 'false');
    }
    function openSoon() { clearTimeout(openTimer); openTimer = setTimeout(open, OPEN_DELAY); }
    function closeSoon() { clearTimeout(openTimer); clearTimeout(closeTimer); closeTimer = setTimeout(close, CLOSE_DELAY); }

    var canHover = window.matchMedia && window.matchMedia('(hover: hover)').matches;
    if (canHover) {
      trigger.addEventListener('mouseenter', openSoon);
      trigger.addEventListener('mouseleave', closeSoon);
      panel.addEventListener('mouseenter', function () { clearTimeout(openTimer); clearTimeout(closeTimer); });
      panel.addEventListener('mouseleave', closeSoon);
    }

    trigger.addEventListener('click', function (e) {
      e.preventDefault();
      if (panel.classList.contains('is-open')) close(); else open();
    });

    parents.forEach(function (p, i) {
      var hasKids = p.getAttribute('data-udm-has-children') === '1';
      var link = p.querySelector('.ud-mega__parent-link');
      p.addEventListener('mouseenter', function () { if (hasKids) setActive(i); });
      if (link) link.addEventListener('focus', function () { if (hasKids) setActive(i); });
    });

    panel.addEventListener('keydown', function (e) {
      if (e.key === 'Escape') { close(); trigger.focus(); return; }
      if (e.key === 'ArrowDown' || e.key === 'ArrowUp') {
        var active = parents.findIndex(function (p) { return p.classList.contains('is-active'); });
        var next = e.key === 'ArrowDown' ? active + 1 : active - 1;
        if (next < 0) next = 0;
        if (next >= parents.length) next = parents.length - 1;
        var link = parents[next] && parents[next].querySelector('.ud-mega__parent-link');
        if (link) { link.focus(); e.preventDefault(); }
      }
    });

    document.addEventListener('click', function (e) { if (!li.contains(e.target)) close(); });
    document.addEventListener('keydown', function (e) { if (e.key === 'Escape') close(); });
    window.addEventListener('resize', function () { if (panel.classList.contains('is-open')) position(); });

    setActive(firstWithChildren());
  }

  /* ---------------------------------------------------------
     Mobile drill-down drawer
     --------------------------------------------------------- */
  function initMobile() {
    var drawer = document.getElementById('udCatDrawer');
    if (!drawer || drawer.getAttribute('data-udm-ready')) return;
    var body = drawer.querySelector('[data-udm-body]');
    if (!body) return;
    drawer.setAttribute('data-udm-ready', '1');

    var tree = readTree();
    var titleEl = drawer.querySelector('[data-udm-title]');
    var backBtn = drawer.querySelector('[data-udm-back]');
    var search = drawer.querySelector('[data-udm-search]');
    var stack = [];

    function renderNodes(nodes, label) {
      titleEl.textContent = label;
      backBtn.hidden = stack.length <= 1;
      body.innerHTML = '';
      var frag = document.createDocumentFragment();
      nodes.forEach(function (node) {
        var row = document.createElement('div');
        row.className = 'ud-cat-drawer__item';

        var a = document.createElement('a');
        a.className = 'ud-cat-drawer__item-link';
        a.href = node.url;
        var name = document.createElement('span');
        name.textContent = node.name;
        a.appendChild(name);
        if (node.product_count) {
          var c = document.createElement('span');
          c.className = 'ud-cat-drawer__count';
          c.textContent = node.product_count;
          a.appendChild(c);
        }
        row.appendChild(a);

        if (node.children && node.children.length) {
          var b = document.createElement('button');
          b.type = 'button';
          b.className = 'ud-cat-drawer__item-more';
          b.setAttribute('aria-label', 'Open ' + node.name);
          b.innerHTML = '<i class="fa fa-angle-right"></i>';
          b.addEventListener('click', function () {
            stack.push({ nodes: node.children, label: node.name });
            renderNodes(node.children, node.name);
            body.scrollTop = 0;
          });
          row.appendChild(b);
        }
        frag.appendChild(row);
      });
      body.appendChild(frag);
    }

    function renderLevel() {
      var level = stack[stack.length - 1];
      if (level) renderNodes(level.nodes, level.label);
    }

    function open() {
      stack = [{ nodes: tree, label: 'Categories' }];
      if (search) search.value = '';
      renderNodes(tree, 'Categories');
      drawer.classList.add('is-open');
      drawer.setAttribute('aria-hidden', 'false');
      document.body.classList.add('ud-cat-lock');
      body.scrollTop = 0;
    }
    function close() {
      drawer.classList.remove('is-open');
      drawer.setAttribute('aria-hidden', 'true');
      document.body.classList.remove('ud-cat-lock');
    }
    function goBack() {
      if (stack.length > 1) { stack.pop(); renderLevel(); body.scrollTop = 0; }
    }

    function searchAll(q) {
      q = q.trim().toLowerCase();
      if (!q) { renderLevel(); return; }
      var out = [];
      (function walk(nodes, path) {
        nodes.forEach(function (n) {
          var p = path.concat(n.name);
          if (n.name.toLowerCase().indexOf(q) >= 0) out.push({ node: n, path: p });
          if (n.children && n.children.length) walk(n.children, p);
        });
      })(tree, []);

      titleEl.textContent = 'Search';
      backBtn.hidden = false;
      body.innerHTML = '';
      if (!out.length) {
        var empty = document.createElement('div');
        empty.className = 'ud-cat-drawer__empty';
        empty.textContent = 'No categories found.';
        body.appendChild(empty);
        return;
      }
      out.slice(0, 60).forEach(function (m) {
        var row = document.createElement('div');
        row.className = 'ud-cat-drawer__item';
        var a = document.createElement('a');
        a.className = 'ud-cat-drawer__item-link ud-cat-drawer__item-link--search';
        a.href = m.node.url;
        var nm = document.createElement('span');
        nm.textContent = m.node.name;
        a.appendChild(nm);
        if (m.path.length > 1) {
          var crumb = document.createElement('span');
          crumb.className = 'ud-cat-drawer__crumb';
          crumb.textContent = m.path.slice(0, -1).join(' / ');
          a.appendChild(crumb);
        }
        row.appendChild(a);
        body.appendChild(row);
      });
    }

    Array.prototype.forEach.call(drawer.querySelectorAll('[data-udm-close]'), function (el) {
      el.addEventListener('click', close);
    });
    if (backBtn) {
      backBtn.addEventListener('click', function () {
        if (titleEl.textContent === 'Search') {
          if (search) search.value = '';
          renderLevel();
        } else {
          goBack();
        }
      });
    }
    if (search) {
      var t = null;
      search.addEventListener('input', function () {
        clearTimeout(t);
        var v = search.value;
        t = setTimeout(function () { searchAll(v); }, 150);
      });
    }
    document.addEventListener('keydown', function (e) {
      if (e.key === 'Escape' && drawer.classList.contains('is-open')) close();
    });

    var btn = document.getElementById('udMobileCatBtn');
    if (btn) btn.addEventListener('click', function (e) { e.preventDefault(); open(); });
  }

  function init() {
    initDesktop();
    initMobile();
  }

  if (document.readyState === 'loading') {
    document.addEventListener('DOMContentLoaded', init);
  } else {
    init();
  }
})();
