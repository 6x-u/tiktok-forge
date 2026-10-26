'use strict';
// Persistent signing server.
//
// Protocol: JSON per line on stdin, JSON per line on stdout.
//   in : {"id":1,"op":"sign","url":"...","referer":"...","body":"...","aid":1988,"cookie":"ttwid=.."}
//   out: {"id":1,"ok":true,"data":{"X-Bogus":"..."}}
// Ops: ping | warm | info | sign | quit
//
// The bundle is evaluated once; every request after that reuses the live
// context, so a signature costs a few hundred microseconds instead of a
// full JS bootstrap.

const fs = require('fs');
const vm = require('vm');
const path = require('path');
const readline = require('readline');
const { buildSandbox } = require('./shim');

const DEFAULT_UA = 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 '
  + '(KHTML, like Gecko) Chrome/141.0.0.0 Safari/537.36';

function createEngine(opts) {
  const bundlePath = opts.bundlePath || path.join(__dirname, 'webmssdk.js');
  const code = fs.readFileSync(bundlePath, 'utf8');
  const sandbox = buildSandbox({
    userAgent: opts.userAgent || DEFAULT_UA,
    cookie: opts.cookie || 'ttwid=',
  });
  const context = vm.createContext(sandbox);
  vm.runInContext(code, context, { filename: bundlePath, timeout: 30000 });

  const acrawler = sandbox.byted_acrawler;
  if (!acrawler || typeof acrawler.frontierSign !== 'function') {
    throw new Error('bundle did not expose byted_acrawler.frontierSign');
  }

  const engine = {
    context,
    sandbox,
    acrawler,
    bundle: path.basename(bundlePath),
    aid: null,
    userAgent: opts.userAgent || DEFAULT_UA,

    setCookie(cookie) {
      if (typeof cookie !== 'string' || !cookie.length) return;
      sandbox.document.cookie = cookie;
    },

    setUserAgent(ua) {
      if (!ua || ua === this.userAgent) return;
      this.userAgent = ua;
      sandbox.navigator.userAgent = ua;
      sandbox.navigator.appVersion = ua.replace('Mozilla/', '');
    },

    ensureAid(aid) {
      const value = Number(aid) || 1988;
      if (this.aid === value) return;
      if (typeof this.acrawler.init === 'function') {
        try { this.acrawler.init({ aid: value }); } catch (e) { /* older bundles */ }
      }
      this.aid = value;
    },

    sign(req) {
      const url = String(req.url || '');
      if (!url) throw new Error('url is required');
      this.setUserAgent(req.userAgent);
      this.setCookie(req.cookie);
      this.ensureAid(req.aid);
      const args = { url };
      if (req.body) args.body = String(req.body);
      if (req.referer) args.referer = String(req.referer);
      const result = this.acrawler.frontierSign(args);
      if (typeof result === 'string') return { 'X-Bogus': result };
      if (result && typeof result === 'object') return result;
      return {};
    },
  };

  sandbox.__ttEngine = engine;
  return engine;
}

function main() {
  const argv = process.argv.slice(2);
  const opts = {};
  for (let i = 0; i < argv.length; i += 2) {
    const key = String(argv[i] || '').replace(/^--/, '');
    if (key) opts[key] = argv[i + 1];
  }

  let engine;
  try {
    engine = createEngine(opts);
  } catch (err) {
    process.stdout.write(JSON.stringify({ id: 0, ok: false, error: 'boot: ' + err.message }) + '\n');
    process.exit(1);
  }

  // boot handshake: the Python side blocks on this line before it sends work
  process.stdout.write(JSON.stringify({
    id: 0, ok: true, data: { ready: true, bundle: engine.bundle },
  }) + '\n');

  const rl = readline.createInterface({ input: process.stdin, crlfDelay: Infinity });
  rl.on('line', (line) => {
    const text = line.trim();
    if (!text) return;
    let msg;
    try { msg = JSON.parse(text); } catch (e) {
      process.stdout.write(JSON.stringify({ id: 0, ok: false, error: 'bad json' }) + '\n');
      return;
    }
    const id = msg.id ?? 0;
    try {
      switch (msg.op) {
        case 'ping':
          process.stdout.write(JSON.stringify({ id, ok: true, data: { pong: true } }) + '\n');
          break;
        case 'info':
          process.stdout.write(JSON.stringify({
            id, ok: true, data: { bundle: engine.bundle, aid: engine.aid, ua: engine.userAgent },
          }) + '\n');
          break;
        case 'warm': {
          const data = engine.sign({ url: 'https://www.tiktok.com/api/post/item_list/?aid=1988&count=1', aid: 1988 });
          process.stdout.write(JSON.stringify({ id, ok: true, data }) + '\n');
          break;
        }
        case 'sign': {
          const data = engine.sign(msg);
          process.stdout.write(JSON.stringify({ id, ok: true, data }) + '\n');
          break;
        }
        case 'quit':
          process.stdout.write(JSON.stringify({ id, ok: true, data: null }) + '\n');
          rl.close();
          process.exit(0);
          break;
        default:
          process.stdout.write(JSON.stringify({ id, ok: false, error: 'unknown op' }) + '\n');
      }
    } catch (err) {
      process.stdout.write(JSON.stringify({ id, ok: false, error: String(err && err.message) }) + '\n');
    }
  });
  rl.on('close', () => process.exit(0));
}

main();
