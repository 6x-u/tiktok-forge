// Minimal browser shim to host TikTok's webmssdk bundle outside a browser.
// Purpose: exercise the vendor SDK's own signing entry (byted_acrawler.frontierSign)
// so signatures are produced by the real engine instead of a reimplementation.

const fs = require('fs');
const vm = require('vm');
const path = require('path');

const NOOP = () => {};

function makeStorage() {
  const m = new Map();
  return {
    getItem: (k) => (m.has(k) ? m.get(k) : null),
    setItem: (k, v) => m.set(k, String(v)),
    removeItem: (k) => m.delete(k),
    clear: () => m.clear(),
    key: (i) => Array.from(m.keys())[i] ?? null,
    get length() { return m.size; },
  };
}

function makeClassList(el) {
  return {
    add: NOOP, remove: NOOP, toggle: NOOP, contains: () => false,
    item: () => null, get length() { return 0; },
  };
}

function makeElement(tag) {
  const el = {
    tagName: String(tag || 'div').toUpperCase(),
    nodeName: String(tag || 'div').toUpperCase(),
    nodeType: 1,
    style: {},
    dataset: {},
    children: [],
    childNodes: [],
    attributes: {},
    innerHTML: '',
    outerHTML: '',
    textContent: '',
    className: '',
    id: '',
    src: '',
    href: '',
    width: 1920,
    height: 1080,
    clientWidth: 1920,
    clientHeight: 937,
    offsetWidth: 1920,
    offsetHeight: 937,
    scrollWidth: 1920,
    scrollHeight: 937,
    clientTop: 0,
    clientLeft: 0,
    offsetTop: 0,
    offsetLeft: 0,
    classList: makeClassList(),
    appendChild: (c) => { el.children.push(c); el.childNodes.push(c); return c; },
    removeChild: (c) => c,
    insertBefore: (c) => c,
    replaceChild: (c) => c,
    setAttribute: (k, v) => { el.attributes[k] = String(v); if (k === 'src') el.src = String(v); },
    getAttribute: (k) => (k in el.attributes ? el.attributes[k] : null),
    removeAttribute: (k) => { delete el.attributes[k]; },
    hasAttribute: (k) => k in el.attributes,
    addEventListener: NOOP,
    removeEventListener: NOOP,
    dispatchEvent: () => true,
    attachShadow: () => makeElement('div'),
    getBoundingClientRect: () => ({
      top: 0, left: 0, right: 1920, bottom: 937, width: 1920, height: 937, x: 0, y: 0,
    }),
    getElementsByTagName: (t) => (String(t).toLowerCase() === 'script' ? [] : []),
    querySelector: () => null,
    querySelectorAll: () => [],
    focus: NOOP, blur: NOOP, click: NOOP, cloneNode: () => makeElement(tag),
    canvasContext: null,
    getContext: null,
  };
  return el;
}

function makeCanvas() {
  const el = makeElement('canvas');
  el.getContext = (kind) => {
    if (kind === '2d') {
      return {
        fillRect: NOOP, clearRect: NOOP, getImageData: (x, y, w, h) => ({
          data: new Uint8ClampedArray(Math.max(4, (w | 0) * (h | 0) * 4)), width: w, height: h,
        }),
        putImageData: NOOP, drawImage: NOOP, createImageData: () => ({ data: new Uint8ClampedArray(4) }),
        measureText: (t) => ({ width: String(t).length * 7.2 }),
        fillText: NOOP, strokeText: NOOP, beginPath: NOOP, closePath: NOOP,
        moveTo: NOOP, lineTo: NOOP, arc: NOOP, fill: NOOP, stroke: NOOP,
        translate: NOOP, rotate: NOOP, scale: NOOP, save: NOOP, restore: NOOP,
        setTransform: NOOP, createLinearGradient: () => ({ addColorStop: NOOP }),
        getContextAttributes: () => ({ alpha: true }),
        canvas: el,
      };
    }
    if (kind === 'webgl' || kind === 'experimental-webgl') {
      return makeWebGL(el);
    }
    return null;
  };
  el.toDataURL = () => 'data:image/png;base64,iVBORw0KGgoAAAANSUhEUgAAAAEAAAABCAYAAAAfFcSJAAAADUlEQVR42mP8z8BQDwAEhQGAhKmMIQAAAABJRU5ErkJggg==';
  return el;
}

function makeWebGL(canvas) {
  const ext = {
    UNMASKED_VENDOR_WEBGL: 0x9245,
    UNMASKED_RENDERER_WEBGL: 0x9246,
  };
  const ctx = {
    canvas,
    VENDOR: 0x1F00,
    RENDERER: 0x1F01,
    VERSION: 0x1F02,
    SHADING_LANGUAGE_VERSION: 0x8B8C,
    MAX_TEXTURE_SIZE: 0x0D33,
    getParameter: (p) => {
      switch (p) {
        case 0x1F00: return 'WebKit';
        case 0x1F01: return 'WebKit WebGL';
        case 0x1F02: return 'WebGL 1.0 (OpenGL ES 2.0 Chromium)';
        case 0x8B8C: return 'WebGL GLSL ES 1.0 (OpenGL ES GLSL ES 1.0 Chromium)';
        case 0x0D33: return 16384;
        case 0x9245: return 'Google Inc. (NVIDIA)';
        case 0x9246: return 'ANGLE (NVIDIA, NVIDIA GeForce RTX 3060 Direct3D11 vs_5_0 ps_5_0, D3D11)';
        default: return 4096;
      }
    },
    getExtension: (n) => (String(n).toLowerCase().includes('unmasked') ? ext : null),
    getSupportedExtensions: () => ['WEBGL_debug_renderer_info'],
    getShaderPrecisionFormat: () => ({ precision: 23, rangeMin: 127, rangeMax: 127 }),
    createBuffer: () => ({}), bindBuffer: NOOP, bufferData: NOOP,
    createProgram: () => ({}), createShader: () => ({}), shaderSource: NOOP,
    compileShader: NOOP, attachShader: NOOP, linkProgram: NOOP, useProgram: NOOP,
    getProgramParameter: () => true, getShaderParameter: () => true,
    getAttribLocation: () => 0, getUniformLocation: () => ({}),
    enableVertexAttribArray: NOOP, vertexAttribPointer: NOOP, drawArrays: NOOP,
    clearColor: NOOP, clear: NOOP, viewport: NOOP, disable: NOOP, enable: NOOP,
    readPixels: NOOP, getError: () => 0,
  };
  return ctx;
}

function buildSandbox(opts) {
  const userAgent = opts.userAgent;
  const cookieJar = new Map();
  for (const part of String(opts.cookie || '').split(';')) {
    const i = part.indexOf('=');
    if (i > 0) cookieJar.set(part.slice(0, i).trim(), part.slice(i + 1).trim());
  }

  const location = {
    href: 'https://www.tiktok.com/',
    origin: 'https://www.tiktok.com',
    protocol: 'https:',
    host: 'www.tiktok.com',
    hostname: 'www.tiktok.com',
    port: '',
    pathname: '/',
    search: '',
    hash: '',
    reload: NOOP,
    assign: NOOP,
    replace: NOOP,
    toString: () => 'https://www.tiktok.com/',
  };

  const documentObj = {
    readyState: 'complete',
    visibilityState: 'visible',
    hidden: false,
    referrer: 'https://www.tiktok.com/',
    title: 'TikTok - Make Your Day',
    URL: 'https://www.tiktok.com/',
    documentURI: 'https://www.tiktok.com/',
    characterSet: 'UTF-8',
    charset: 'UTF-8',
    inputEncoding: 'UTF-8',
    contentType: 'text/html',
    compatMode: 'CSS1Compat',
    cookie: {
      toString: () => Array.from(cookieJar.entries()).map(([k, v]) => `${k}=${v}`).join('; '),
    },
    location,
    domain: 'tiktok.com',
    createElement: (t) => (String(t).toLowerCase() === 'canvas' ? makeCanvas() : makeElement(t)),
    createElementNS: (ns, t) => (String(t).toLowerCase() === 'canvas' ? makeCanvas() : makeElement(t)),
    createTextNode: (t) => ({ nodeType: 3, textContent: String(t), nodeValue: String(t) }),
    createDocumentFragment: () => makeElement('fragment'),
    getElementById: () => null,
    getElementsByTagName: (t) => (String(t).toLowerCase() === 'head' ? [makeElement('head')] : []),
    getElementsByClassName: () => [],
    getElementsByName: () => [],
    querySelector: (sel) => (String(sel).includes('script') ? null : makeElement('div')),
    querySelectorAll: () => [],
    addEventListener: NOOP,
    removeEventListener: NOOP,
    dispatchEvent: () => true,
    hasFocus: () => true,
    elementFromPoint: () => null,
    execCommand: () => true,
    write: NOOP,
    open: NOOP,
    close: NOOP,
    get scripts() { return []; },
    get all() { return []; },
  };
  // real cookie string + setter support
  Object.defineProperty(documentObj, 'cookie', {
    configurable: true,
    get() {
      return Array.from(cookieJar.entries()).map(([k, v]) => `${k}=${v}`).join('; ');
    },
    set(v) {
      const first = String(v).split(';')[0];
      const i = first.indexOf('=');
      if (i > 0) cookieJar.set(first.slice(0, i).trim(), first.slice(i + 1).trim());
    },
  });

  const navigatorObj = {
    userAgent,
    appName: 'Netscape',
    appVersion: userAgent.replace('Mozilla/', ''),
    appCodeName: 'Mozilla',
    platform: 'Win32',
    product: 'Gecko',
    productSub: '20030107',
    vendor: 'Google Inc.',
    vendorSub: '',
    language: 'en-US',
    languages: ['en-US', 'en'],
    onLine: true,
    cookieEnabled: true,
    doNotTrack: null,
    hardwareConcurrency: 8,
    deviceMemory: 8,
    maxTouchPoints: 0,
    webdriver: false,
    plugins: [],
    mimeTypes: [],
    permissions: { query: () => Promise.resolve({ state: 'prompt' }) },
    sendBeacon: () => true,
    javaEnabled: () => false,
    getBattery: () => Promise.resolve({ charging: true, level: 1 }),
    userAgentData: {
      brands: [
        { brand: 'Chromium', version: '141' },
        { brand: 'Google Chrome', version: '141' },
        { brand: 'Not?A_Brand', version: '24' },
      ],
      mobile: false,
      platform: 'Windows',
      getHighEntropyValues: () => Promise.resolve({
        architecture: 'x86', bitness: '64', model: '', platformVersion: '15.0.0',
        uaFullVersion: '141.0.0.0', fullVersionList: [],
      }),
    },
  };

  const performanceObj = {
    now: () => Number(process.hrtime.bigint() / 1000n) / 1000,
    timeOrigin: Date.now() - 1000,
    mark: NOOP, measure: NOOP, clearMarks: NOOP, clearMeasures: NOOP,
    getEntries: () => [], getEntriesByType: () => [], getEntriesByName: () => [],
    timing: { navigationStart: Date.now() - 1500 },
    memory: { jsHeapSizeLimit: 4294705152, totalJSHeapSize: 30000000, usedJSHeapSize: 20000000 },
  };

  const sandbox = {
    console: { log: NOOP, info: NOOP, warn: NOOP, error: NOOP, debug: NOOP, trace: NOOP, table: NOOP, group: NOOP, groupEnd: NOOP, time: NOOP, timeEnd: NOOP },
    document: documentObj,
    navigator: navigatorObj,
    location,
    performance: performanceObj,
    screen: { width: 1920, height: 1080, availWidth: 1920, availHeight: 1040, colorDepth: 24, pixelDepth: 24, orientation: { type: 'landscape-primary', angle: 0 } },
    innerWidth: 1920, innerHeight: 937, outerWidth: 1920, outerHeight: 1040,
    devicePixelRatio: 1, screenX: 0, screenY: 0, screenLeft: 0, screenTop: 0,
    scrollX: 0, scrollY: 0, pageXOffset: 0, pageYOffset: 0,
    localStorage: makeStorage(),
    sessionStorage: makeStorage(),
    history: { length: 2, state: null, pushState: NOOP, replaceState: NOOP, back: NOOP, forward: NOOP, go: NOOP },
    crypto: {
      getRandomValues: (arr) => {
        const bytes = require('crypto').randomBytes(arr.length * (arr.BYTES_PER_ELEMENT || 1));
        const view = new Uint8Array(bytes.buffer, bytes.byteOffset, bytes.length);
        if (arr instanceof Uint8Array) arr.set(view.subarray(0, arr.length));
        else for (let i = 0; i < arr.length; i++) arr[i] = view[i] % 0xffffffff;
        return arr;
      },
      randomUUID: () => require('crypto').randomUUID(),
      subtle: {},
    },
    addEventListener: NOOP,
    removeEventListener: NOOP,
    dispatchEvent: () => true,
    getComputedStyle: () => ({ getPropertyValue: () => '', length: 0, item: () => '' }),
    matchMedia: () => ({ matches: false, addListener: NOOP, removeListener: NOOP, addEventListener: NOOP, removeEventListener: NOOP }),
    requestAnimationFrame: (cb) => setTimeout(() => cb(performanceObj.now()), 16),
    cancelAnimationFrame: (id) => clearTimeout(id),
    setTimeout, clearTimeout, setInterval, clearInterval, queueMicrotask,
    fetch: () => Promise.reject(new Error('offline')),
    XMLHttpRequest: function XHR() {
      this.open = NOOP; this.send = NOOP; this.setRequestHeader = NOOP;
      this.getAllResponseHeaders = () => ''; this.getResponseHeader = () => null;
      this.abort = NOOP; this.addEventListener = NOOP; this.readyState = 0;
      this.status = 0; this.responseText = ''; this.withCredentials = false;
    },
    WebSocket: function WS() { this.send = NOOP; this.close = NOOP; this.addEventListener = NOOP; },
    Worker: function W() { this.postMessage = NOOP; this.terminate = NOOP; this.addEventListener = NOOP; },
    Image: function Img() { this.width = 1; this.height = 1; this.src = ''; this.addEventListener = NOOP; Object.defineProperty(this, 'onload', { set: NOOP, get: () => null }); },
    TextEncoder, TextDecoder, URL, URLSearchParams, Blob: function Blob() {}, FormData: function FormData() { this.append = NOOP; },
    atob: (s) => Buffer.from(String(s), 'base64').toString('binary'),
    btoa: (s) => Buffer.from(String(s), 'binary').toString('base64'),
    Event: function Event(t) { this.type = t; }, CustomEvent: function CustomEvent(t) { this.type = t; },
    KeyboardEvent: function KeyboardEvent(t) { this.type = t; },
    MouseEvent: function MouseEvent(t) { this.type = t; },
    ErrorEvent: function ErrorEvent(t) { this.type = t; },
    Promise, Array, Object, Math, Date, JSON, RegExp, String, Number, Boolean,
    Uint8Array, Uint16Array, Uint32Array, Int8Array, Int16Array, Int32Array,
    Float32Array, Float64Array, ArrayBuffer, DataView, Map, Set, WeakMap, WeakSet,
    Reflect, Proxy, Symbol, BigInt, Intl, parseInt, parseFloat, isNaN, isFinite,
    encodeURIComponent, decodeURIComponent, encodeURI, decodeURI, escape, unescape,
    Float16Array: undefined,
    Request: class Request { constructor(u, o) { this.url = String(u); this.method = (o && o.method) || 'GET'; this.headers = new Map(); } clone() { return this; } },
    Response: class Response { constructor(b) { this.body = b; this.ok = true; this.status = 200; } json() { return Promise.resolve({}); } text() { return Promise.resolve(''); } },
    Headers: class Headers { constructor() { this.m = new Map(); } get(k) { return this.m.get(k) ?? null; } set(k, v) { this.m.set(k, v); } append(k, v) { this.m.set(k, v); } has(k) { return this.m.has(k); } forEach(fn) { this.m.forEach((v, k) => fn(v, k)); } },
    AbortController: class AbortController { constructor() { this.signal = { aborted: false, addEventListener: NOOP, removeEventListener: NOOP, onabort: null }; } abort() { this.signal.aborted = true; } },
    AbortSignal: { timeout: () => ({ aborted: false, addEventListener: NOOP }) },
    ReadableStream: function ReadableStream() {},
    process: undefined,
  };
  sandbox.window = sandbox;
  sandbox.self = sandbox;
  sandbox.globalThis = sandbox;
  sandbox.top = sandbox;
  sandbox.parent = sandbox;
  sandbox.frames = sandbox;
  sandbox.frameElement = null;
  sandbox.ActiveXObject = undefined;
  sandbox.opera = undefined;
  // document.defaultView must point back
  documentObj.defaultView = sandbox;
  documentObj.implementation = { createHTMLDocument: () => documentObj };
  return sandbox;
}

module.exports = { buildSandbox };
