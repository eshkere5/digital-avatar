const $=s=>document.querySelector(s);
const esc=s=>String(s??'').replace(/[&<>"']/g,c=>({'&':'&amp;','<':'&lt;','>':'&gt;','"':'&quot;',"'":'&#39;'}[c]));
const S={pid:'ivan',today:'2026-12-07',view:'today',mtab:'inbox',profiles:[]};
const VIEWS=[['today','Сегодня','Утренний план и решения'],['mail','Почта','Разбор писем по правилам профиля'],['meeting','Встреча','Аватар на звонке'],['protocols','Протоколы','Утверждение и рассылка'],['calendar','Календарь','Защита времени и освобождённые часы'],['learning','Обучение','Что аватар запомнил из правок'],['metrics','Метрики','Для питча'],['profile','Профиль','Настройка без кода'],['connections','Подключения','Модели, Telegram, Outlook']];
const toast=(t,ms=3200)=>{const e=$('#toast');e.textContent=t;e.classList.add('on');setTimeout(()=>e.classList.remove('on'),ms)};
async function api(p,o={}){const r=await fetch('/api'+p,{headers:{'Content-Type':'application/json'},...o,body:o.body?JSON.stringify(o.body):undefined});let j;try{j=await r.json()}catch{j={}}if(!r.ok){const m=j.detail||r.statusText;toast('Ошибка: '+(typeof m==='string'?m:JSON.stringify(m)));throw new Error(m)}return j}
const P=p=>`/${S.pid}${p}${p.includes('?')?'&':'?'}today=${S.today}`;
const fmt=iso=>new Date(iso).toLocaleString('ru',{weekday:'short',day:'2-digit',month:'2-digit',hour:'2-digit',minute:'2-digit'});
const hm=iso=>iso.slice(11,16);
const ACT={'спросить_руководителя':['bad','Решает руководитель'],'делегировать':['','Делегировано'],'авто':['ok','Авто'],'в_сводку':['gray','В сводку'],'игнорировать':['gray','Игнор']};
const tag=(c,t)=>`<span class="tag ${c}">${esc(t)}</span>`;

async function boot(){
  const r=await api('/profiles');S.profiles=r.profiles;S.today=r.demo_today;
  $('#pid').innerHTML=S.profiles.map(p=>`<option value="${p.id}">${esc(p.name)}</option>`).join('');$('#pid').value=S.pid;$('#today').value=S.today;
  $('#pid').onchange=e=>{S.pid=e.target.value;render()};$('#today').onchange=e=>{S.today=e.target.value;render()};
  $('#newprof').onclick=newProfile;render();status();
}
async function status(){const s=await api('/status');$('#status').innerHTML=`<span class="chip ${s.llm?'ok':'warn'}">${s.llm?'LLM подключена':'LLM не подключена'}</span><span class="chip ${s.telegram?'ok':'warn'}">Telegram ${s.telegram?'ок':'нет'}</span><span class="chip">Outlook: ${s.outlook==='graph'?'Graph':'заглушка'}</span>`}
async function newProfile(){const name=prompt('Имя нового руководителя');if(!name)return;const id=prompt('Короткий id (латиница)','boss2');if(!id)return;
  await api('/profiles',{method:'POST',body:{id,name,position:'Руководитель направления',base:S.pid}});S.profiles=(await api('/profiles')).profiles;S.pid=id;
  $('#pid').innerHTML=S.profiles.map(p=>`<option value="${p.id}">${esc(p.name)}</option>`).join('');$('#pid').value=id;S.view='profile';toast('Профиль создан из шаблона — отредактируйте цели и правила');render()}
function nav(counts={}){$('#nav').innerHTML=VIEWS.map(v=>`<button class="${S.view===v[0]?'on':''}" data-v="${v[0]}">${v[1]}${counts[v[0]]?`<span class="n">${counts[v[0]]}</span>`:''}</button>`).join('');
  document.querySelectorAll('#nav button').forEach(b=>b.onclick=()=>{S.view=b.dataset.v;render()})}
async function render(){nav();const v=VIEWS.find(x=>x[0]===S.view);$('#title').textContent=v[1];$('#sub').textContent=v[2];$('#view').innerHTML='<div class="empty">Загрузка…</div>';
  try{await VIEW[S.view]()}catch(e){console.error(e)}
  api(P('/briefing')).then(b=>nav({mail:b.decisions.length})).catch(()=>{})}

const VIEW={};
VIEW.today=async()=>{const b=await api(P('/briefing')),f=b.freed;
  $('#view').innerHTML=`<div class="grid g4" style="margin-bottom:16px">
   <div class="card kpi"><b>${b.decisions.length}</b><span>ждут вашего решения</span></div>
   <div class="card kpi"><b>${b.meetings_avatar.length}</b><span>встреч возьмёт аватар</span><small>лично вам: ${b.meetings_leader.length}</small></div>
   <div class="card kpi"><b>${f.conservative_h}–${f.total_h} ч</b><span>освобождено за неделю</span><small>консервативно – с протоколами</small></div>
   <div class="card kpi"><b>${Math.round(f.share_no_leader*100)}%</b><span>писем без вашего участия</span><small>уникальных: ${Math.round(f.share_no_leader_unique*100)}%</small></div></div>
  <div class="grid g2"><div class="card"><div class="row"><h2 class="sp">Сообщение в Telegram, ${esc(b.weekday)}</h2><button class="sm" id="sendtg">Отправить</button></div>
   <div class="tg">${b.text_html.replace(/<b>(.*?)<\/b>/g,'<b>$1</b>')}</div></div>
   <div class="card"><h2>Что решает только руководитель</h2><div class="list">${b.decisions.map(r=>`<div><div class="row">${tag('bad',r.category)}<b>${esc(r.from_name)}</b></div><div>${esc(r.subject)}</div>${r.downgrade?`<div class="mail-body">⚠ ${esc(r.downgrade)}</div>`:''}</div>`).join('')||'<div class="empty">Всё разобрано</div>'}</div>
   <div class="row" style="margin-top:10px"><button class="ghost sm" onclick="S.view='mail';render()">Перейти к почте</button></div></div></div>`;
  $('#sendtg').onclick=async()=>{const r=await api(P('/briefing/send'),{method:'POST'});toast(r.telegram.ok?'Отправлено в Telegram':(r.telegram.reason||'Не отправлено'))}};

VIEW.mail=async()=>{const d=await api(P('/inbox')),rows=d.rows,ev=d.eval;
  const cnt=a=>rows.filter(r=>r.action===a&&!r.duplicate_of).length;
  $('#view').innerHTML=`<div class="grid g4" style="margin-bottom:16px">
   <div class="card kpi"><b>${ev.accuracy!=null?Math.round(ev.accuracy*100)+'%':'—'}</b><span>точность по эталону</span><small>${ev.correct}/${ev.total}; утечек защищённых: ${(ev.protected_leaks||[]).length}</small></div>
   <div class="card kpi"><b>${rows.filter(r=>r.duplicate_of).length}</b><span>дублей свёрнуто</span></div>
   <div class="card kpi"><b>${cnt('спросить_руководителя')}</b><span>требуют вас</span></div>
   <div class="card"><button id="auto">Выполнить автодействия</button><div class="muted" style="font-size:12px;margin-top:6px">Делегирование, ответы по календарю, сводка, архив. Защищённые категории не затрагиваются.</div></div></div>
   <div class="card"><table><thead><tr><th>Письмо</th><th>Категория</th><th>Действие</th><th></th></tr></thead><tbody>
   ${rows.map(r=>`<tr class="${r.duplicate_of?'dup':''}"><td><b>${esc(r.from_name)}</b> <span class="muted">${esc(r.received.slice(5))}</span><div>${esc(r.subject)}</div><div class="mail-body">${esc(r.body)}</div>${r.downgrade?`<div class="mail-body" style="color:var(--warn)">⚠ ${esc(r.downgrade)}</div>`:''}${r.draft?`<div class="tg" style="margin-top:8px"><textarea rows="5" id="dr-${r.id}">${esc(r.draft.text)}</textarea><div class="row" style="margin-top:6px">${r.draft.rules_applied?.length?tag('ok','учтены правки: '+r.draft.rules_applied.length):''}<span class="sp"></span>${r.draft.sent?tag('ok','отправлено'):`<button class="sm" onclick="sendDraft('${r.id}')">Отправить</button>`}</div></div>`:''}</td>
   <td>${tag('',r.category)}<div class="mail-body">${esc(r.why)}</div></td>
   <td>${tag(...ACT[r.action])}${r.delegate_to?`<div class="mail-body">→ ${esc(r.delegate_to)}</div>`:''}${r.duplicate_of?`<div class="mail-body">дубль ${r.duplicate_of}</div>`:''}<div class="mail-body">${esc(r.state)}</div></td>
   <td>${r.needs_confirmation&&!r.duplicate_of&&!r.draft?`<div class="row" style="flex-direction:column;align-items:stretch;gap:4px"><button class="sm" onclick="decide('${r.id}','approve')">Согласовать</button><button class="sm ghost" onclick="decide('${r.id}','clarify')">Уточнить</button><button class="sm bad" onclick="decide('${r.id}','reject')">Отказать</button></div>`:''}</td></tr>`).join('')}
   </tbody></table></div>`;
  $('#auto').onclick=async()=>{const r=await api(P('/inbox/run-auto'),{method:'POST'});toast(`Выполнено: авто ${r['авто']}, делегировано ${r['делегировать']}, в сводку ${r['в_сводку']}, архив ${r['игнорировать']}`);render()}};
async function decide(id,decision){const note=prompt('Комментарий для ответа (можно пусто)','')??'';await api(P(`/emails/${id}/decision`),{method:'POST',body:{decision,note}});render()}
async function sendDraft(id){const text=$('#dr-'+id).value;const r=await api(`/${S.pid}/emails/${id}/send`,{method:'POST',body:{text}});toast(r.learned?'Отправлено. Правка запомнена':'Отправлено');render()}

let TTS=null;function speak(t,onend){if(!('speechSynthesis' in window)){onend&&onend();return}const u=new SpeechSynthesisUtterance(t);u.lang='ru-RU';u.onstart=()=>$('#av')?.classList.add('talk');u.onend=u.onerror=()=>{$('#av')?.classList.remove('talk');onend&&onend()};speechSynthesis.speak(u)}
VIEW.meeting=async()=>{const lib=(await api('/library')).items,ph=(await api(P('/avatar-photo'))).data_url,prof=S.profiles.find(p=>p.id===S.pid);
  const sum=lib.filter(x=>x.summary),tr=lib.filter(x=>x.transcript);
  $('#view').innerHTML=`<div class="grid g2"><div class="card"><div class="avatar" id="av" style="${ph?`background-image:url(${ph})`:''}">${ph?'':esc(prof.name.split(' ').map(x=>x[0]).join(''))}<span class="badge-ai">ИИ</span></div>
   <p class="muted" style="text-align:center">Аватар представляется ИИ-помощником. Чтобы показать его в МТС Линк, Zoom, Дион или Телемост: откройте эту страницу в браузере, включите виртуальную камеру (например, OBS Virtual Camera) и выберите её в платформе.</p>
   <label>Платформа (для сценария)<select id="plat"><option>МТС Линк</option><option>Zoom</option><option>Дион</option><option>Телемост</option></select></label>
   <label>Прошлый протокол<select id="prev"><option value="">— нет —</option>${sum.map(x=>`<option>${esc(x.name)}</option>`).join('')}</select></label>
   <label>Запись встречи (транскрипт)<select id="trs">${tr.map(x=>`<option>${esc(x.name)}</option>`).join('')}</select></label>
   <div class="row" style="margin-top:10px"><button id="start">Начать встречу</button><button class="ghost" id="finish" disabled>Завершить → протокол</button><button class="ghost sm" id="mic">🎤 Голос</button><label class="ghost" style="cursor:pointer;color:var(--acc)">Фото<input type="file" id="ph" accept="image/*" hidden></label></div></div>
   <div class="card"><h2>Ход встречи</h2><div class="chat" id="chat"></div><div class="row" style="margin-top:8px"><input class="sp" id="say" placeholder="Реплика участника: например, «Какой статус по КП?» или «Можно скидку 15%?»"><button id="sendsay">Сказать</button></div></div></div>`;
  const chat=(who,t,me)=>{const c=$('#chat');c.insertAdjacentHTML('beforeend',`<div class="msg ${me?'me':''}"><small>${esc(who)}</small>${esc(t)}</div>`);c.scrollTop=c.scrollHeight};
  let timer=null,lines=[];
  $('#ph').onchange=e=>{const f=e.target.files[0];if(!f)return;const r=new FileReader();r.onload=async()=>{await api(P('/avatar-photo'),{method:'PUT',body:{data_url:r.result}});$('#av').style.backgroundImage=`url(${r.result})`;$('#av').firstChild.textContent=''};r.readAsDataURL(f)};
  $('#start').onclick=async()=>{$('#start').disabled=true;$('#finish').disabled=false;const sc=await api(P('/meeting/script?prev='+encodeURIComponent($('#prev').value)));
    chat('Аватар (ИИ)',sc.intro);const qs=[...sc.questions];
    const askNext=()=>{if(!qs.length){stream();return}const q=qs.shift();chat('Аватар (ИИ)',q);speak(q,()=>setTimeout(askNext,1200))};
    speak(sc.intro,askNext);
    async function stream(){chat('Система','Запись встречи идёт: ниже — реплики участников (ускоренно).');
      const t=await api(`/transcript?name=${encodeURIComponent($('#trs').value)}`).catch(()=>({lines:[]}));lines=t.lines.slice(0,40);let i=0;
      timer=setInterval(()=>{if(i>=lines.length){clearInterval(timer);return}chat('Участник',lines[i++])},700)}};
  const say=async()=>{const t=$('#say').value.trim();if(!t)return;$('#say').value='';chat('Участник',t,true);const a=await api(P('/meeting/say'),{method:'POST',body:{text:t}});chat('Аватар (ИИ)'+(a.escalate?' · передано руководителю':''),a.text);speak(a.text)};
  $('#sendsay').onclick=say;$('#say').onkeydown=e=>{if(e.key==='Enter')say()};
  $('#mic').onclick=()=>{const R=window.SpeechRecognition||window.webkitSpeechRecognition;if(!R)return toast('Браузер не поддерживает распознавание речи');const r=new R();r.lang='ru-RU';r.onresult=e=>{$('#say').value=e.results[0][0].transcript;say()};r.start();toast('Говорите…')};
  $('#finish').onclick=async()=>{clearInterval(timer);speechSynthesis?.cancel();const sc=await api(P('/meeting/script?prev='+encodeURIComponent($('#prev').value)));chat('Аватар (ИИ)',sc.outro);speak(sc.outro);
    const p=await api(P('/protocols/draft'),{method:'POST',body:{title:$('#trs').value,transcript:'-'.repeat(12),library_prev:$('#prev').value,library_transcript:$('#trs').value}});toast('Черновик протокола готов — на утверждении');S.view='protocols';setTimeout(render,1200)}};

VIEW.protocols=async()=>{const items=(await api(`/${S.pid}/protocols`)).items;
  $('#view').innerHTML=items.length?items.map(p=>`<div class="card" style="margin-bottom:16px"><div class="row"><h2 class="sp">${esc(p.title)}</h2>${tag(p.status==='sent'?'ok':p.status==='draft'?'warn':'gray',{draft:'на утверждении',sent:'разослан',approved:'утверждён',rejected:'отклонён'}[p.status])}${tag('gray',p.data.engine||'')}</div>
   ${p.prev_questions?.length?`<div class="mail-body">Вопросы по прошлому протоколу: ${p.prev_questions.length}</div>`:''}
   ${p.rules_applied?.length?`<div style="margin:6px 0">${p.rules_applied.map(r=>tag('ok','правило: '+r)).join(' ')}</div>`:''}
   ${p.status==='draft'?`<textarea id="pt-${p.id}" rows="16">${esc(p.text)}</textarea><div class="row" style="margin-top:8px"><button onclick="approve('${p.id}')">Утвердить и разослать</button><button class="bad" onclick="rejectP('${p.id}')">Отклонить</button><span class="muted">Правки в тексте будут запомнены</span></div>`:`<pre class="md">${esc(p.text)}</pre>`}
   ${p.sent?`<h3>Выполнено после утверждения</h3><div class="mail-body">Письмо: ${esc(p.sent.mail.mode)} ${esc(p.sent.mail.file||'')} · задач создано: ${p.sent.tasks.length}</div>`:''}</div>`).join(''):'<div class="card empty">Протоколов пока нет. Проведите встречу на вкладке «Встреча».</div>'};
async function approve(id){const r=await api(P(`/protocols/${id}/approve`),{method:'POST',body:{text:$('#pt-'+id).value}});toast(`Разослано. Задач: ${r.tasks?.length||0}`);render()}
async function rejectP(id){await api(`/${S.pid}/protocols/${id}/reject`,{method:'POST',body:{reason:''}});render()}

VIEW.calendar=async()=>{const d=await api(P('/calendar')),f=d.freed;const days=[...new Set(d.events.map(e=>e.start.slice(0,10)))].filter((x,i,a)=>new Date(x).getDay()%6).sort().slice(0,10);
  const week=days.slice(0,5),H0=9,H1=18,px=44;
  const hr=s=>+s.slice(11,13)+ +s.slice(14,16)/60,ovl=(b,e)=>hr(e.start)<hr(b.end)-0.01&&hr(e.start)+Math.max(18,e.minutes/60*px-2)/px>hr(b.start)+0.01;
  const col=day=>`<div class="col" style="height:${(H1-H0)*px}px">${d.blocks.filter(b=>b.start.startsWith(day)).map(b=>`<div class="ev block" style="top:${((+b.start.slice(11,13)+ +b.start.slice(14,16)/60)-H0)*px}px;height:${(((+b.end.slice(11,13)+ +b.end.slice(14,16)/60)-(+b.start.slice(11,13)+ +b.start.slice(14,16)/60)))*px}px;right:${d.events.some(e=>e.start.startsWith(day)&&ovl(b,e))?'49%':'2px'}">🛡 ${esc(b.title)}</div>`).join('')}${d.events.filter(e=>e.start.startsWith(day)).map(e=>`<div class="ev ${e.avatar_ok?'':'leader'}" title="${esc(e.title)}" style="top:${((+e.start.slice(11,13)+ +e.start.slice(14,16)/60)-H0)*px}px;height:${Math.max(18,e.minutes/60*px-2)}px;left:${d.blocks.some(b=>b.start.startsWith(day)&&ovl(b,e))?'52%':'2px'}">${hm(e.start)} ${esc(e.title)}</div>`).join('')}</div>`;
  const grid=wk=>`<div class="cal"><div class="h"></div>${wk.map(x=>`<div class="h">${new Date(x).toLocaleDateString('ru',{weekday:'short',day:'numeric',month:'numeric'})}</div>`).join('')}<div>${Array.from({length:H1-H0},(_,i)=>`<div class="t" style="height:${px}px">${H0+i}:00</div>`).join('')}</div>${wk.map(col).join('')}</div>`;
  $('#view').innerHTML=`<div class="grid g4" style="margin-bottom:16px"><div class="card kpi"><b>${f.conservative_h}–${f.total_h} ч</b><span>освобождено за неделю</span></div><div class="card kpi"><b>${f.meetings_avatar}/${f.meetings_total}</b><span>встреч закрывает аватар</span></div><div class="card kpi"><b>${f.mail_h} ч</b><span>почта без вас</span></div><div class="card kpi"><b>${f.protocol_h} ч</b><span>протоколы (экономия)</span></div></div>
  <div class="card" style="margin-bottom:16px"><div class="row"><span class="tag warn">Нужен руководитель</span><span class="tag">Берёт аватар</span><span class="tag ok">🛡 Защищённый блок</span></div><div style="margin-top:10px">${grid(week)}</div><p class="muted" style="font-size:12px">Расчёт: ${esc(f.assumptions)}</p></div>
  <div class="card"><h2>Конфликты с защищёнными блоками</h2><div class="list">${d.proposals.map(p=>`<div><div class="row"><b>${esc(p.event.title)}</b><span class="muted">${fmt(p.event.start)}</span>${tag('warn',p.block)}<span class="sp"></span>${p.proposal?`<span>→ ${fmt(p.proposal.start)}</span><button class="sm" onclick="mv('${p.event.id}','${p.proposal.start}','${p.proposal.end}')">Перенести</button>`:`<span class="muted">${esc(p.note)}</span>`}</div></div>`).join('')||'<div class="empty">Конфликтов нет</div>'}</div></div>`};
async function mv(id,s,e){await api(`/${S.pid}/calendar/move`,{method:'POST',body:{event_id:id,start:s,end:e}});toast('Перенесено, приглашение сформировано');render()}

VIEW.learning=async()=>{const m=await api(`/${S.pid}/memory`);
  $('#view').innerHTML=`<div class="grid g2"><div class="card"><div class="row"><h2 class="sp">Правила руководителя</h2><button class="ghost sm" id="dis">Сжать правки через LLM</button></div><div class="list">${m.rules.map(r=>`<div class="row"><span class="sp">${r.type==='replace'?`«${esc(r.from)}» → «${esc(r.to)}»`:r.type==='delete'?`убирать «${esc(r.from)}»`:esc(r.text)}</span>${tag('gray','×'+r.count)}<label style="flex-direction:row;align-items:center"><input type="checkbox" ${r.on!==false?'checked':''} onchange="tg('${r.id}',this.checked)"></label><button class="sm bad" onclick="dl('${r.id}')">✕</button></div>`).join('')||'<div class="empty">Пока пусто. Отредактируйте черновик письма или протокола — правило появится здесь и сработает в следующем черновике.</div>'}</div></div>
  <div class="card"><h2>Последние правки</h2><div class="list">${m.edits.map(e=>`<div><div class="row">${tag('',e.kind)}<span class="muted">${esc(e.ts)} · ${esc(e.ctx)}</span></div>${e.ops.slice(0,4).map(o=>`<div class="mail-body">${esc(o.op)}: «${esc(o.from)}» → «${esc(o.to)}»</div>`).join('')}</div>`).join('')||'<div class="empty">Правок пока нет</div>'}</div></div></div>`;
  $('#dis').onclick=async()=>{const r=await api(`/${S.pid}/memory/distill`,{method:'POST'});toast(r.llm?`Добавлено правил: ${r.added.length}`:'Подключите LLM');render()}};
async function tg(id,on){await api(`/${S.pid}/memory/${id}`,{method:'POST',body:{on}})}
async function dl(id){await api(`/${S.pid}/memory/${id}`,{method:'DELETE'});render()}

VIEW.metrics=async()=>{const m=await api(P('/metrics')),f=m.freed,e=m.eval||{};const pr=n=>`<div class="bar"><i style="width:${Math.min(100,n)}%"></i></div>`;
  const aud=(await api(`/${S.pid}/audit`)).items;
  $('#view').innerHTML=`<div class="grid g4" style="margin-bottom:16px">
  <div class="card kpi"><b>${f.conservative_h}–${f.total_h} ч</b><span>часов в неделю освобождено</span><small>цель ТЗ: 8–12</small></div>
  <div class="card kpi"><b>${Math.round(f.share_no_leader*100)}%</b><span>писем без руководителя</span>${pr(f.share_no_leader*100)}<small>уникальных: ${Math.round(f.share_no_leader_unique*100)}%</small></div>
  <div class="card kpi"><b>${e.accuracy!=null?Math.round(e.accuracy*100)+'%':'—'}</b><span>точность разбора</span><small>утечек в защищённые: ${(e.protected_leaks||[]).length}</small></div>
  <div class="card kpi"><b>${m.learned_rules}</b><span>правил из правок</span><small>правок: ${m.edits}</small></div>
  <div class="card kpi"><b>${m.protocols.sent}/${m.protocols.total}</b><span>протоколов разослано</span></div>
  <div class="card kpi"><b>${m.tasks.overdue}</b><span>просроченных задач</span><small>из ${m.tasks.total}</small></div>
  <div class="card kpi"><b>${m.escalations}</b><span>вопросов передано руководителю</span></div></div>
  <div class="card"><h2>Журнал действий (цепочка хэшей)</h2><div class="list">${aud.map(a=>`<div class="row"><span class="muted">${esc(a.ts)}</span>${tag('gray',a.actor)}<b>${esc(a.action)}</b><span class="muted">${esc(a.target)}</span><span class="sp"></span><code class="muted">${esc(a.hash)}</code></div>`).join('')||'<div class="empty">Пусто</div>'}</div></div>`};

VIEW.profile=async()=>{const p=await api(`/${S.pid}/profile`),x=p.parsed;
  $('#view').innerHTML=`<div class="grid g2"><div class="card"><div class="row"><h2 class="sp">profile.md</h2><button id="saveprof">Сохранить</button></div><textarea id="md" rows="32" style="font:13px ui-monospace,Consolas,monospace">${esc(p.markdown)}</textarea><p class="muted" style="font-size:12px">Блоки «Правила разбора» и «Защищённые блоки» — формат: «категория → действие → кому» и «название | дни | ЧЧ:ММ-ЧЧ:ММ». Категории из «Никогда без подтверждения» нельзя перевести в авто.</p></div>
  <div class="card"><h2>Как агент понял профиль</h2><h3>${esc(x.name)} · ${esc(x.position)}</h3><div class="mail-body">Telegram chat_id: ${esc(x.chat_id||'—')} · утренний план ${esc(x.briefing_time)}</div>
  <h3>Цели</h3><ul>${x.goals.map(g=>`<li>${esc(g)}</li>`).join('')}</ul><h3>Только с подтверждением</h3>${x.never.map(n=>tag('bad',n)).join(' ')}
  <h3>Правила</h3><table>${Object.entries(x.rules).map(([k,v])=>`<tr><td>${esc(k)}</td><td>${esc(v.action)}</td><td class="muted">${esc(v.to)}</td></tr>`).join('')}</table>
  <h3>Защищённые блоки</h3>${x.blocks.map(b=>`<div>🛡 ${esc(b.title)} · ${b.days.map(d=>['пн','вт','ср','чт','пт','сб','вс'][d]).join(', ')} · ${b.start}–${b.end}</div>`).join('')}
  <h3>Перед встречей один на один</h3><div class="row"><select id="who">${p.org.filter(o=>o.role_for_leader==='подчинённый').map(o=>`<option>${esc(o.name)}</option>`).join('')}</select><button class="sm ghost" id="prep">Сводка</button></div><div id="prepout" class="tg" style="margin-top:8px;display:none"></div></div></div>`;
  $('#saveprof').onclick=async()=>{await api(`/${S.pid}/profile`,{method:'PUT',body:{markdown:$('#md').value}});S.profiles=(await api('/profiles')).profiles;toast('Профиль сохранён — правила применены сразу');render()};
  $('#prep').onclick=async()=>{const r=await api(P('/prep?name='+encodeURIComponent($('#who').value)));const o=$('#prepout');o.style.display='block';o.textContent=(r.summary?r.summary+'\n\n':'')+r.talking_points.map(x=>'• '+x).join('\n')}};

VIEW.connections=async()=>{const s=await api('/settings');
  $('#view').innerHTML=`<div class="card"><h2>Большие LLM по ключу</h2><p class="muted">Ключ хранится только на этом компьютере (data/secrets.json) и не возвращается в интерфейс. Порядок — приоритет и фолбэк. Включите «маскировать ПДн», чтобы почты и телефоны не уходили в облако.</p>
  ${s.providers.map(p=>`<div class="prov" data-p="${p.id}"><div><b>${esc(p.label)}</b><div class="mail-body">${p.has_key?'ключ '+esc(p.key_hint):'ключ не задан'}</div><input class="key" type="password" placeholder="API-ключ" autocomplete="off"></div>
   <div><label>Модель<input class="model" list="m-${p.id}" value="${esc(p.model)}" placeholder="ID модели"><datalist id="m-${p.id}"></datalist></label><div class="mail-body"><input class="url" value="${esc(p.base_url)}" style="width:100%"></div></div>
   <div class="row" style="flex-direction:column;align-items:stretch;gap:4px"><label style="flex-direction:row;align-items:center;gap:6px"><input type="checkbox" class="en" ${p.enabled?'checked':''}>включена</label><label>Приоритет<input class="pri" type="number" value="${p.priority}" style="width:70px"></label></div>
   <div class="row" style="flex-direction:column;align-items:stretch;gap:4px"><button class="sm save">Сохранить</button><button class="sm ghost models">Модели</button><button class="sm ghost test">Проверить</button></div></div>`).join('')}
  <div class="row" style="margin-top:12px"><label style="flex-direction:row;align-items:center;gap:6px"><input type="checkbox" id="pii" ${s.mask_pii?'checked':''}>Маскировать e-mail и телефоны для облака</label><label style="flex-direction:row;align-items:center;gap:6px"><input type="checkbox" id="cloud" ${s.allow_cloud?'checked':''}>Разрешить облачные модели</label></div></div>
  <div class="grid g2" style="margin-top:16px"><div class="card"><h2>Telegram</h2><p class="muted">Токен бота от @BotFather. chat_id руководителя — в профиле. Кнопки «Утвердить/Отклонить» работают через long polling.</p><div class="row"><input id="tg" type="password" class="sp" placeholder="${s.telegram_set?'токен задан':'токен бота'}"><button class="sm" id="tgsave">Сохранить</button></div></div>
  <div class="card"><h2>Outlook (Microsoft Graph)</h2><p class="muted">Токен с правами Mail.Send и Calendars.ReadWrite. Без него письма и события пишутся в data/outbox как .eml/.ics (заглушка, допустимая по ТЗ).</p><div class="row"><input id="gr" type="password" class="sp" placeholder="${s.graph_set?'токен задан':'access token'}"><button class="sm" id="grsave">Сохранить</button></div></div></div>`;
  document.querySelectorAll('.prov').forEach(el=>{const id=el.dataset.p,q=c=>el.querySelector(c);
   q('.save').onclick=async()=>{await api('/settings',{method:'PUT',body:{providers:{[id]:{key:q('.key').value,model:q('.model').value,base_url:q('.url').value,enabled:q('.en').checked,priority:+q('.pri').value}}}});toast('Сохранено');status();render()};
   q('.models').onclick=async()=>{try{const r=await api(`/settings/${id}/models`);q('datalist').innerHTML=r.models.map(m=>`<option>${esc(m)}</option>`).join('');toast(`Моделей: ${r.models.length}`)}catch{}};
   q('.test').onclick=async()=>{const r=await api(`/settings/${id}/test`,{method:'POST'});toast(r.ok?`Работает · ${r.ms} мс`:'Не работает: '+r.error)}});
  $('#pii').onchange=$('#cloud').onchange=()=>api('/settings',{method:'PUT',body:{mask_pii:$('#pii').checked,allow_cloud:$('#cloud').checked}});
  $('#tgsave').onclick=async()=>{await api('/settings',{method:'PUT',body:{telegram_token:$('#tg').value}});toast('Сохранено');status();render()};
  $('#grsave').onclick=async()=>{await api('/settings',{method:'PUT',body:{graph_token:$('#gr').value}});toast('Сохранено');status();render()}};
boot();