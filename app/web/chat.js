(function(){
const SENS=/бюджет|скидк|цен[аыуе]\b|стоимост|оплат|гарант|обещ|увольн|найм|оффер|зарплат|отпуск|договор|подпис/;
const INTENTS=[
 ['help',/^(привет|здравствуй|добрый (день|вечер|утро)|hello|hi\b)|что (ты )?умеешь|чем (ты )?помож|помощь|help|команды/],
 ['status',/статус|кто отвечает|ответственн|кто делает|когда сдаст/],
 ['prep',/1:1|1-на-1|один на один|к встрече с|перед встречей|подготов\S* меня/],
 ['mail',/почт|письм|входящ|требу\S*.*(решени|меня|вас)|ждут.*решени/],
 ['plan',/план|сегодня|брифинг|утренн|что у меня/],
 ['overdue',/просроч|задач|дедлайн|горит|срыв/],
 ['calendar',/календар|конфликт|перенес|перенос|окно|окна|защищ|блок/],
 ['protocols',/протокол|утвердить|на утверждени/],
 ['metrics',/сколько часов|часов|экономи|метрик|эффект|освобод/],
 ['esc',/эскалац|передан\S* руковод|что ты не знал/],
];
const route=t=>{t=t.toLowerCase();if(SENS.test(t))return'ask';for(const[k,r]of INTENTS)if(r.test(t))return k;return'ask'};
const CHIPS=['План на сегодня','Что требует моего решения','Просроченные задачи','Конфликты в календаре','Протоколы на утверждении','Сколько часов освобождено','Что ты умеешь'];
const SRC={policy:['bad','политика: решает руководитель'],llm:['ok','модель'],tasks:['gray','по задачам'],rules:['gray','по правилам']};
const CSS=`
.ac{display:grid;grid-template-columns:minmax(0,1fr) 300px;gap:16px;align-items:start}
.ac-main{display:flex;flex-direction:column;height:calc(100vh - 170px);min-height:520px;padding:0;overflow:hidden}
.ac-top{display:flex;align-items:center;gap:12px;padding:14px 18px;border-bottom:1px solid var(--line)}
.ac-ava{width:38px;height:38px;border-radius:50%;background:var(--acc2);color:var(--acc);display:grid;place-items:center;font-weight:700;position:relative;flex:none}
.ac-ava i{position:absolute;right:-2px;bottom:-2px;width:11px;height:11px;border-radius:50%;background:var(--ok);border:2px solid var(--card)}
.ac-top b{display:block;line-height:1.2}.ac-top small{color:var(--mut)}
.ac-log{flex:1;overflow:auto;padding:18px;display:flex;flex-direction:column;gap:14px;scroll-behavior:smooth}
.ac-m{max-width:78%;animation:acin .22s ease both}.ac-m.me{align-self:flex-end}
.ac-w{font-size:11px;color:var(--mut);margin:0 4px 3px}.ac-m.me .ac-w{text-align:right}
.ac-b{padding:10px 14px;border-radius:14px;background:var(--bg);border:1px solid var(--line);font-size:14px;line-height:1.5;overflow-wrap:anywhere}
.ac-m.me .ac-b{background:var(--acc);border-color:var(--acc);color:#fff;border-bottom-right-radius:4px}.ac-m.bot .ac-b{border-bottom-left-radius:4px}
.ac-pre{white-space:pre-wrap}.ac-it{padding:8px 0;border-top:1px solid var(--line)}.ac-it:first-of-type{border-top:0}
.ac-it .row{gap:6px}.ac-sub{color:var(--mut);font-size:12.5px}.ac-acts{display:flex;gap:6px;flex-wrap:wrap;margin-top:10px}
.ac-acts button,.ac-chips button{background:var(--card);color:var(--ink);border:1px solid var(--line);border-radius:99px;padding:5px 12px;font-size:13px;transition:.15s}
.ac-acts button:hover,.ac-chips button:hover{border-color:var(--acc);color:var(--acc);filter:none}
.ac-acts button.pri{background:var(--acc);color:#fff;border-color:var(--acc)}.ac-acts button.pri:hover{color:#fff;filter:brightness(1.08)}
.ac-chips{display:flex;gap:6px;overflow-x:auto;padding:10px 18px 0;scrollbar-width:none}.ac-chips button{white-space:nowrap}
.ac-in{display:flex;gap:8px;padding:12px 18px 16px;align-items:flex-end}
.ac-in textarea{flex:1;resize:none;max-height:120px;border-radius:12px;padding:10px 12px}
.ac-in button{border-radius:12px;height:40px}.ac-in .ic{width:40px;padding:0;background:var(--card);color:var(--ink);border-color:var(--line)}
.ac-dots{display:inline-flex;gap:4px;padding:4px 0}.ac-dots i{width:6px;height:6px;border-radius:50%;background:var(--mut);animation:acd 1s infinite}
.ac-dots i:nth-child(2){animation-delay:.15s}.ac-dots i:nth-child(3){animation-delay:.3s}
.ac-side{display:flex;flex-direction:column;gap:16px}.ac-kp{display:grid;grid-template-columns:1fr 1fr;gap:10px}
.ac-kp div{border:1px solid var(--line);border-radius:10px;padding:10px}.ac-kp b{display:block;font-size:22px;line-height:1.1}.ac-kp span{font-size:12px;color:var(--mut)}
.ac-side ul{margin:6px 0 0;padding-left:18px;color:var(--mut);font-size:13px}.ac-side li{margin:4px 0}
@keyframes acin{from{opacity:0;transform:translateY(6px)}to{opacity:1;transform:none}}
@keyframes acd{0%,80%,100%{opacity:.25;transform:translateY(0)}40%{opacity:1;transform:translateY(-3px)}}
@media(max-width:980px){.ac{grid-template-columns:1fr}.ac-main{height:calc(100vh - 150px)}.ac-m{max-width:92%}}
@media(prefers-reduced-motion:reduce){.ac-m,.ac-dots i{animation:none}.ac-log{scroll-behavior:auto}}`;
VIEWS.splice(3,0,['chat','Чат','Спросите аватара: почта, задачи, календарь, протоколы']);
VIEW.chat=async()=>{
  if(!document.getElementById('ac-css')){const s=document.createElement('style');s.id='ac-css';s.textContent=CSS;document.head.appendChild(s)}
  const prof=S.profiles.find(p=>p.id===S.pid)||{name:'Руководитель'},HK='ac-hist-'+S.pid;
  const ini=prof.name.split(' ').map(x=>x[0]).join('').slice(0,2);
  $('#view').innerHTML=`<div class="ac"><div class="card ac-main">
   <div class="ac-top"><div class="ac-ava">ИИ<i></i></div><div class="sp"><b>Аватар · ${esc(prof.name)}</b><small id="ac-mode">подключаюсь…</small></div><button class="ghost sm" id="ac-clr">Очистить</button></div>
   <div class="ac-log" id="ac-log" aria-live="polite"></div>
   <div class="ac-chips">${CHIPS.map(c=>`<button data-act="ask" data-q="${esc(c)}">${esc(c)}</button>`).join('')}</div>
   <div class="ac-in"><button class="ic" id="ac-mic" title="Голос">🎤</button><textarea id="ac-t" rows="1" placeholder="Спросите о почте, задачах, календаре или протоколах…" aria-label="Сообщение"></textarea><button id="ac-go">Отправить</button></div></div>
   <div class="ac-side"><div class="card"><h2>Сейчас у ${esc(prof.name.split(' ')[0])}</h2><div class="ac-kp" id="ac-kp"><div><b>…</b><span>ждут решения</span></div><div><b>…</b><span>просрочено</span></div><div><b>…</b><span>встреч берёт аватар</span></div><div><b>…</b><span>передано вам</span></div></div></div>
   <div class="card"><h2>Как это работает</h2><ul><li>Данные берутся из почты, календаря, задач и протоколов профиля.</li><li>Вопросы про деньги, кадры и обязательства аватар не решает, а передаёт руководителю.</li><li>Необратимые действия (перенос, отправка) только по вашей кнопке.</li></ul></div></div></div>`;
  const log=$('#ac-log'),inp=$('#ac-t');let hist=[];try{hist=JSON.parse(localStorage.getItem(HK)||'[]')}catch{}
  const save=()=>{try{localStorage.setItem(HK,JSON.stringify(hist.slice(-50)))}catch{}};
  const clock=()=>new Date().toLocaleTimeString('ru',{hour:'2-digit',minute:'2-digit'});
  const el=(who,html,me,ts)=>{const d=document.createElement('div');d.className='ac-m '+(me?'me':'bot');d.innerHTML=`<div class="ac-w">${esc(who)} · ${ts}</div><div class="ac-b">${html}</div>`;log.appendChild(d);log.scrollTop=log.scrollHeight;return d};
  const add=(who,html,me)=>{const ts=clock();hist.push({who,html,me:!!me,ts});save();return el(who,html,me,ts)};
  const bot=html=>add('Аватар (ИИ)',html,false);
  const btn=(label,attrs,pri)=>`<button class="${pri?'pri':''}" ${attrs}>${esc(label)}</button>`;
  const go=(v,label)=>btn(label,`data-act="goto" data-v="${v}"`,true);
  const ask=q=>btn(q,`data-act="ask" data-q="${esc(q)}"`);
  const typing=()=>{const d=document.createElement('div');d.className='ac-m bot';d.innerHTML='<div class="ac-b"><span class="ac-dots"><i></i><i></i><i></i></span></div>';log.appendChild(d);log.scrollTop=log.scrollHeight;return d};
  const none=m=>`<div class="ac-sub">${m}</div>`;
  const panel=async()=>{try{const[b,m]=await Promise.all([api(P('/briefing')),api(P('/metrics'))]);
    $('#ac-kp').innerHTML=[[b.decisions.length,'ждут решения'],[m.tasks.overdue,'просрочено задач'],[b.meetings_avatar.length,'встреч берёт аватар'],[m.escalations,'передано вам']].map(x=>`<div><b>${x[0]}</b><span>${x[1]}</span></div>`).join('')}catch{}};
  const handlers={
   async help(){return`Я работаю по данным профиля и умею:<div class="ac-it">• <b>План на сегодня</b> — утренняя сводка</div><div class="ac-it">• <b>Почта</b> — что требует вашего решения</div><div class="ac-it">• <b>Задачи</b> — просроченные и ближайшие, «статус по КП»</div><div class="ac-it">• <b>Календарь</b> — конфликты с защищёнными блоками и перенос</div><div class="ac-it">• <b>Протоколы</b> — что ждёт утверждения</div><div class="ac-it">• <b>1:1</b> — «подготовь к встрече с Сидоровым»</div><div class="ac-acts">${ask('План на сегодня')}${ask('Просроченные задачи')}</div>`},
   async plan(){const b=await api(P('/briefing'));return`<div class="ac-pre">${b.text_html}</div><div class="ac-acts">${go('mail','Открыть почту')}${ask('Конфликты в календаре')}${ask('Просроченные задачи')}</div>`},
   async mail(){const d=await api(P('/inbox')),rows=d.rows.filter(r=>r.needs_confirmation&&!r.duplicate_of&&['ожидает','новое'].includes(r.state));
    const auto=d.rows.filter(r=>!r.duplicate_of&&!r.needs_confirmation).length;
    if(!rows.length)return`Всё разобрано: на вас ничего не ждёт. Остальное (${auto}) обработано по правилам.<div class="ac-acts">${go('mail','Открыть почту')}</div>`;
    return`<b>${rows.length}</b> ${rows.length%10==1&&rows.length!=11?'письмо ждёт':'писем ждут'} вашего решения, ещё ${auto} разобрано без вас.`+rows.slice(0,5).map(r=>`<div class="ac-it"><div class="row">${tag('bad',r.category)}<b>${esc(r.from_name)}</b></div><div>${esc(r.subject)}</div>${r.downgrade?`<div class="ac-sub">⚠ ${esc(r.downgrade)}</div>`:''}</div>`).join('')+(rows.length>5?none(`и ещё ${rows.length-5}…`):'')+`<div class="ac-acts">${go('mail','Принять решения')}</div>`},
   async overdue(){const ts=(await api(P('/tasks'))).tasks,over=ts.filter(t=>t.overdue),soon=ts.filter(t=>!t.overdue&&t.days_left!=null&&t.days_left>=0&&t.days_left<=3&&!['готово','done','выполнена'].includes(t.status));
    if(!over.length&&!soon.length)return'Просроченных задач нет, ближайшие три дня свободны от дедлайнов.';
    const row=t=>`<div class="ac-it"><div class="row"><b class="sp">${esc(t.task)}</b>${tag(t.overdue?'bad':'warn',t.overdue?'просрочено':'до '+t.due)}</div><div class="ac-sub">${esc(t.owner||'без ответственного')} · срок ${esc(t.due)}</div></div>`;
    return`<b>Просрочено: ${over.length}</b>`+over.slice(0,6).map(row).join('')+(soon.length?`<div style="margin-top:10px"><b>Горит в ближайшие 3 дня: ${soon.length}</b></div>`+soon.slice(0,4).map(row).join(''):'')+`<div class="ac-acts">${ask('Подготовь к 1:1')}</div>`},
   async calendar(){const c=await api(P('/calendar')),f=c.freed,pr=c.proposals||[];
    return`За неделю освобождено <b>${f.conservative_h}–${f.total_h} ч</b>, аватар закрывает ${f.meetings_avatar} из ${f.meetings_total} встреч.`+(pr.length?`<div style="margin-top:8px"><b>Конфликты с защищёнными блоками: ${pr.length}</b></div>`+pr.slice(0,4).map(p=>`<div class="ac-it"><div class="row"><b class="sp">${esc(p.event.title)}</b>${tag('warn',p.block)}</div><div class="ac-sub">${fmt(p.event.start)}${p.proposal?' → '+fmt(p.proposal.start):' · '+esc(p.note||'нет окна')}</div>${p.proposal?`<div class="ac-acts">${btn('Перенести',`data-act="mv" data-id="${esc(p.event.id)}" data-s="${esc(p.proposal.start)}" data-e="${esc(p.proposal.end)}"`,true)}</div>`:''}</div>`).join(''):'<div style="margin-top:6px">Конфликтов с защищёнными блоками нет.</div>')+`<div class="ac-acts">${go('calendar','Открыть календарь')}</div>`},
   async protocols(){const it=(await api(`/${S.pid}/protocols`)).items,dr=it.filter(p=>p.status==='draft');
    if(!it.length)return`Протоколов пока нет. Проведите встречу на вкладке «Встреча»: аватар подготовит черновик.<div class="ac-acts">${go('meeting','Перейти ко встрече')}</div>`;
    return`Протоколов: <b>${it.length}</b>, на утверждении: <b>${dr.length}</b>, разослано: ${it.filter(p=>p.status==='sent').length}.`+dr.slice(0,4).map(p=>`<div class="ac-it"><b>${esc(p.title)}</b><div class="ac-sub">${esc(p.date)} · задач в черновике: ${(p.data.tasks||[]).length}</div></div>`).join('')+`<div class="ac-acts">${go('protocols',dr.length?'Утвердить':'Открыть протоколы')}</div>`},
   async metrics(){const m=await api(P('/metrics')),f=m.freed,e=m.eval||{};
    return`<div class="ac-it"><b>${f.conservative_h}–${f.total_h} ч</b> в неделю освобождено</div><div class="ac-it"><b>${Math.round(f.share_no_leader*100)}%</b> писем без участия руководителя</div><div class="ac-it"><b>${e.accuracy!=null?Math.round(e.accuracy*100)+'%':'—'}</b> точность разбора, утечек защищённых: ${(e.protected_leaks||[]).length}</div><div class="ac-it">Правил из правок: <b>${m.learned_rules}</b> · просрочено задач: <b>${m.tasks.overdue}</b> · передано руководителю: <b>${m.escalations}</b></div><div class="ac-acts">${go('metrics','Все метрики')}</div>`},
   async esc(){const it=(await api(`/${S.pid}/escalations`)).items;
    return it.length?`Передано руководителю: <b>${it.length}</b>`+it.slice(-6).reverse().map(x=>`<div class="ac-it"><span class="ac-sub">${esc(x.ts)}</span> ${esc(x.q)}</div>`).join(''):'Пока ничего не передавалось: вопросов про деньги, кадры или обязательства не было.'},
   async prep(text){const org=(await api(`/${S.pid}/profile`)).org.filter(o=>o.role_for_leader==='подчинённый'),t=text.toLowerCase();
    const hit=org.find(o=>o.name.split(' ').some(w=>w.length>3&&t.includes(w.toLowerCase().slice(0,Math.max(4,w.length-2)))));
    if(!hit)return'С кем готовим встречу один на один?<div class="ac-acts">'+org.slice(0,8).map(o=>ask('Подготовь к 1:1 с '+o.name)).join('')+'</div>';
    const r=await api(P('/prep?name='+encodeURIComponent(hit.name)));
    return`<b>1:1 с ${esc(hit.name)}</b>`+(r.summary?`<div class="ac-pre" style="margin-top:6px">${esc(r.summary)}</div>`:'')+(r.talking_points.length?r.talking_points.map(x=>`<div class="ac-it">• ${esc(x)}</div>`).join(''):'<div class="ac-sub">Нет открытых задач и писем — можно обсудить развитие и обратную связь.</div>')},
   async status(text){return handlers.ask(text)},
   async ask(text){const a=await api(P('/meeting/say'),{method:'POST',body:{text}}),s=SRC[a.source]||['gray',a.source||'правила'];
    return`<div>${esc(a.text)}</div><div class="ac-acts" style="margin-top:8px">${a.escalate?tag('bad','передано руководителю'):''} ${tag(s[0],s[1])}</div>`}
  };
  async function send(text){text=text.trim();if(!text)return;add('Вы',esc(text),true);const w=typing();let html;
    try{html=await handlers[route(text)](text)}catch(e){html='Не получилось получить данные: '+esc(e.message||e)}
    w.remove();bot(html);panel()}
  log.onclick=e=>{const b=e.target.closest('[data-act]');if(!b)return;const a=b.dataset.act;
    if(a==='ask')send(b.dataset.q);else if(a==='goto'){S.view=b.dataset.v;render()}
    else if(a==='mv'&&confirm('Перенести встречу и сформировать приглашение?'))api(`/${S.pid}/calendar/move`,{method:'POST',body:{event_id:b.dataset.id,start:b.dataset.s,end:b.dataset.e}}).then(()=>{b.disabled=true;b.textContent='Перенесено';toast('Перенесено, приглашение сформировано');panel()})};
  document.querySelector('.ac-chips').onclick=log.onclick;
  $('#ac-go').onclick=()=>{const v=inp.value;inp.value='';inp.style.height='';send(v)};
  inp.onkeydown=e=>{if(e.key==='Enter'&&!e.shiftKey){e.preventDefault();$('#ac-go').click()}};
  inp.oninput=()=>{inp.style.height='auto';inp.style.height=Math.min(120,inp.scrollHeight)+'px'};
  $('#ac-clr').onclick=()=>{hist=[];save();log.innerHTML='';greet()};
  $('#ac-mic').onclick=()=>{const R=window.SpeechRecognition||window.webkitSpeechRecognition;if(!R)return toast('Браузер не поддерживает распознавание речи');const r=new R();r.lang='ru-RU';r.onresult=e=>send(e.results[0][0].transcript);r.start();toast('Говорите…')};
  const greet=()=>bot(`Здравствуйте, ${esc(prof.name.split(' ')[0])}! Я ИИ-помощник и работаю по вашим данным: почта, задачи, календарь, протоколы. Решения по деньгам, кадрам и обязательствам передаю вам.<div class="ac-acts">${ask('План на сегодня')}${ask('Что требует моего решения')}${ask('Что ты умеешь')}</div>`);
  if(hist.length)hist.forEach(m=>el(m.who,m.html,m.me,m.ts));else greet();
  api('/status').then(s=>$('#ac-mode').textContent=s.llm?'модель подключена · отвечает развёрнуто':'режим правил · без внешней модели').catch(()=>{$('#ac-mode').textContent='онлайн'});
  panel();inp.focus();
};
VIEW.chat._route=route;
})();
