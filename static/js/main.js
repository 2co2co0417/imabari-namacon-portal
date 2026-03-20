// 右カラム：PCは最初からopen、スマホは閉じて開始
(function initAsideAccordion(){
  const isPC = window.matchMedia('(min-width: 921px)').matches;
  document.querySelectorAll('details.acc[data-acc="pc-open"]').forEach(d => {
    if (isPC) d.setAttribute('open', '');
    else d.removeAttribute('open');
  });
})();

// ハンバーガーメニュー
(function initHamburgerMenu(){
  const toggle = document.querySelector('.menu-toggle');
  const nav = document.getElementById('global-nav');

  if (!toggle || !nav) return;

  function closeMenu(){
    nav.classList.remove('open');
    toggle.setAttribute('aria-expanded', 'false');
  }

  function openMenu(){
    nav.classList.add('open');
    toggle.setAttribute('aria-expanded', 'true');
  }

  toggle.addEventListener('click', function(e){
    e.stopPropagation();
    if (nav.classList.contains('open')) closeMenu();
    else openMenu();
  });

  document.addEventListener('click', function(e){
    if (!nav.contains(e.target) && !toggle.contains(e.target)){
      closeMenu();
    }
  });

  nav.querySelectorAll('a').forEach(link => {
    link.addEventListener('click', function(){
      closeMenu();
    });
  });

  window.addEventListener('resize', function(){
    if (window.innerWidth > 768){
      closeMenu();
    }
  });
})();