(function(){
const Q=s=>document.querySelector(s),QA=s=>[...document.querySelectorAll(s)];
const IC={today:'<circle cx="12" cy="12" r="4"/><path d="M12 3v2M12 19v2M4.2 4.2l1.4 1.4M18.4 18.4l1.4 1.4M3 12h2M19 12h2M4.2 19.8l1.4-1.4M18.4 5.6l1.4-1.4"/>',mail:'<rect x="3" y="5" width="18" height="14" rx="2"/><path d="m3 7 9 6 9-6"/>',chat:'<path d="M21 12a8 8 0 0 1-11.6 7.1L4 20l1-4.6A8 8 0 1 1 21 12Z"/>',meeting:'<rect x="3" y="6" width="13" height="12" rx="2"/><path d="m16 10 5-3v10l-5-3"/>',protocols:'<path d="M7 3h8l4 4v14H7z"/><path d="M15 3v4h4M10 12h6M10 16h6"/>',calendar:'<rect x="3" y="5" width="18" height="16" rx="2"/><path d="M3 10h18M8 3v4M16 3v4"/>',learning:'<path d="M12 3 2 8l10 5 10-5-10-5Z"/><path d="M6 10.5V16c0 1.5 3 3 6 3s6-1.5 6-3v-5.5"/>',metrics:'<path d="M4 20V10M10 20V4M16 20v-7M22 20H2"/>',profile:'<circle cx="12" cy="8" r="4"/><path d="M4 21a8 8 0 0 1 16 0"/>',connections:'<path d="M9 7V3M15 7V3M7 7h10v4a5 5 0 0 1-10 0V7ZM12 16v5"/>',moon:'<path d="M21 13A9 9 0 1 1 11 3a7 7 0 0 0 10 10Z"/>',sun:'<circle cx="12" cy="12" r="4"/><path d="M12 2v2M12 20v2M2 12h2M20 12h2M5 5l1.5 1.5M17.5 17.5 19 19M5 19l1.5-1.5M17.5 6.5 19 5"/>'};
const svg=k=>`<svg viewBox="0 0 24 24" width="18" height="18" fill="none" stroke="currentColor" stroke-width="1.7" stroke-linecap="round" stroke-linejoin="round" aria-hidden="true">${IC[k]||''}</svg>`;
const LS=(k,v)=>{try{return v===undefined?localStorage.getItem(k):localStorage.setItem(k,v)}catch{return null}};
/* тема */
const setTheme=t=>{document.documentElement.dataset.theme=t;LS('av-theme',t);const b=Q('#ux-theme');if(b)b.innerHTML=svg(t==='dark'?'sun':'moon')};
setTheme(LS('av-theme')||'light');
/* ключ администратора: нужен, только если на сервере задан AVATAR_ADMIN_KEY */
const _api=window.api;
window.api=async function(p,o={}){
  const call=()=>{const k=sessionStorage.getItem('av-admin');return _api(p,{...o,headers:{'Content-Type':'application/json',...(k?{'X-Admin-Key':k}:{})}})};
  try{return await call()}catch(e){
    if(/AVATAR_ADMIN_KEY/.test(String(e.message))){const k=prompt('Введите ключ администратора (переменная AVATAR_ADMIN_KEY на сервере)');if(k){sessionStorage.setItem('av-admin',k.trim());return await call()}}
    throw e}};
/* иконки в меню */
const _nav=window.nav;
window.nav=function(c){_nav(c);QA('#nav button').forEach(b=>{const n=b.querySelector('.n'),lab=b.textContent.replace(n?n.textContent:'','').trim();b.innerHTML=`<span class="ni">${svg(b.dataset.v)}</span><span class="nt">${lab}</span>${n?n.outerHTML:''}`})};
/* плавная смена вкладок и счётчики */
const reduce=matchMedia('(prefers-reduced-motion: reduce)').matches;
const countUp=()=>{if(reduce)return;QA('.kpi b').forEach(el=>{const m=/^(\d+)(%?)$/.exec(el.textContent.trim());if(!m)return;const to=+m[1],suf=m[2],t0=performance.now(),d=650;const step=t=>{const k=Math.min(1,(t-t0)/d),e=1-Math.pow(1-k,3);el.textContent=Math.round(to*e)+suf;if(k<1)requestAnimationFrame(step)};requestAnimationFrame(step)})};
const _render=window.render;
window.render=async function(){const v=Q('#view');v.classList.remove('vin');void v.offsetWidth;v.classList.add('vin');await _render();countUp()};
/* кнопки в шапке */
const ctl=Q('.ctl');
if(ctl){ctl.insertAdjacentHTML('beforeend',`<button class="ghost ico-btn" id="ux-stage" title="Сцена аватара для видеозвонка (МТС Линк, Zoom, Дион, Телемост)">${svg('meeting')}<span>Режим звонка</span></button><button class="ghost ico-btn" id="ux-theme" aria-label="Сменить тему"></button>`);
  Q('#ux-theme').innerHTML=svg(document.documentElement.dataset.theme==='dark'?'sun':'moon');
  Q('#ux-theme').onclick=()=>setTheme(document.documentElement.dataset.theme==='dark'?'light':'dark');
  Q('#ux-stage').onclick=()=>window.open(`/static/stage.html?pid=${encodeURIComponent(S.pid)}&today=${encodeURIComponent(S.today)}`,'avatar-stage','width=1280,height=760')}
/* «Встреча»: подключение к видеоплатформам */
const _meet=VIEW.meeting;
VIEW.meeting=async()=>{await _meet();const P_=window.AV_PLATFORMS;if(!P_)return;
  const keys=Object.keys(P_);let cur=LS('av-plat')&&P_[LS('av-plat')]?LS('av-plat'):'mts';
  const html=`<div class="card" id="plat" style="margin-top:16px"><div class="row"><h2 class="sp">Подключение к видеозвонку</h2><button id="plat-open">Открыть сцену аватара</button><button class="ghost" id="plat-chk">Проверить браузер</button></div>
   <p class="muted" style="margin-bottom:0">Сцена — отдельное окно с аватаром, субтитрами и голосом. Его показывают в звонке как вкладку со звуком либо выводят через виртуальную камеру.</p>
   <div class="plat-tabs" id="plat-tabs">${keys.map(k=>`<button data-k="${k}" class="${k===cur?'on':''}">${P_[k].name}</button>`).join('')}</div><div class="plat-box" id="plat-box"></div><div id="plat-res" style="margin-top:10px"></div></div>`;
  Q('#view').insertAdjacentHTML('beforeend',html);
  const draw=()=>{Q('#plat-box').innerHTML=window.AV_PLATFORM_TEXT(cur);QA('#plat-tabs button').forEach(b=>b.classList.toggle('on',b.dataset.k===cur))};draw();
  Q('#plat-tabs').onclick=e=>{const b=e.target.closest('button');if(!b)return;cur=b.dataset.k;LS('av-plat',cur);draw()};
  Q('#plat-open').onclick=()=>window.open(`/static/stage.html?pid=${encodeURIComponent(S.pid)}&today=${encodeURIComponent(S.today)}&platform=${cur}`,'avatar-stage','width=1280,height=760');
  Q('#plat-chk').onclick=async()=>{const R=window.SpeechRecognition||window.webkitSpeechRecognition,md=navigator.mediaDevices,rows=[['Озвучка ответов (speechSynthesis)',!!window.speechSynthesis],['Голосовой ввод (SpeechRecognition)',!!R],['Показ вкладки (getDisplayMedia)',!!(md&&md.getDisplayMedia)],['Работает в Chrome или Яндекс Браузере',/Chrome|YaBrowser|Edg/.test(navigator.userAgent)]];
    try{const r=await fetch('/api/status');rows.push(['Сервер аватара отвечает',r.ok])}catch{rows.push(['Сервер аватара отвечает',false])}
    Q('#plat-res').innerHTML=rows.map(r=>`<div class="chk ${r[1]?'ok':'no'}"><i></i>${r[0]}</div>`).join('')}};
/* «Подключения»: проверка и привязка Telegram */
const _conn=VIEW.connections;
VIEW.connections=async()=>{await _conn();
  let ex=null;try{ex=await fetch('/api/extras').then(r=>r.ok?r.json():null)}catch{}
  const box=document.createElement('div');box.className='card';box.style.marginTop='16px';box.id='tgx';
  if(!ex){box.innerHTML='<h2>Telegram: проверка и привязка</h2><p class="muted">Серверные расширения не подключены. Запускайте приложение командой <code>uvicorn app.main:app</code> (или <code>python run.py</code>), тогда здесь появятся проверка токена и привязка чата.</p>';Q('#view').appendChild(box);return}
  box.innerHTML=`<div class="row"><h2 class="sp">Telegram: проверка и привязка</h2><span class="tag ${ex.telegram_env?'ok':'gray'}">${ex.telegram_env?'токен из переменной TELEGRAM_BOT_TOKEN':'токен из интерфейса'}</span>${ex.admin_protected?'<span class="tag ok">защищено ключом администратора</span>':'<span class="tag warn">без ключа администратора</span>'}</div>
   <p class="muted">Токен создаёт @BotFather (команда /newbot). Для публичного стенда задайте его переменной окружения, а не в интерфейсе.</p>
   <div class="row"><button id="tg-test">Проверить токен</button><span id="tg-res" class="muted"></span></div>
   <h3>Привязать чат к руководителю</h3>
   <p class="muted">1. Откройте своего бота в Telegram и отправьте ему любое сообщение. 2. Нажмите «Обновить» и выберите чат. 3. Выберите руководителя и нажмите «Привязать».</p>
   <div class="row"><button class="ghost sm" id="tg-ref">Обновить список</button><span id="tg-seen" class="seen"></span></div>
   <div class="row" style="margin-top:8px"><label>Руководитель<select id="tg-pid">${S.profiles.map(p=>`<option value="${p.id}" ${p.id===S.pid?'selected':''}>${esc(p.name)}</option>`).join('')}</select></label><label>chat_id<input id="tg-chat" placeholder="например 123456789"></label><button id="tg-link">Привязать</button><button class="ghost" id="tg-send">Отправить тест</button></div>`;
  Q('#view').appendChild(box);
  const res=(t,ok)=>{const e=Q('#tg-res');e.textContent=t;e.style.color=ok===undefined?'':ok?'var(--ok)':'var(--bad)'};
  const seen=async()=>{try{const r=await api('/telegram/status');Q('#tg-seen').innerHTML=r.seen.length?r.seen.map(s=>`<button data-c="${esc(s.chat_id)}">${esc(s.chat_id)} · ${esc(s.text||'нажатие кнопки')} · ${esc(s.ts)}</button>`).join(''):'<span class="muted">Пока никто не писал боту</span>'}catch{}};
  Q('#tg-seen').onclick=e=>{const b=e.target.closest('button');if(b)Q('#tg-chat').value=b.dataset.c};
  Q('#tg-ref').onclick=seen;seen();
  Q('#tg-test').onclick=async()=>{res('Проверяю…');try{const r=await api('/telegram/test',{method:'POST'});res(r.ok?`Токен рабочий: бот @${r.username}`:r.error,r.ok)}catch(e){res(String(e.message||e),false)}};
  Q('#tg-link').onclick=async()=>{const pid=Q('#tg-pid').value,chat_id=Q('#tg-chat').value.trim();if(!chat_id)return toast('Укажите chat_id');try{await api(`/${pid}/telegram/link`,{method:'POST',body:{chat_id}});toast('Чат привязан, в Telegram отправлено подтверждение');S.profiles=(await api('/profiles')).profiles}catch{}};
  Q('#tg-send').onclick=async()=>{const pid=Q('#tg-pid').value;try{const r=await api(`/${pid}/telegram/test-send`,{method:'POST'});toast(r.ok?'Тестовое сообщение отправлено':(r.reason||'Не отправлено'))}catch{}}};
})();
