import express from 'express';

const app = express();
const PORT = process.env.PORT ?? 3000;

// Parse JSON (common for webhooks)
app.use(express.json());

// Webhook endpoint – accepts POST requests
app.post('/webhook', (req, res) => {
  data = req.body
  return_id = data.get("id")
  console.log('--- Webhook received ---');
  console.log('Headers:', JSON.stringify(req.headers, null, 2));
  console.log('Body:', return_id);
  console.log('------------------------');
  res.status(200).json({ received: true });
});

app.listen(PORT, () => {
  console.log(`Webhook listener running at http://localhost:${PORT}`);
  console.log(`  POST http://localhost:${PORT}/webhook`);
});
