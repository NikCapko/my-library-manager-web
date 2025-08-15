// TOC: на десктопе раскрыт, на мобильном — свернут
(function () {
    const details = document.querySelector('#bookToc details');
    if (!details) return;
    const mq = window.matchMedia('(min-width: 901px)');
    const apply = () => { details.open = mq.matches; };
    apply();
    mq.addEventListener('change', apply);
})();

// «Наверх»
const scrollBtn = document.getElementById('scrollTopBtn');
if (scrollBtn) {
    window.addEventListener('scroll', () => {
        if (document.body.scrollTop > window.innerHeight / 2 ||
            document.documentElement.scrollTop > window.innerHeight / 2) {
            scrollBtn.classList.add('show');
        } else {
            scrollBtn.classList.remove('show');
        }
    });
    scrollBtn.addEventListener('click', () => {
        window.scrollTo({ top: 0, behavior: 'smooth' });
    });
}

// Активный пункт TOC
(function () {
    const toc = document.getElementById('bookToc');
    if (!toc) return;

    const links = Array.from(toc.querySelectorAll('a[href^="#"]'));
    if (!links.length) return;

    const targets = links
        .map(a => {
            const id = decodeURIComponent(a.getAttribute('href').slice(1));
            const el = document.getElementById(id);
            return el ? { link: a, el } : null;
        })
        .filter(Boolean);

    if (!targets.length) return;

    const onScroll = () => {
        // ближайший заголовок выше середины окна — активный
        const fromTop = window.scrollY + 80;
        let current = targets[0];
        for (const t of targets) {
            if (t.el.offsetTop <= fromTop) current = t;
            else break;
        }
        links.forEach(a => a.classList.remove('active'));
        current.link.classList.add('active');
    };
    window.addEventListener('scroll', onScroll, { passive: true });
    onScroll();
})();

// Режим stacked: раскрытие/скрытие RU по клику
(function () {
    const root = document.getElementById('stacked');
    if (!root) return;

    // Клик по кнопке «RU» у строки
    root.addEventListener('click', (e) => {
        const btn = e.target.closest('.stacked-toggle');
        if (!btn) return;
        const targetId = btn.dataset.target;
        const target = document.getElementById(targetId);
        if (!target) return;
        const expanded = btn.getAttribute('aria-expanded') === 'true';
        if (expanded) {
            target.hidden = true;
            btn.setAttribute('aria-expanded', 'false');
        } else {
            target.hidden = false;
            btn.setAttribute('aria-expanded', 'true');
        }
    });

    // Глобальный переключатель «Показать все RU / Скрыть все RU»
    const toggleAll = document.getElementById('stackedToggleAll');
    if (toggleAll) {
        toggleAll.addEventListener('click', () => {
            const isCollapsed = toggleAll.dataset.state !== 'expanded';
            const buttons = root.querySelectorAll('.stacked-toggle');
            const rus = root.querySelectorAll('.stacked-ru');
            if (isCollapsed) {
                rus.forEach(el => { el.hidden = false; });
                buttons.forEach(b => b.setAttribute('aria-expanded', 'true'));
                toggleAll.dataset.state = 'expanded';
                toggleAll.textContent = 'Скрыть все RU';
            } else {
                rus.forEach(el => { el.hidden = true; });
                buttons.forEach(b => b.setAttribute('aria-expanded', 'false'));
                toggleAll.dataset.state = 'collapsed';
                toggleAll.textContent = 'Показать все RU';
            }
        });
    }
})();
