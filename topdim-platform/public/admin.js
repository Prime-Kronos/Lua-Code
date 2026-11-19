"use strict";
let csrfToken="";
const $=id=>document.getElementById(id);
async function api(url,options={}){
 const headers={"Accept":"application/json",...(options.headers||{})};
 if(options.body)headers["Content-Type"]="application/json";
 if(csrfToken&&options.method&&options.method!=="GET")headers["X-CSRF-Token"]=csrfToken;
 const response=await fetch(url,{...options,headers,credentials:"same-origin"});
 const data=await response.json().catch(()=>({}));
 if(!response.ok)throw new Error(data.error||"Ошибка запроса");
 return data;
}
function showDashboard(){ $("login").classList.add("hidden");$("dashboard").classList.remove("hidden");$("logout").classList.remove("hidden"); }
function showLogin(){ $("dashboard").classList.add("hidden");$("login").classList.remove("hidden");$("logout").classList.add("hidden");csrfToken=""; }
$("loginForm").addEventListener("submit",async e=>{
 e.preventDefault();$("loginMsg").textContent="Проверяем данные…";$("loginMsg").className="notice";
 $("loginBtn").disabled=true;
 try{const data=await api("/api/admin/login",{method:"POST",body:JSON.stringify({email:$("email").value,password:$("password").value})});csrfToken=data.csrfToken;showDashboard();await loadQueue();}
 catch(err){$("loginMsg").textContent=err.message;$("loginMsg").className="notice error";}
 finally{$("loginBtn").disabled=false;}
});
async function loadQueue(){
 $("queueMsg").textContent="Загружаем…";const box=$("list");box.replaceChildren();
 try{const data=await api("/api/admin/submissions");
 if(!data.items.length){$("queueMsg").textContent="Новых объявлений на проверку нет.";return;}
 $("queueMsg").textContent="";
 for(const item of data.items){
  const card=document.createElement("article");card.className="item";
  const img=document.createElement("img");img.alt="Фото предмета";img.loading="lazy";img.src="/api/admin/submissions/"+encodeURIComponent(item.id)+"/photo";
  const content=document.createElement("div");
  const title=document.createElement("h3");title.textContent=item.title;
  const meta=document.createElement("div");meta.className="meta";meta.textContent=[item.kind,item.category,item.area,item.date].join(" · ");
  const desc=document.createElement("p");desc.className="desc";desc.textContent=item.description;
  const actions=document.createElement("div");actions.className="actions";
  const approve=document.createElement("button");approve.textContent="Одобрить";approve.addEventListener("click",()=>review(item.id,"approved",approve));
  const reject=document.createElement("button");reject.textContent="Отклонить";reject.className="danger";reject.addEventListener("click",()=>review(item.id,"rejected",reject));
  actions.append(approve,reject);content.append(title,meta,desc,actions);card.append(img,content);box.append(card);
 }
 }catch(err){$("queueMsg").textContent=err.message;$("queueMsg").className="notice error";if(err.message.includes("Войдите")||err.message.includes("сессия"))showLogin();}
}
async function review(id,status,button){button.disabled=true;try{await api("/api/admin/submissions/"+encodeURIComponent(id),{method:"PATCH",body:JSON.stringify({status})});await loadQueue();}catch(err){$("queueMsg").textContent=err.message;$("queueMsg").className="notice error";button.disabled=false;}}
$("refresh").addEventListener("click",loadQueue);
$("logout").addEventListener("click",async()=>{try{await api("/api/admin/logout",{method:"POST",body:"{}"});}catch{}showLogin();});
(async()=>{try{const data=await api("/api/admin/me");csrfToken=data.csrfToken;showDashboard();await loadQueue();}catch{showLogin();}})();