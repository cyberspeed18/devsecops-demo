const express = require('express');
const _ = require('lodash');

const app = express();

app.get('/', (req, res) => {
  res.json({ service: 'demo-node-app', message: 'Hello from the DevSecOps demo' });
});

app.get('/health', (req, res) => {
  res.json({ status: 'ok' });
});

app.get('/api/greet', (req, res) => {
  const name = _.capitalize(String(req.query.name || 'world')).slice(0, 50);
  res.json({ greeting: `Hello, ${name}!` });
});

module.exports = app;
