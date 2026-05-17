import fs from 'node:fs';
import http from 'node:http';
import path from 'node:path';
import { fileURLToPath } from 'node:url';

const __dirname = path.dirname(fileURLToPath(import.meta.url));
const defaultEnvFile = path.resolve(__dirname, '../../backend/.env');

const parseEnvValue = (value) => {
  const trimmed = value.trim();
  if ((trimmed.startsWith('"') && trimmed.endsWith('"')) || (trimmed.startsWith("'") && trimmed.endsWith("'"))) {
    return trimmed.slice(1, -1);
  }
  return trimmed;
};

const loadEnvFile = () => {
  const envFile = process.env.MIDSCENE_ENV_FILE || defaultEnvFile;
  if (process.env.MIDSCENE_ENV_FILE === '0' || !fs.existsSync(envFile)) return;

  for (const line of fs.readFileSync(envFile, 'utf8').split(/\r?\n/)) {
    const trimmed = line.trim();
    if (!trimmed || trimmed.startsWith('#')) continue;
    const separator = trimmed.indexOf('=');
    if (separator === -1) continue;
    const key = trimmed.slice(0, separator).trim();
    const value = parseEnvValue(trimmed.slice(separator + 1));
    if (!(key in process.env)) process.env[key] = value;
  }
};

const configureMidsceneEnv = () => {
  loadEnvFile();

  process.env.MIDSCENE_MODEL_NAME ||= process.env.MODEL_RIGHT_PUPIL_VL || 'qwen-vl-max-latest';
  process.env.MIDSCENE_MODEL_FAMILY ||= 'qwen2.5-vl';
  process.env.MIDSCENE_MODEL_API_KEY ||= process.env.QWEN_API_KEY;
  process.env.MIDSCENE_MODEL_BASE_URL ||= process.env.QWEN_BASE_URL;
  process.env.OPENAI_API_KEY ||= process.env.MIDSCENE_MODEL_API_KEY;
  process.env.OPENAI_BASE_URL ||= process.env.MIDSCENE_MODEL_BASE_URL;
};

configureMidsceneEnv();

const PORT = Number(process.env.PORT || 8787);
const HOST = process.env.HOST || '127.0.0.1';
const DRY_RUN = process.argv.includes('--real') ? false : process.argv.includes('--dry-run') || process.env.MIDSCENE_DRY_RUN === '1';

const json = (res, statusCode, body) => {
  res.writeHead(statusCode, { 'content-type': 'application/json; charset=utf-8' });
  res.end(JSON.stringify(body));
};

const readJson = async (req) => {
  const chunks = [];
  for await (const chunk of req) chunks.push(chunk);
  const raw = Buffer.concat(chunks).toString('utf8');
  return raw ? JSON.parse(raw) : {};
};

const normalizeAction = (step) => String(step.action_type || step.action || '').toLowerCase();

const buildInstruction = (step) => {
  const action = normalizeAction(step);
  const target = step.target || step.description || '';
  const value = step.value || step.params?.text || '';

  if (action === 'goto') return null;
  if (action === 'type') return `在${target}输入${value}`;
  if (action === 'click') return `点击${target}`;
  if (action === 'assert') return value ? `确认${target}显示${value}` : `确认${target}`;
  if (action === 'scroll') return `滚动到${target}`;
  if (action === 'wait') return `等待${target || value || '页面稳定'}`;
  return step.description || `${action} ${target}`.trim();
};

const dryRun = async (payload) => {
  const steps = payload.case?.steps || [];
  return {
    success: true,
    status: 'passed',
    duration_ms: 0,
    trace_id: `MIDSCENE_DRY_${Date.now()}`,
    steps: steps.map((step, index) => ({
      step_index: index,
      success: true,
      duration_ms: 0,
      description: step.description || step.action_type || `step ${index + 1}`,
      details: {
        step_name: step.description || step.action_type || `step ${index + 1}`,
        step_type: 'UI',
        action_taken: normalizeAction(step),
        target_description: step.target || step.description || '',
        strategy: 'midscene_dry_run',
      },
    })),
  };
};

const loadRuntime = async () => {
  const [{ chromium }, midscene] = await Promise.all([
    import('playwright'),
    import('@midscene/web/playwright'),
  ]);
  const Agent = midscene.PlaywrightAgent;
  if (!Agent) throw new Error('@midscene/web/playwright PlaywrightAgent export was not found');
  return { chromium, Agent };
};

const screenshotDataUri = async (page) => {
  const screenshot = await page.screenshot({ type: 'png', fullPage: true });
  return `data:image/png;base64,${screenshot.toString('base64')}`;
};

const runCase = async (payload) => {
  if (DRY_RUN) return dryRun(payload);

  const { chromium, Agent } = await loadRuntime();
  const browser = await chromium.launch({ headless: process.env.HEADLESS !== '0' });
  const page = await browser.newPage();
  const agent = new Agent(page);
  const startedAt = Date.now();
  const results = [];

  try {
    for (const [index, step] of (payload.case?.steps || []).entries()) {
      const stepStartedAt = Date.now();
      const action = normalizeAction(step);
      const instruction = buildInstruction(step);

      if (action === 'goto') {
        const url = step.url || step.value || payload.context?.base_url;
        if (!url) throw new Error('GOTO step requires url or value');
        await page.goto(url);
      } else if (action === 'assert') {
        await agent.aiAssert(instruction);
      } else if (instruction) {
        await agent.aiAction(instruction);
      }

      const screenshotAfter = await screenshotDataUri(page);
      results.push({
        step_index: index,
        success: true,
        duration_ms: Date.now() - stepStartedAt,
        screenshot: screenshotAfter,
        description: step.description || instruction || action,
        details: {
          step_name: step.description || instruction || action,
          step_type: 'UI',
          action_taken: action,
          target_description: step.target || step.description || '',
          screenshot_after: screenshotAfter,
          page_url: page.url(),
          strategy: 'midscene',
        },
      });
    }

    return {
      success: true,
      status: 'passed',
      duration_ms: Date.now() - startedAt,
      trace_id: `MIDSCENE_${Date.now()}`,
      steps: results,
    };
  } catch (error) {
    try {
      const screenshotAfter = await screenshotDataUri(page);
      results.push({
        step_index: results.length,
        success: false,
        duration_ms: 0,
        screenshot: screenshotAfter,
        error: error instanceof Error ? error.message : String(error),
        details: {
          step_name: 'execution_error',
          step_type: 'UI',
          action_taken: 'error',
          screenshot_after: screenshotAfter,
          page_url: page.url(),
          strategy: 'midscene',
        },
      });
    } catch {}

    return {
      success: false,
      status: 'failed',
      duration_ms: Date.now() - startedAt,
      trace_id: `MIDSCENE_${Date.now()}`,
      error: error instanceof Error ? error.message : String(error),
      steps: results,
    };
  } finally {
    await browser.close();
  }
};

const server = http.createServer(async (req, res) => {
  try {
    if (req.method === 'GET' && req.url === '/health') {
      json(res, 200, { status: 'ok', dry_run: DRY_RUN });
      return;
    }

    if (req.method === 'POST' && req.url === '/run') {
      const payload = await readJson(req);
      const result = await runCase(payload);
      json(res, 200, result);
      return;
    }

    json(res, 404, { error: 'not_found' });
  } catch (error) {
    json(res, 500, { success: false, status: 'error', error: error instanceof Error ? error.message : String(error) });
  }
});

server.listen(PORT, HOST, () => {
  console.log(`Midscene runner listening on http://${HOST}:${PORT}`);
});
