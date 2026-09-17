/* Dashboard: My Products — bulk selection + row action menus.
   Plain (non-async) page navigation: no loading states are fabricated. */
(function () {
    'use strict';

    function initBulkSelection() {
        var selectAll = document.getElementById('ud-products-select-all');
        var bar = document.getElementById('ud-products-bulk-bar');
        var countEl = document.getElementById('ud-products-selected-count');
        var checkboxes = Array.prototype.slice.call(
            document.querySelectorAll('.ud-product-checkbox')
        );
        if (!bar || !checkboxes.length) { return; }

        function refresh() {
            var checked = checkboxes.filter(function (cb) { return cb.checked; }).length;
            bar.hidden = checked === 0;
            if (countEl) {
                countEl.textContent = checked + ' selected';
            }
            if (selectAll) {
                selectAll.checked = checked === checkboxes.length;
                selectAll.indeterminate = checked > 0 && checked < checkboxes.length;
            }
        }

        if (selectAll) {
            selectAll.addEventListener('change', function () {
                checkboxes.forEach(function (cb) { cb.checked = selectAll.checked; });
                refresh();
            });
        }
        checkboxes.forEach(function (cb) { cb.addEventListener('change', refresh); });
        refresh();
    }

    function initActionMenus() {
        var triggers = Array.prototype.slice.call(
            document.querySelectorAll('.ud-actions-trigger')
        );
        if (!triggers.length) { return; }

        function menuFor(trigger) {
            var id = trigger.getAttribute('aria-controls');
            return id ? document.getElementById(id) : null;
        }

        function closeMenu(trigger, restoreFocus) {
            var menu = menuFor(trigger);
            if (!menu) { return; }
            menu.hidden = true;
            trigger.setAttribute('aria-expanded', 'false');
            if (restoreFocus) { trigger.focus(); }
        }

        function closeAll(except, restoreFocus) {
            triggers.forEach(function (t) {
                if (t !== except) { closeMenu(t, restoreFocus); }
            });
        }

        function openMenu(trigger) {
            var menu = menuFor(trigger);
            if (!menu) { return; }
            closeAll(trigger, false);
            menu.hidden = false;
            trigger.setAttribute('aria-expanded', 'true');
            var first = menu.querySelector('[role="menuitem"]');
            if (first) { first.focus(); }
        }

        triggers.forEach(function (trigger) {
            trigger.addEventListener('click', function (event) {
                event.stopPropagation();
                var menu = menuFor(trigger);
                if (menu && !menu.hidden) {
                    closeMenu(trigger, false);
                } else {
                    openMenu(trigger);
                }
            });

            var menu = menuFor(trigger);
            if (!menu) { return; }
            menu.addEventListener('keydown', function (event) {
                var items = Array.prototype.slice.call(
                    menu.querySelectorAll('[role="menuitem"]')
                );
                var index = items.indexOf(document.activeElement);
                if (event.key === 'ArrowDown') {
                    event.preventDefault();
                    (items[index + 1] || items[0]).focus();
                } else if (event.key === 'ArrowUp') {
                    event.preventDefault();
                    (items[index - 1] || items[items.length - 1]).focus();
                } else if (event.key === 'Home') {
                    event.preventDefault();
                    if (items[0]) { items[0].focus(); }
                } else if (event.key === 'End') {
                    event.preventDefault();
                    if (items[items.length - 1]) { items[items.length - 1].focus(); }
                } else if (event.key === 'Escape') {
                    event.preventDefault();
                    closeMenu(trigger, true);
                } else if (event.key === 'Tab') {
                    closeMenu(trigger, false);
                }
            });
        });

        document.addEventListener('click', function (event) {
            if (!event.target.closest('.ud-product-actions')) {
                closeAll(null, false);
            }
        });
        document.addEventListener('keydown', function (event) {
            if (event.key === 'Escape') { closeAll(null, false); }
        });
    }

    function initConfirms() {
        Array.prototype.forEach.call(
            document.querySelectorAll('[data-ud-confirm]'),
            function (el) {
                el.addEventListener('click', function (event) {
                    if (!window.confirm(el.getAttribute('data-ud-confirm'))) {
                        event.preventDefault();
                    }
                });
            }
        );
    }

    function init() {
        initBulkSelection();
        initActionMenus();
        initConfirms();
    }

    if (document.readyState === 'loading') {
        document.addEventListener('DOMContentLoaded', init);
    } else {
        init();
    }
})();
