const $ = (s) => document.querySelector(s);
const grid = $('#listingGrid');
const empty = $('#emptyState');
let activeKind = 'Все';
let items = [];
let toastTimer;

const iconMap = { 'Аксессуары':'watch', 'Электроника':'headphones', 'Ключи':'key-round', 'Сумки':'backpack', 'Другое':'package' };
const demoItems = [
 {id:'td-1001',title:'Чёрный кошелёк',category:'Аксессуары',kind:'Найдено',place:'Ташкент · Мирзо-Улугбекский район',date:'Сегодня',description:'Найден рядом с парком. Владелец сможет подтвердить содержимое.',org:'Частный пользователь',color:'#263246',icon:'wallet'},
 {id:'td-1002',title:'Беспроводные наушники',category:'Электроника',kind:'Потеряно',place:'Ташкент · метро Космонавтлар',date:'Вчера',description:'Белый кейс, без указания серийного номера в открытом доступе.',org:'Частный пользователь',color:'#e8edf6',icon:'headphones'},
 {id:'td-1003',title:'Связка ключей',category:'Ключи',kind:'Найдено',place:'Ташкент · Юнусабад',date:'18 ноя',description:'Несколько ключей на кольце. Детали доступны после проверки заявки.',org:'Учебный центр · демо',color:'#d6b46a',icon:'key-round'},
 {id:'td-1004',title:'Детский рюкзак',category:'Сумки',kind:'Найдено',place:'Ташкент · Чиланзар',date:'17 ноя',description:'Передан на стойку информации учреждения. Не публикуем личные данные.',org:'Организация · демо',color:'#cf8f77',icon:'backpack'},
 {id:'td-1005',title:'Смарт-часы',category:'Электроника',kind:'Потеряно',place:'Ташкент · Бунёдкор',date:'16 ноя',description:'Тёмный ремешок. Для подтверждения владельца потребуется дополнительная проверка.',org:'Частный пользователь',color:'#343c4c',icon:'watch'},
 {id:'td-1006',title:'Зонт',category:'Другое',kind:'Найдено',place:'Ташкент · Шайхантахур',date:'15 ноя',description:'Найден в общественном месте. Свяжитесь с ответственным учреждением.',org:'Организация · демо',color:'#8ca4bb',icon:'umbrella'}
];

function notify(message) {
  $('#toastText').textContent = message;
  $('#toast').classList.add('show');
  clearTimeout(toastTimer);
  toastTimer = setTimeout(() => $('#toast').classList.remove('show'), 2800);
}
function openDemo(title, text) {
  $('#modalTitle').textContent = title || 'Скоро на Topdim';
  $('#modalText').textContent = text || 'Сейчас это демонстрация интерфейса. Реальные объявления, аккаунты и заявки пока отключены.';
  $('#modalBackdrop').classList.remove('hidden');
  if (window.gsap) gsap.fromTo('.modal',{y:24,opacity:0,scale:.97},{y:0,opacity:1,scale:1,duration:.35,ease:'power3.out'});
}
function closeModal() { $('#modalBackdrop').classList.add('hidden'); }
function card(item) {
  const found = item.kind === 'Найдено';
  const emoji = ({wallet:'👛',headphones:'🎧','key-round':'🔑',backpack:'🎒',watch:'⌚',umbrella:'☂️'})[item.icon] || '📦';
  return `<article class="listing-card" data-id="${item.id}" tabindex="0" role="button" aria-label="Подробнее: ${item.title}">
    <div class="listing-art" style="background:linear-gradient(145deg,${item.color}22,${item.color}44)"><span class="listing-badge ${found?'badge-found':'badge-lost'}">${found?'Найдено':'Потеряно'}</span><span class="art-emoji">${emoji}</span></div>
    <div class="listing-content"><div class="listing-meta"><span>${item.category}</span><span>${item.date}</span></div><h3>${item.title}</h3><div class="listing-place"><i data-lucide="map-pin"></i>${item.place}</div><div class="listing-bottom"><span class="org-mini"><span><i data-lucide="building-2"></i></span>${item.org}</span><span class="card-arrow"><i data-lucide="arrow-up-right"></i></span></div></div>
  </article>`;
}
function render() {
  const q = $('#searchInput').value.trim().toLowerCase();
  const category = $('#categorySelect').value;
  const filtered = items.filter(x => (!q || [x.title,x.category,x.place,x.description].join(' ').toLowerCase().includes(q)) && (activeKind==='Все'||x.kind===activeKind) && (category==='Все'||x.category===category));
  grid.innerHTML = filtered.map(card).join('');
  empty.classList.toggle('hidden', filtered.length > 0);
  grid.style.display = filtered.length ? 'grid' : 'none';
  $('#resultsCount').textContent = 'Показано ' + filtered.length + ' из ' + items.length + ' объявлений';
  if (window.lucide) lucide.createIcons();
  if (window.gsap && filtered.length) gsap.fromTo('.listing-card',{opacity:0,y:14},{opacity:1,y:0,duration:.42,stagger:.06,ease:'power2.out'});
}
async function loadItems() {
  try {
    const response = await fetch('/api/listings');
    if (!response.ok) throw new Error('api');
    const data = await response.json();
    items = data.items?.length ? data.items : demoItems;
  } catch { items = demoItems; }
  render();
}
$('#kindFilters').addEventListener('click', e => {
  const button = e.target.closest('[data-kind]');
  if (!button) return;
  activeKind = button.dataset.kind;
  document.querySelectorAll('.filter').forEach(x => x.classList.toggle('active', x===button));
  render();
});
$('#searchInput').addEventListener('input', render);
$('#categorySelect').addEventListener('change', render);
$('#searchBtn').addEventListener('click', () => { render(); $('#catalog').scrollIntoView({behavior:'smooth'}); });
$('#viewAll').addEventListener('click', () => { $('#searchInput').value=''; $('#categorySelect').value='Все'; activeKind='Все'; document.querySelectorAll('.filter').forEach(x=>x.classList.toggle('active',x.dataset.kind==='Все')); render(); });
$('#resetFilters').addEventListener('click', () => { $('#searchInput').value=''; $('#categorySelect').value='Все'; activeKind='Все'; document.querySelectorAll('.filter').forEach(x=>x.classList.toggle('active',x.dataset.kind==='Все')); render(); });
grid.addEventListener('click', e => { const c=e.target.closest('.listing-card'); if(!c)return; const item=items.find(x=>x.id===c.dataset.id); if(item) openDemo(item.title, item.description+' Это демонстрационная карточка, поэтому заявка на возврат пока не отправляется.'); });
grid.addEventListener('keydown', e => { if(e.key==='Enter' && e.target.classList.contains('listing-card')) e.target.click(); });
['lostBtn','foundBtn','loginBtn','orgBtn','mobileMenu'].forEach(id => $('#'+id)?.addEventListener('click', () => openDemo(id==='orgBtn'?'Подключение организации':id==='loginBtn'?'Вход в аккаунт':id==='lostBtn'?'Сообщить о пропаже':id==='foundBtn'?'Опубликовать находку':'Меню Topdim', 'Функция будет доступна после подготовки безопасной регистрации, модерации и юридических документов. Сейчас никакие персональные данные не собираются.')));
$('#langBtn').addEventListener('click', () => notify('Переключение UZ / RU / EN появится в следующем обновлении.'));
$('#modalClose').addEventListener('click', closeModal);
$('#modalOk').addEventListener('click', closeModal);
$('#modalBackdrop').addEventListener('click', e => { if(e.target === $('#modalBackdrop')) closeModal(); });
document.addEventListener('keydown', e => { if((e.metaKey||e.ctrlKey)&&e.key.toLowerCase()==='k'){e.preventDefault();$('#searchInput').focus();} if(e.key==='Escape')closeModal(); });
if(window.gsap){
  gsap.from('.hero-copy > *',{y:22,opacity:0,duration:.7,stagger:.09,ease:'power3.out',delay:.1});
  gsap.from('.phone-mock',{y:30,opacity:0,rotate:0,duration:1,ease:'power3.out',delay:.25});
  gsap.from('.float-card',{y:18,opacity:0,duration:.7,stagger:.15,ease:'back.out(1.5)',delay:.65});
  gsap.to('.card-wallet',{y:-9,duration:2.4,repeat:-1,yoyo:true,ease:'sine.inOut'});
  gsap.to('.card-safe',{y:8,duration:2.8,repeat:-1,yoyo:true,ease:'sine.inOut'});
  gsap.utils.toArray('.step-card,.org-panel,.safety-section').forEach(el=>gsap.from(el,{scrollTrigger:undefined,opacity:0,y:25,duration:.7,ease:'power2.out',paused:true,onComplete:()=>{}}));
}
if(window.lucide) lucide.createIcons();
loadItems();
