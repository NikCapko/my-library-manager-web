// Управление темой: 'auto' | 'light' | 'dark'
(function () {
    const KEY = 'theme';
    const root = document.documentElement;

    function apply(mode) {
        if (mode === 'auto') {
            root.removeAttribute('data-theme');
        } else {
            root.setAttribute('data-theme', mode);
        }
        // обновляем иконку кнопки, если она есть
        const btn = document.getElementById('theme-toggle');
        if (btn) {
            btn.textContent = mode === 'dark' ? '🌙' : mode === 'light' ? '☀️' : '🖥';
            btn.title = 'Тема: ' + mode;
        }
    }

    function current() {
        return localStorage.getItem(KEY) || 'auto';
    }

    function cycle() {
        const order = ['auto', 'light', 'dark'];
        const next = order[(order.indexOf(current()) + 1) % order.length];
        localStorage.setItem(KEY, next);
        apply(next);
    }

    // Применяем сразу (важно — до отрисовки, чтобы не мигало)
    apply(current());

    // Вешаем обработчик после загрузки DOM
    document.addEventListener('DOMContentLoaded', function () {
        const btn = document.getElementById('theme-toggle');
        if (btn) {
            apply(current());
            btn.addEventListener('click', cycle);
        }
    });

    // Реагируем на смену системной темы, если выбран 'auto'
    if (window.matchMedia) {
        window.matchMedia('(prefers-color-scheme: dark)')
            .addEventListener('change', function () {
                if (current() === 'auto') apply('auto');
            });
    }
})();
