// Launcher behind `npm run dev`: starts `next dev --turbopack` on this
// worktree's pinned UI port.
//
// Next reads its port from argv/process.env at CLI-parse time, BEFORE it loads
// .env files, so a UI_PORT line in ui/.env cannot reach it on its own -- this
// shim bridges the two. scripts/worktree-sync-env.sh assigns a unique UI_PORT
// per git worktree and derives CORS_ALLOWED_ORIGINS + UI_APP_URL in api/.env
// from it, so the backend's origin allowlist matches the port this UI binds.
//
// With UI_PORT unset -- the default for a plain clone -- no -p is passed and
// `next dev` behaves exactly as it did before: port 3000, auto-incrementing if
// busy. An exported UI_PORT wins over the ui/.env value. Extra args are
// forwarded, so `npm run dev -- --hostname 0.0.0.0` still works.
//
// Plain node, no dependencies: npm runs scripts through cmd.exe on Windows,
// where shell substitution in package.json would not expand.
import { spawn } from 'node:child_process';
import { readFileSync } from 'node:fs';
import { dirname, join } from 'node:path';
import { fileURLToPath } from 'node:url';

const uiRoot = join(dirname(fileURLToPath(import.meta.url)), '..');

/** Last UI_PORT assignment in ui/.env, or null when unset/absent. */
function pinnedPort() {
    let contents;
    try {
        contents = readFileSync(join(uiRoot, '.env'), 'utf8');
    } catch {
        return null;
    }
    // Last occurrence wins, matching how dotenv-style loaders resolve dupes.
    const matches = [...contents.matchAll(/^[ \t]*UI_PORT[ \t]*=[ \t]*"?(\d+)"?[ \t]*$/gm)];
    return matches.length > 0 ? matches[matches.length - 1][1] : null;
}

const publicPort = process.env.UI_PORT || pinnedPort() || '3010';
const internalPort = process.env.INTERNAL_WEB_PORT || '3011';
const gatewayScript = join(uiRoot, 'scripts', 'audible-gateway.mjs');

// Spawn Next's JS entry on internal port
const nextChild = spawn(
    process.execPath,
    [
        join(uiRoot, 'node_modules', 'next', 'dist', 'bin', 'next'),
        'dev',
        '--turbopack',
        '-p', internalPort,
        ...process.argv.slice(2),
    ],
    {
        cwd: uiRoot,
        stdio: 'inherit',
        env: { ...process.env, UI_PORT: internalPort, PORT: internalPort },
    }
);

// Spawn Audible AI Gateway on the public port (3010)
const gatewayChild = spawn(
    process.execPath,
    [gatewayScript],
    {
        cwd: uiRoot,
        stdio: 'inherit',
        env: {
            ...process.env,
            UI_PORT: publicPort,
            INTERNAL_WEB_PORT: internalPort,
            API_PORT: process.env.API_PORT || '8000',
        },
    }
);

function cleanup() {
    try { nextChild.kill(); } catch {}
    try { gatewayChild.kill(); } catch {}
}

process.on('SIGINT', () => { cleanup(); process.exit(0); });
process.on('SIGTERM', () => { cleanup(); process.exit(0); });

nextChild.on('exit', (code, signal) => {
    cleanup();
    process.exit(signal ? 1 : (code ?? 0));
});

gatewayChild.on('exit', (code, signal) => {
    cleanup();
    process.exit(signal ? 1 : (code ?? 0));
});
