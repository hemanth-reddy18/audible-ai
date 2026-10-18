/**
 * Audible AI — Unified Single-Origin Reverse Proxy Gateway.
 *
 * Exposes a single public entry point on port 3010 that transparently routes:
 *   - /api/v1/*        -> FastAPI Backend (port 8000)
 *   - /docs, /openapi.json -> FastAPI Swagger & OpenAPI (port 8000)
 *   - /api/v1/ws/*     -> FastAPI WebSockets (port 8000, bi-directional audio)
 *   - /_next/webpack-hmr -> Next.js HMR WebSocket (port 3011)
 *   - /*               -> Next.js Web Frontend (port 3011)
 */

import http from 'node:http';
import net from 'node:net';

const GATEWAY_PORT = parseInt(process.env.UI_PORT || process.env.GATEWAY_PORT || '3010', 10);
const WEB_PORT = parseInt(process.env.INTERNAL_WEB_PORT || '3011', 10);
const API_PORT = parseInt(process.env.API_PORT || '8000', 10);
const HOST = '0.0.0.0';

function isApiRoute(url) {
    if (!url) return false;
    return (
        url.startsWith('/api/v1') ||
        url.startsWith('/docs') ||
        url === '/openapi.json'
    );
}

function normalizeTargetPath(url) {
    if (url === '/openapi.json') return '/api/v1/openapi.json';
    if (url === '/api/v1/docs') return '/docs';
    return url;
}

const server = http.createServer((req, res) => {
    const isApi = isApiRoute(req.url);
    const targetPort = isApi ? API_PORT : WEB_PORT;
    const targetHost = '127.0.0.1';
    const targetPath = isApi ? normalizeTargetPath(req.url) : req.url;

    const headers = { ...req.headers };
    headers['x-forwarded-host'] = req.headers.host || `localhost:${GATEWAY_PORT}`;
    headers['x-forwarded-proto'] = 'http';
    headers['x-forwarded-for'] = req.socket.remoteAddress || '127.0.0.1';
    headers.host = `127.0.0.1:${targetPort}`;

    const proxyReq = http.request(
        {
            host: targetHost,
            port: targetPort,
            path: targetPath,
            method: req.method,
            headers,
        },
        (proxyRes) => {
            res.writeHead(proxyRes.statusCode, proxyRes.headers);
            proxyRes.pipe(res);
        }
    );

    proxyReq.on('error', (err) => {
        if (!res.headersSent) {
            res.writeHead(502, { 'Content-Type': 'application/json' });
            res.end(
                JSON.stringify({
                    error: 'Bad Gateway',
                    message: `Audible AI Gateway could not connect to ${isApi ? 'API' : 'Web'} service on port ${targetPort}`,
                    detail: err.message,
                })
            );
        }
    });

    req.pipe(proxyReq);
});

// Handle WebSocket upgrade events
server.on('upgrade', (req, clientSocket, head) => {
    clientSocket.on('error', () => {
        try { clientSocket.destroy(); } catch {}
    });

    const isApiWs = req.url && (req.url.startsWith('/api/v1/ws') || req.url.startsWith('/ws'));
    const targetPort = isApiWs ? API_PORT : WEB_PORT;

    const targetSocket = net.connect(targetPort, '127.0.0.1', () => {
        let raw = `${req.method} ${req.url} HTTP/${req.httpVersion}\r\n`;
        for (let i = 0; i < req.rawHeaders.length; i += 2) {
            const key = req.rawHeaders[i];
            const val = key.toLowerCase() === 'host' ? `127.0.0.1:${targetPort}` : req.rawHeaders[i + 1];
            raw += `${key}: ${val}\r\n`;
        }
        raw += `x-forwarded-host: ${req.headers.host || `localhost:${GATEWAY_PORT}`}\r\n`;
        raw += `x-forwarded-proto: http\r\n`;
        raw += '\r\n';

        targetSocket.write(raw);
        if (head && head.length > 0) {
            targetSocket.write(head);
        }

        targetSocket.pipe(clientSocket);
        clientSocket.pipe(targetSocket);
    });

    targetSocket.on('error', (err) => {
        try {
            clientSocket.write('HTTP/1.1 502 Bad Gateway\r\nSec-WebSocket-Version: 13\r\n\r\n');
            clientSocket.destroy();
        } catch {}
    });
});

server.listen(GATEWAY_PORT, HOST, () => {
    console.log(`[Audible Gateway] Single-Origin Gateway online at http://localhost:${GATEWAY_PORT}`);
    console.log(`[Audible Gateway]   -> Routing /api/v1/*, /docs, /openapi.json to FastAPI (port ${API_PORT})`);
    console.log(`[Audible Gateway]   -> Routing WebSocket upgrades to FastAPI WS (port ${API_PORT})`);
    console.log(`[Audible Gateway]   -> Routing all UI pages and assets to Next.js (port ${WEB_PORT})`);
});
