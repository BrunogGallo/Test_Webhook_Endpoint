import express from 'express';

const app = express();
const PORT = process.env.PORT ?? 3000;

// Parse JSON (common for webhooks)
app.use(express.json());

// Webhook endpoint – accepts POST requests
app.post('/webhook', (req, res) => {
  console.log('--- Webhook received ---');
  console.log('Headers:', JSON.stringify(req.headers, null, 2));
  console.log('Body:', req.body);
  console.log('------------------------');
  res.status(200).json({ received: true });
});

// Optional: catch-all POST for testing (e.g. POST /)
app.post('/', (req, res) => {
  console.log('--- POST received at / ---');
  console.log('Headers:', JSON.stringify(req.headers, null, 2));
  console.log('Body:', req.body);
  console.log('------------------------');
  res.status(200).json({ received: true });
});

app.listen(PORT, () => {
  console.log(`Webhook listener running at http://localhost:${PORT}`);
  console.log(`  POST http://localhost:${PORT}/webhook`);
});
