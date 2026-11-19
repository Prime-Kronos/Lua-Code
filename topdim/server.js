const express = require('express');
const helmet = require('helmet');
const path = require('path');
const { Pool } = require('pg');

const app = express();
const PORT = process.env.PORT || 3000;
app.disable('x-powered-by');
app.use(helmet({ contentSecurityPolicy: false }));
app.use(express.json({ limit: '20kb' }));

const demoItems = [
  { id: 'td-1001', title: 'Чёрный кошелёк', category: 'Аксессуары', kind: 'Найдено', place: 'Ташкент · Мирзо-Улугбекский район', date: 'Сегодня', description: 'Найден рядом с парком. Владелец сможет подтвердить содержимое.', org: 'Частный пользователь', color: '#263246', icon: 'wallet' },
  { id: 'td-1002', title: 'Беспроводные наушники', category: 'Электроника', kind: 'Потеряно', place: 'Ташкент · метро Космонавтлар', date: 'Вчера', description: 'Белый кейс, без указания серийного номера в открытом доступе.', org: 'Частный пользователь', color: '#e8edf6', icon: 'headphones' },
  { id: 'td-1003', title: 'Связка ключей', category: 'Ключи', kind: 'Найдено', place: 'Ташкент · Юнусабад', date: '18 ноя', description: 'Несколько ключей на кольце. Детали доступны после проверки заявки.', org: 'Учебный центр · демо', color: '#d6b46a', icon: 'key-round' },
  { id: 'td-1004', title: 'Детский рюкзак', category: 'Сумки', kind: 'Найдено', place: 'Ташкент · Чиланзар', date: '17 ноя', description: 'Передан на стойку информации учреждения. Не публикуем личные данные.', org: 'Организация · демо', color: '#cf8f77', icon: 'backpack' },
  { id: 'td-1005', title: 'Смарт-часы', category: 'Электроника', kind: 'Потеряно', place: 'Ташкент · Бунёдкор', date: '16 ноя', description: 'Тёмный ремешок. Для подтверждения владельца потребуется дополнительная проверка.', org: 'Частный пользователь', color: '#343c4c', icon: 'watch' },
  { id: 'td-1006', title: 'Зонт', category: 'Другое', kind: 'Найдено', place: 'Ташкент · Шайхантахур', date: '15 ноя', description: 'Найден в общественном месте. Свяжитесь с ответственным учреждением.', org: 'Организация · демо', color: '#8ca4bb', icon: 'umbrella' }
];

let pool = null;
if (process.env.DATABASE_URL) {
  pool = new Pool({
    connectionString: process.env.DATABASE_URL,
    ssl: { rejectUnauthorized: false },
    max: 3,
    idleTimeoutMillis: 10000,
    connectionTimeoutMillis: 8000
  });
}

async function initDb() {
  if (!pool) return;
  await pool.query(`
    CREATE TABLE IF NOT EXISTS demo_listings (
      id TEXT PRIMARY KEY,
      title TEXT NOT NULL,
      category TEXT NOT NULL,
      kind TEXT NOT NULL,
      place TEXT NOT NULL,
      date_label TEXT NOT NULL,
      description TEXT NOT NULL,
      org TEXT NOT NULL,
      color TEXT NOT NULL,
      icon TEXT NOT NULL
    )
  `);
  const count = await pool.query('SELECT COUNT(*)::int AS n FROM demo_listings');
  if (count.rows[0].n === 0) {
    for (const x of demoItems) {
      await pool.query(
        'INSERT INTO demo_listings (id,title,category,kind,place,date_label,description,org,color,icon) VALUES ($1,$2,$3,$4,$5,$6,$7,$8,$9,$10) ON CONFLICT DO NOTHING',
        [x.id,x.title,x.category,x.kind,x.place,x.date,x.description,x.org,x.color,x.icon]
      );
    }
  }
}

app.get('/api/health', async (_req, res) => {
  let database = 'demo-fallback';
  if (pool) {
    try { await pool.query('SELECT 1'); database = 'connected'; }
    catch { database = 'unavailable'; }
  }
  res.json({ ok: true, app: 'Topdim', mode: 'demo-read-only', database });
});

app.get('/api/listings', async (req, res) => {
  const q = String(req.query.q || '').slice(0, 80).toLowerCase();
  const category = String(req.query.category || '').slice(0, 40);
  const kind = String(req.query.kind || '').slice(0, 20);
  try {
    let items = demoItems;
    if (pool) {
      const result = await pool.query('SELECT id,title,category,kind,place,date_label AS date,description,org,color,icon FROM demo_listings ORDER BY id');
      if (result.rows.length) items = result.rows;
    }
    items = items.filter(x => (!q || [x.title,x.category,x.place,x.description].join(' ').toLowerCase().includes(q)) && (!category || category === 'Все' || x.category === category) && (!kind || kind === 'Все' || x.kind === kind));
    res.json({ items, total: items.length, mode: 'demo-read-only' });
  } catch {
    res.status(503).json({ error: 'Каталог временно недоступен' });
  }
});

app.use(express.static(path.join(__dirname, 'public')));
app.get('*', (_req, res) => res.sendFile(path.join(__dirname, 'public', 'index.html')));

initDb().then(() => {
  app.listen(PORT, '0.0.0.0', () => console.log('Topdim listening on ' + PORT));
}).catch(err => {
  console.error('Database initialization failed:', err.message);
  app.listen(PORT, '0.0.0.0', () => console.log('Topdim running in fallback demo mode'));
});
