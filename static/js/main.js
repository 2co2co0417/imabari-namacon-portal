// 右カラム：PCは最初からopen、スマホは閉じて開始
(function initAsideAccordion(){
  const isPC = window.matchMedia('(min-width: 921px)').matches;
  document.querySelectorAll('details.acc[data-acc="pc-open"]').forEach(d => {
    if(isPC) d.setAttribute('open', '');
    else d.removeAttribute('open');
  });
})();