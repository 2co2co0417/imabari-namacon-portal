// 右カラム：PCは最初からopen、スマホは閉じて開始
(function initAsideAccordion(){
  const isPC = window.matchMedia('(min-width: 921px)').matches;
  document.querySelectorAll('details.acc[data-acc="pc-open"]').forEach(d => {
    if(isPC) d.setAttribute('open', '');
    else d.removeAttribute('open');
  });
})();

// ハンバーガーメニュー
(function initHamburgerMenu(){
  const toggle = document.querySelector('.menu-toggle');
  const nav = document.getElementById('global-nav');

  if(!toggle || !nav) return;

  toggle.addEventListener('click', function(){
    nav.classList.toggle('open');
  });

  document.addEventListener('click', function(e){
    if(!nav.contains(e.target) && !toggle.contains(e.target)){
      nav.classList.remove('open');
    }
  });

})();