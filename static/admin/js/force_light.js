(function () {
    // Remove dark-mode immediately and block it from being re-added
    function stripDark() {
        document.documentElement.classList.remove('dark-mode');
        document.body && document.body.classList.remove('dark-mode');
    }

    stripDark();

    // Clear every localStorage key that AdminLTE / Jazzmin use for dark mode
    ['jazzmin-color-scheme', 'jazzmin-theme', 'adminlte-theme',
     'bs-color-scheme', 'darkMode', 'dark_mode', 'theme'].forEach(function (k) {
        try { localStorage.removeItem(k); } catch (_) {}
    });
    // Jazzmin specifically looks for this key = 'light'
    try { localStorage.setItem('jazzmin-color-scheme', 'light'); } catch (_) {}

    // Also override localStorage.setItem to prevent dark mode being stored again
    var _setItem = localStorage.setItem.bind(localStorage);
    localStorage.setItem = function (key, value) {
        if (/theme|dark|color.scheme/i.test(key) && /dark/i.test(value)) return;
        _setItem(key, value);
    };

    // Watch for the class being added back by JS and remove it instantly
    var observer = new MutationObserver(function (mutations) {
        mutations.forEach(function (m) {
            if (m.type === 'attributes' && m.attributeName === 'class') {
                var el = m.target;
                if (el.classList.contains('dark-mode')) {
                    el.classList.remove('dark-mode');
                }
            }
        });
    });

    document.addEventListener('DOMContentLoaded', function () {
        stripDark();
        observer.observe(document.body, { attributes: true, attributeFilter: ['class'] });
        observer.observe(document.documentElement, { attributes: true, attributeFilter: ['class'] });
    });
})();
