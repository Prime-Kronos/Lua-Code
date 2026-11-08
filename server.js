const express = require('express');
const path = require('path');
const app = express();
const PORT = process.env.PORT || 3000;
app.use(express.json());
app.use(express.static(path.join(__dirname, 'public')));
app.get('/api/health', (_req, res) => res.json({ok:true, service:'izumrud-restaurant'}));
app.post('/api/orders', (req, res) => {
  const {items, type, table, customer} = req.body || {};
  if (!Array.isArray(items) || !items.length || !['dinein','takeaway'].includes(type)) {
    return res.status(400).json({ok:false, error:'Invalid order'});
  }
  // Order persistence and Telegram notifications are enabled after secure credentials are configured.
  res.status(202).json({ok:true, status:'received-demo', message:'Order form received. Staff integration is being configured.'});
});
app.get('*', (_req,res) => res.sendFile(path.join(__dirname,'public','index.html')));
app.listen(PORT, '0.0.0.0', () => console.log('Izumrud running on '+PORT));
