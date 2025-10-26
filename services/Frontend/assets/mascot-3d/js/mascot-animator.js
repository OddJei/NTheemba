async function loadSVG(url, id){
  const res = await fetch(url);
  const text = await res.text();
  const doc = new DOMParser().parseFromString(text, "image/svg+xml");
  const svg = doc.documentElement;
  svg.id = id;
  svg.classList.add('mascot-view');
  return svg;
}

function setActiveView(id){
  document.querySelectorAll('.mascot-view').forEach(v => v.classList.remove('is-active'));
  const el = document.getElementById(id);
  if(el) el.classList.add('is-active');
}

function currentViewRoot(){
  return document.querySelector('.mascot-view.is-active') || null;
}

function part(id, root){
  return (root || currentViewRoot())?.querySelector('#'+id);
}

function waveArm(side='right'){
  const root = currentViewRoot();
  const upper = part(`arm-${side}-upper`, root);
  const lower = part(`arm-${side}-lower`, root);
  if(!upper || !lower) return;

  upper.style.transformOrigin = "top center";
  lower.style.transformOrigin = "top center";

  upper.animate(
    [{ transform: "rotate(0deg)" }, { transform: "rotate(-16deg)" }, { transform: "rotate(0deg)"}],
    { duration: 420, iterations: 3, easing: "ease-in-out" }
  );
  lower.animate(
    [{ transform: "rotate(0deg)" }, { transform: "rotate(30deg)" }, { transform: "rotate(0deg)"}],
    { duration: 420, iterations: 3, easing: "ease-in-out" }
  );
}

function nodHead(){
  const h = part('mascot-head');
  if(!h) return;
  h.style.transformOrigin = "center bottom";
  h.animate(
    [{ transform:"rotate(0deg)" }, { transform:"rotate(9deg)" }, { transform:"rotate(0deg)" }],
    { duration: 500, iterations: 2, easing: "ease-in-out" }
  );
}

function look(direction='left'){
  const l = part('eye-left'), r = part('eye-right');
  const offset = (direction==='left') ? -3 : (direction==='right' ? 3 : 0);
  [l, r].forEach(e=>{
    if(!e) return;
    e.animate(
      [{ transform:`translateX(0px)` }, { transform:`translateX(${offset}px)` }, { transform:`translateX(0px)` }],
      { duration: 700, easing:'ease-in-out' }
    );
  });
}

function toggleSmile(on=true){
  const root = currentViewRoot();
  root?.classList.toggle('is-smiling', on);
}

function toggleTalk(on=true){
  const root = currentViewRoot();
  root?.classList.toggle('is-talking', on);
}

function flipTo(viewId){
  const viewer = document.querySelector('.viewer');
  // quick flip illusion
  viewer.classList.remove('flip-y');
  void viewer.offsetWidth; // reflow
  viewer.classList.add('flip-y');
  setTimeout(()=>{ setActiveView(viewId); }, 180);
  setTimeout(()=> viewer.classList.remove('flip-y'), 650);
}

function bindControls(){
  document.getElementById('btn-front').addEventListener('click', ()=> setActiveView('view-front'));
  document.getElementById('btn-back').addEventListener('click', ()=> flipTo('view-back'));
  document.getElementById('btn-left').addEventListener('click', ()=> setActiveView('view-left'));
  document.getElementById('btn-right').addEventListener('click', ()=> setActiveView('view-right'));

  document.getElementById('btn-wave').addEventListener('click', ()=> waveArm('right'));
  document.getElementById('btn-wave-left').addEventListener('click', ()=> waveArm('left'));
  document.getElementById('btn-nod').addEventListener('click', nodHead);
  document.getElementById('btn-look-left').addEventListener('click', ()=> look('left'));
  document.getElementById('btn-look-right').addEventListener('click', ()=> look('right'));
  document.getElementById('btn-smile').addEventListener('click', ()=> toggleSmile(true));
  document.getElementById('btn-neutral').addEventListener('click', ()=> { toggleSmile(false); toggleTalk(false); });
  document.getElementById('btn-talk').addEventListener('click', ()=> toggleTalk(true));

  document.getElementById('btn-pivots').addEventListener('click', ()=>{
    const root = currentViewRoot();
    root?.classList.toggle('show-pivots');
  });
}

async function boot(){
  const stage = document.getElementById('stage');

  const front = await loadSVG('assets/mascot-front.svg', 'view-front');
  const back  = await loadSVG('assets/mascot-back.svg',  'view-back');
  const left  = await loadSVG('assets/mascot-side-left.svg',  'view-left');
  const right = await loadSVG('assets/mascot-side-right.svg', 'view-right');

  stage.append(front, back, left, right);
  setActiveView('view-front');
  bindControls();
}
document.addEventListener('DOMContentLoaded', boot);
