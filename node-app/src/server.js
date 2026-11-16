const app = require('./app');

const port = process.env.PORT || 3000;
app.listen(port, '0.0.0.0', () => {
  console.log(`demo-node-app listening on ${port}`);
});
