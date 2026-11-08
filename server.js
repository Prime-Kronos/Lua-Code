const http = require('http');
const fs = require('fs');
const path = require('path');
const crypto = require('crypto');
const PORT = process.env.PORT || 3000;
const DATA = path.join(__dirname, 'data.json');
const ADMIN_USER = process.env.ADMIN_USER || 'owner';
const ADMIN_PASS = process.env.ADMIN_PASS || 'ChangeMe-2026!';
const sessions = new Set();
const seed = {
  restaurants:[{id:'r1',name:'Demo Restaurant',description:'Sample menu for preview',category:'Restaurant'}],
  menu:[{id:'m1',restaurantId:'r1',name:'Osh',description:'Traditional rice dish',price:35000,category:'Main'},{id:'m2',restaurantId:'r1',name:'Somsa',description:'Baked pastry',price:12000,category:'Snack'},{id:'m3',restaurantId:'r1',name:'Limonad',description:'Fresh lemonade',price:10000,category:'Drink'}],
  hotels:[{id:'h1',name:'Demo Hotel',city:'Tashkent',description:'Sample accommodation'}],
  rooms:[{id:'room1',hotelId:'h1',name:'Standard room',capacity:2,price:280000},{id:'room2',hotelId:'h1',name:'Family room',capacity:4,price:450000}],
  services:[{id:'s1',name:'Beauty appointment',description:'Sample service',duration:60,price:100000},{id:'s2',name:'Consultation',description:'Sample consultation',duration:30,price:50000}],
  orders:[],bookings:[],appointments:[]
};
function load(){try{return JSON.parse(fs.readFileSync(DATA,'utf8'))}catch{return structuredClone(seed)}}
let db=load();
function save(){fs.writeFileSync(DATA,JSON.stringify(db,null,2))}
function send(res,status,obj){res.writeHead(status,{'Content-Type':'application/json; charset=utf-8','Access-Control-Allow-Origin':'*'});res.end(JSON.stringify(obj))}
function readBody(req){return new Promise((resolve,reject)=>{let s='';req.on('data',c=>{s+=c;if(s.length>1e6)reject(new Error('Body too large'))});req.on('end',()=>{try{resolve(s?JSON.parse(s):{})}catch{reject(new Error('Invalid JSON'))}})})}
function authorized(req){const t=(req.headers.authorization||'').replace(/^Bearer /,'');return sessions.has(t)}
const mime={'.html':'text/html; charset=utf-8','.css':'text/css; charset=utf-8','.js':'text/javascript; charset=utf-8','.json':'application/json; charset=utf-8','.webmanifest':'application/manifest+json'};
const server=http.createServer(async(req,res)=>{
  if(req.method==='OPTIONS'){res.writeHead(204,{'Access-Control-Allow-Origin':'*','Access-Control-Allow-Headers':'Content-Type, Authorization','Access-Control-Allow-Methods':'GET,POST,PATCH,OPTIONS'});return res.end()}
  const url=new URL(req.url,'http://localhost');
  try{
    if(req.method==='GET'&&url.pathname==='/api/catalog')return send(res,200,{restaurants:db.restaurants,menu:db.menu,hotels:db.hotels,rooms:db.rooms,services:db.services});
    if(req.method==='POST'&&['/api/orders','/api/bookings','/api/appointments'].includes(url.pathname)){
      const body=await readBody(req);const type=url.pathname.split('/').pop();const key=type==='orders'?'orders':type==='bookings'?'bookings':'appointments';
      const item={id:crypto.randomUUID(),status:'new',createdAt:new Date().toISOString(),...body};
      if(!body.customer||!body.phone)return send(res,400,{error:'Name and phone are required'});
      db[key].unshift(item);save();return send(res,201,{ok:true,item});
    }
    if(req.method==='POST'&&url.pathname==='/api/admin/login'){
      const b=await readBody(req);if(b.username!==ADMIN_USER||b.password!==ADMIN_PASS)return send(res,401,{error:'Invalid login'});
      const token=crypto.randomBytes(32).toString('hex');sessions.add(token);return send(res,200,{token});
    }
    if(req.method==='GET'&&url.pathname==='/api/admin/requests'){
      if(!authorized(req))return send(res,401,{error:'Unauthorized'});
      return send(res,200,{orders:db.orders,bookings:db.bookings,appointments:db.appointments});
    }
    const match=url.pathname.match(/^\/api\/admin\/requests\/(orders|bookings|appointments)\/([^/]+)$/);
    if(req.method==='PATCH'&&match){
      if(!authorized(req))return send(res,401,{error:'Unauthorized'});
      const b=await readBody(req);const row=db[match[1]].find(x=>x.id===match[2]);if(!row)return send(res,404,{error:'Not found'});
      row.status=String(b.status||'new');save();return send(res,200,{ok:true,row});
    }
    if(req.method==='GET'){
      let p=url.pathname==='/'?'/index.html':url.pathname;
      const full=path.join(__dirname,'public',path.normalize(p).replace(/^([/\\])+/,''));if(!full.startsWith(path.join(__dirname,'public')))return send(res,403,{error:'Forbidden'});
      fs.readFile(full,(err,data)=>{if(err){res.writeHead(404);return res.end('Not found')}res.writeHead(200,{'Content-Type':mime[path.extname(full)]||'application/octet-stream'});res.end(data)});
      return;
    }
    send(res,404,{error:'Not found'});
  }catch(e){send(res,400,{error:e.message||'Request failed'})}
});
server.listen(PORT,()=>console.log('ELVARQ SYSTEMS running on '+PORT));
process.on('SIGINT',()=>{save();process.exit()});
