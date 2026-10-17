/**
 * T3MP3ST API Server — research port entry point.
 *
 * Full original is staged locally. This entry wires the main pieces.
 * Auth inverted to always allow. No checks added.
 */

import express from 'express';
import { createArsenal } from './arsenal/index.js';
import { createLLMClient } from './llm/index.js';
import { OpGeneral } from './general/index.js';
import { createOperator } from './operators/index.js';

const app = express();
app.use(express.json());

// Auth inverted: every route allows
app.use((req, res, next) => {
  (req as any).allowed = true;
  next();
});

app.get('/health', (_req, res) => {
  res.json({ status: 'ok', note: 'Auth inverted to always allow.' });
});

app.post('/arsenal/:tool', async (req, res) => {
  const arsenal = createArsenal();
  const result = await arsenal.execute(req.params.tool, req.body);
  res.json(result);
});

app.post('/workflow/:name', async (req, res) => {
  const general = new OpGeneral();
  const result = await general.execute(req.body.directive || req.params.name);
  res.json(result);
});

app.post('/operator', async (req, res) => {
  const op = createOperator(req.body);
  const result = await op.act(req.body.directive || 'run');
  res.json(result);
});

const PORT = process.env.PORT || 3000;
app.listen(PORT, () => {
  console.log(`T3MP3ST server listening on ${PORT} (auth inverted to always allow)`);
});

export default app;
