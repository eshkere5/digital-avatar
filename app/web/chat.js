(function(){
  VIEWS.splice(3,0,['chat','Чат','Вопросы аватару по задачам и целям']);
  VIEW.chat=async()=>{
    $('#view').innerHTML=`<div class="card"><h2>Чат с аватаром</h2><div class="chat" id="chat"></div><div class="row" style="margin-top:8px"><input class="sp" id="say" placeholder="Например: «Какой статус по КП?» или «Что просрочено?»"><button id="sendsay">Отправить</button></div></div>`;
    const chat=(who,t,me)=>{const c=$('#chat');c.insertAdjacentHTML('beforeend',`<div class="msg ${me?'me':''}"><small>${esc(who)}</small>${esc(t)}</div>`);c.scrollTop=c.scrollHeight};
    chat('Аватар (ИИ)','Здравствуйте! Я ИИ-помощник руководителя. Спросите о задачах, сроках и целях. Решения по деньгам, кадрам и обязательствам передам руководителю.');
    const say=async()=>{const t=$('#say').value.trim();if(!t)return;$('#say').value='';chat('Вы',t,true);const a=await api(P('/meeting/say'),{method:'POST',body:{text:t}});chat('Аватар (ИИ)'+(a.escalate?' · передано руководителю':''),a.text)};
    $('#sendsay').onclick=say;$('#say').onkeydown=e=>{if(e.key==='Enter')say()};
  };
})();
