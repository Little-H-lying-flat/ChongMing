#!/usr/bin/env node

import fs from 'node:fs';
import http from 'node:http';
import path from 'node:path';
import { fileURLToPath, pathToFileURL } from 'node:url';

const __filename = fileURLToPath(import.meta.url);
const __dirname = path.dirname(__filename);

const routes = [
  '/',
  '/visual-ui',
  '/executions',
  '/settings',
  '/model-config',
  '/api-auto',
  '/design',
  '/performance',
  '/phoenix',
  '/smart-ops',
  '/turbo',
];

const viewports = [
  { name: 'desktop', width: 1440, height: 1000 },
  { name: 'mobile', width: 390, height: 844 },
];

const defaultBaseUrl = process.env.VISUAL_QA_BASE_URL || 'http://127.0.0.1:3000';
const outDir = path.resolve(process.env.VISUAL_QA_OUT_DIR || 'visual-qa-output');

async function loadPlaywright() {
  const candidates = [
    'playwright',
    path.resolve(__dirname, '../../midscene-runner/node_modules/playwright/index.js'),
  ];

  for (const candidate of candidates) {
    try {
      const mod = await import(candidate.startsWith('.') || path.isAbsolute(candidate) ? pathToFileURL(candidate).href : candidate);
      return mod.chromium ? mod : mod.default;
    } catch {}
  }

  throw new Error('Playwright is not installed. Install it in frontend or run npm install in ../midscene-runner.');
}

function checkServer(url) {
  return new Promise((resolve) => {
    const parsed = new URL(url);
    const req = http.get({
      host: parsed.hostname,
      port: parsed.port || (parsed.protocol === 'https:' ? 443 : 80),
      path: '/',
      timeout: 3000,
    }, (res) => {
      res.resume();
      resolve(true);
    });
    req.on('error', () => resolve(false));
    req.on('timeout', () => {
      req.destroy();
      resolve(false);
    });
  });
}

function screenshotName(route, viewportName) {
  const routeName = route === '/' ? 'home' : route.replace(/^\//, '').replaceAll('/', '__');
  return `${viewportName}-${routeName}.png`;
}

async function main() {
  if (!(await checkServer(defaultBaseUrl))) {
    throw new Error(`Frontend is not reachable at ${defaultBaseUrl}. Start it first, or set VISUAL_QA_BASE_URL.`);
  }

  const { chromium } = await loadPlaywright();
  fs.mkdirSync(outDir, { recursive: true });

  const browser = await chromium.launch({ headless: true });
  const report = [];

  for (const viewport of viewports) {
    const page = await browser.newPage({ viewport, deviceScaleFactor: 1 });

    for (const route of routes) {
      const messages = [];
      const failedRequests = [];
      const onConsole = (msg) => {
        if (['error', 'warning'].includes(msg.type())) messages.push(`${msg.type()}: ${msg.text()}`);
      };
      const onPageError = (err) => messages.push(`pageerror: ${err.message}`);
      const onRequestFailed = (request) => failedRequests.push(`${request.failure()?.errorText || 'failed'} ${request.url()}`);

      page.on('console', onConsole);
      page.on('pageerror', onPageError);
      page.on('requestfailed', onRequestFailed);

      const started = Date.now();
      try {
        const response = await page.goto(`${defaultBaseUrl}${route}`, { waitUntil: 'networkidle', timeout: 45000 });
        await page.waitForTimeout(800);
        const screenshot = path.join(outDir, screenshotName(route, viewport.name));
        await page.screenshot({ path: screenshot, fullPage: true });
        const bodyText = await page.locator('body').innerText({ timeout: 5000 }).catch(() => '');

        report.push({
          route,
          viewport: viewport.name,
          status: response ? response.status() : null,
          ok: response ? response.ok() : false,
          elapsedMs: Date.now() - started,
          screenshot,
          bodyTextSample: bodyText.slice(0, 500),
          messages,
          failedRequests,
        });
      } catch (error) {
        report.push({ route, viewport: viewport.name, error: error.message, messages, failedRequests });
      } finally {
        page.off('console', onConsole);
        page.off('pageerror', onPageError);
        page.off('requestfailed', onRequestFailed);
      }
    }

    await page.close();
  }

  await browser.close();

  const reportPath = path.join(outDir, 'report.json');
  fs.writeFileSync(reportPath, JSON.stringify(report, null, 2), 'utf8');

  const summary = report.map(({ route, viewport, status, ok, error, messages, failedRequests }) => ({
    route,
    viewport,
    status,
    ok,
    error,
    warnings: messages.filter((m) => m.startsWith('warning:')).length,
    errors: messages.filter((m) => m.startsWith('error:') || m.startsWith('pageerror:')).length,
    failedRequests: failedRequests.length,
  }));

  console.log(JSON.stringify(summary, null, 2));
  console.log(`Visual QA report: ${reportPath}`);

  const hardFailures = report.filter((item) => item.error || item.ok === false || item.messages.some((m) => m.startsWith('pageerror:')));
  if (hardFailures.length > 0) {
    process.exitCode = 1;
  }
}

main().catch((error) => {
  console.error(error.message);
  process.exitCode = 1;
});
