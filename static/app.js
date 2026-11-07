const dishes=[
{id:"sazan",name:"Сазан на мангале",cat:"fish",price:185000,weight:"1 кг",desc:"Ароматный сазан с пряностями, приготовленный на углях.",img:"https://images.unsplash.com/photo-1510130387422-82bed34b37e9?auto=format&fit=crop&w=800&q=82",tag:"Фирменное"},
{id:"fried",name:"Сазан жареный",cat:"fish",price:165000,weight:"1 кг",desc:"Золотистая корочка, нежное мясо и лимонная подача.",img:"https://images.unsplash.com/photo-1519708227418-c8fd9a32b7a2?auto=format&fit=crop&w=800&q=82",tag:"Популярное"},
{id:"trout",name:"Форель на гриле",cat:"fish",price:220000,weight:"1 шт.",desc:"Форель с травами и лёгким цитрусовым ароматом.",img:"https://images.unsplash.com/photo-1515003197210-e0cd7184f8b5?auto=format&fit=crop&w=800&q=82",tag:"Рекомендуем"},
{id:"catfish",name:"Сом жареный",cat:"fish",price:175000,weight:"1 кг",desc:"Сочная рыба с хрустящей корочкой и специями.",img:"https://images.unsplash.com/photo-1535399831218-d5bd36d1a6b3?auto=format&fit=crop&w=800&q=82",tag:"Классика"},
{id:"potato",name:"Картофель по-домашнему",cat:"hot",price:28000,weight:"200 г",desc:"Румяный картофель с зеленью и чесночным маслом.",img:"https://images.unsplash.com/photo-1518013431117-eb1465fa5752?auto=format&fit=crop&w=800&q=82",tag:"Гарнир"},
{id:"veg",name:"Овощи на гриле",cat:"hot",price:35000,weight:"250 г",desc:"Сезонные овощи, обжаренные на открытом огне.",img:"https://images.unsplash.com/photo-1547592180-85f173990554?auto=format&fit=crop&w=800&q=82",tag:"Лёгкое"},
{id:"achichuk",name:"Салат Ачичук",cat:"salad",price:22000,weight:"200 г",desc:"Томаты, лук и свежая зелень.",img:"https://images.unsplash.com/photo-1512621776951-a57141f2eefd?auto=format&fit=crop&w=800&q=82",tag:"Свежий"},
{id:"salad",name:"Овощной салат",cat:"salad",price:30000,weight:"250 г",desc:"Свежие овощи с фирменной заправкой.",img:"https://images.unsplash.com/photo-1540420773420-3366772f4999?auto=format&fit=crop&w=800&q=82",tag:"Лёгкий"},
{id:"lemonade",name:"Домашний лимонад",cat:"drink",price:30000,weight:"1 л",desc:"Лимон, мята и прохладная свежесть.",img:"https://images.unsplash.com/photo-1513558161293-cdaf765edfd4?auto=format&fit=crop&w=800&q=82",tag:"Освежающий"},
{id:"tea",name:"Чайник чая",cat:"drink",price:18000,weight:"1 чайник",desc:"Ароматный горячий чай для компании.",img:"https://images.unsplash.com/photo-1544787219-7f47ccb76574?auto=format&fit=crop&w=800&q=82",tag:"Традиция"}];
const money=n=>new Intl.NumberFormat("ru-RU").format(n)+" сум";
const cart={};
const sid=localStorage.getItem("amu_session")||(crypto.randomUUID?crypto.randomUUID():"amu-"+Math.random().toString(36).slice(2)+Date.now());
localStorage.setItem("amu_session",sid);
let last=Number(localStorage.getItem("amu_last")||0),rating=5;
const $=id=>document.getElementById(id);
function toast(t){$("toast").textContent=t;$("toast").classList.add("show");clearTimeout(toast.timer);toast.timer=setTimeout(()=>$("toast").classList.remove("show"),3300)}
function render(cat="all"){$("menuGrid").innerHTML=dishes.filter(x=>cat==="all"||x.cat===cat).map(x=>'<article class="dish"><img loading="lazy" src="'+x.img+'" alt="'+x.name+'"><div class="dish-body"><div class="dish-top"><h3>'+x.name+'</h3><span class="price">'+money(x.price)+'</span></div><p>'+x.desc+'</p><div class="dish-foot"><small>'+x.weight+' · '+x.tag+'</small><button data-add="'+x.id+'">＋ Добавить</button></div></div></article>').join("")}
function items(){return Object.keys(cart).filter(k=>cart[k]>0).map(k=>({...dishes.find(x=>x.id===k),qty:cart[k]}))}
function total(){return items().reduce((s,x)=>s+x.price*x.qty,0)}
function drawCart(){const all=items();$("cartCount").textContent=all.reduce((s,x)=>s+x.qty,0);$("cartTotal").textContent=money(total());$("cartItems").innerHTML=all.length?all.map(x=>'<div class="cart-row"><div><strong>'+x.name+'</strong><small>'+money(x.price)+' · '+x.weight+'</small></div><div class="qty"><button data-qty="'+x.id+'" data-d="-1">−</button><b>'+x.qty+'</b><button data-qty="'+x.id+'" data-d="1">＋</button></div></div>').join(""):"Корзина пока пуста 🐟"}
function drawersClose(){$("drawer").classList.remove("open");$("noticePanel").classList.remove("open");$("shade").classList.remove("show")}
function modal(id){drawersClose();$(id).classList.add("show")}
function modalClose(id){$(id).classList.remove("show")}
async function post(path,data){const r=await fetch(path,{method:"POST",headers:{"Content-Type":"application/json"},body:JSON.stringify(data)});const d=await r.json().catch(()=>({}));if(!r.ok)throw new Error(d.detail||"Не удалось отправить.");return d}
$("menuGrid").addEventListener("click",e=>{const b=e.target.closest("[data-add]");if(!b)return;cart[b.dataset.add]=(cart[b.dataset.add]||0)+1;drawCart();toast("Добавлено в корзину")});
$("categories").addEventListener("click",e=>{const b=e.target.closest("[data-cat]");if(!b)return;document.querySelectorAll("[data-cat]").forEach(x=>x.classList.remove("active"));b.classList.add("active");render(b.dataset.cat)});
$("cartItems").addEventListener("click",e=>{const b=e.target.closest("[data-qty]");if(!b)return;const id=b.dataset.qty;cart[id]=Math.max(0,(cart[id]||0)+Number(b.dataset.d));if(!cart[id])delete cart[id];drawCart()});
$("openCart").onclick=()=>{$("drawer").classList.add("open");$("shade").classList.add("show")};
$("closeCart").onclick=drawersClose;$("shade").onclick=drawersClose;
$("checkout").onclick=()=>{if(!items().length)return toast("Сначала добавьте блюда в корзину.");modal("checkoutModal")};
$("heroWaiter").onclick=()=>modal("waiterModal");$("openReview").onclick=()=>modal("reviewModal");
document.querySelectorAll(".close-modal").forEach(b=>b.onclick=()=>b.closest(".modal").classList.remove("show"));
$("checkoutForm").onsubmit=async e=>{e.preventDefault();const f=new FormData(e.target),btn=e.target.querySelector("button[type=submit]");btn.disabled=true;btn.textContent="Отправляем...";try{const result=await post("/api/orders",{session_id:sid,customer_name:String(f.get("customer_name")).trim(),phone:String(f.get("phone")).trim(),table:String(f.get("table")).trim(),payment:f.get("payment"),items:items().map(x=>({name:x.name,quantity:x.qty,price:x.price})),total:total(),comment:String(f.get("comment")||"").trim()});Object.keys(cart).forEach(k=>delete cart[k]);drawCart();modalClose("checkoutModal");e.target.reset();toast("Заказ "+result.order_id+" отправлен!");}catch(err){toast(err.message)}finally{btn.disabled=false;btn.textContent="Отправить заказ →"}};
$("waiterForm").onsubmit=async e=>{e.preventDefault();const f=new FormData(e.target),btn=e.target.querySelector("button[type=submit]");btn.disabled=true;try{await post("/api/waiter",{session_id:sid,table:String(f.get("table")).trim(),message:String(f.get("message")||"").trim()});modalClose("waiterModal");e.target.reset();toast("Вызов официанта отправлен!")}catch(err){toast(err.message)}finally{btn.disabled=false}};
$("stars").onclick=e=>{const b=e.target.closest("[data-rate]");if(!b)return;rating=Number(b.dataset.rate);document.querySelectorAll("[data-rate]").forEach(x=>x.classList.toggle("sel",Number(x.dataset.rate)<=rating))};
$("reviewForm").onsubmit=async e=>{e.preventDefault();const f=new FormData(e.target),btn=e.target.querySelector("button[type=submit]");btn.disabled=true;try{await post("/api/reviews",{session_id:sid,name:String(f.get("name")||"Гость").trim(),rating,text:String(f.get("text")).trim()});modalClose("reviewModal");e.target.reset();toast("Спасибо! Отзыв отправлен ресторану.")}catch(err){toast(err.message)}finally{btn.disabled=false}};
$("notifications").onclick=()=>{$("noticePanel").classList.add("open");$("shade").classList.add("show")};$("closeNotice").onclick=drawersClose;
function addNotice(x){const list=$("noticeList");if(list.textContent.includes("Пока уведомлений"))list.textContent="";const row=document.createElement("div");row.className="notice";const small=document.createElement("small");small.textContent=x.type==="admin_reply"?"ОТВЕТ РЕСТОРАНА":x.type==="order_status"?"СТАТУС ЗАКАЗА":x.type==="waiter"?"ОФИЦИАНТ":"ЗАКАЗ";const text=document.createElement("div");text.textContent=x.message;row.append(small,text);list.prepend(row);toast(x.message)}
async function poll(){try{const r=await fetch("/api/notifications?session_id="+encodeURIComponent(sid)+"&after="+last);if(!r.ok)return;const d=await r.json();for(const x of d.items||[]){addNotice(x);last=Math.max(last,x.id);localStorage.setItem("amu_last",String(last))}}catch(e){}}
setInterval(poll,3500);poll();
const google="https://search.google.com/local/writereview?placeid=ChIJQz9yTABfrjgRfbTF7kyjdyM",apple="https://maps.apple.com/?q=Amu%20Sazan&address=Ziyokor%201-tor%20ko%27chasi%2C%209%2C%20Tashkent%2C%20Uzbekistan";
$("googleLink").href=google;$("appleLink").href=apple;
function qr(id,url){if(window.QRCode)QRCode.toCanvas($(id),url,{width:180,margin:1,color:{dark:"#14231d",light:"#ffffff"}},err=>{if(err)$(id).insertAdjacentText("afterend",url)});else $(id).insertAdjacentText("afterend",url)}
qr("qrMenu",location.origin+"/#menu");qr("qrGoogle",google);qr("qrApple",apple);
render();drawCart();