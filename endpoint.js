import express from 'express'
;
const app = express();
app.use(express.json()); // Essential to read the JSON from Two Boxes

// This is your "Endpoint"
app.post('/test-webhook', (req, res) => {
    console.log('Received data:', req.body);

    // 1. Process the data (e.g., save to DB or send to Slack)
    // 2. ALWAYS send a 200 response so they don't keep retrying
    res.status(200).send('Event Received');
});

const PORT = process.env.PORT || 3000;

// Add '0.0.0.0' here!
app.listen(PORT, '0.0.0.0', () => {
    console.log(`Server is live and reachable on port ${PORT}`);
});