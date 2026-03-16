/**
 * AccuFlow WhatsApp Express Server — Multi-Client Edition
 * 
 * Single Node.js process managing multiple isolated WhatsApp sessions.
 * Each client gets their own Baileys connection, QR code, and auth folder.
 * 
 * Endpoints (all scoped by :clientId):
 *   GET  /health                                    - Server health check
 *   GET  /api/:clientId/qr.png                      - Client's QR code as PNG
 *   GET  /api/:clientId/status                      - Client's { linked: true/false }
 *   POST /api/:clientId/unlink                      - Unlink client's WhatsApp
 *   POST /api/:clientId/send-ledger                 - Send ledger to a customer
 *   POST /api/:clientId/send-balance-accounts       - Batch send balances
 *   POST /api/:clientId/send-address-row            - Send single address row
 *   POST /api/:clientId/send-address-rows           - Batch send address rows
 *   GET  /api/:clientId/send-progress/:jobId        - SSE progress stream
 *   GET  /api/:clientId/job-status/:jobId           - Polling job status
 *   POST /api/:clientId/cancel-job/:jobId           - Cancel batch job
 *   GET  /api/sessions                              - List all active sessions (admin)
 * 
 * No Redis/BullMQ — in-memory sequential sending with Poisson delays.
 */

import { makeWASocket, useMultiFileAuthState, Browsers, fetchLatestBaileysVersion, DisconnectReason } from '@whiskeysockets/baileys';
import express from 'express';
import cors from 'cors';
import QRCode from 'qrcode';
import pino from 'pino';
import fs from 'fs';
import path from 'path';
import { fileURLToPath } from 'url';
import { generateTradeTable } from './image.js';
import crypto from 'crypto';

// --- __dirname for ESM ---
const __filename = fileURLToPath(import.meta.url);
const __dirname = path.dirname(__filename);

// --- CONFIG ---
const PORT = process.env.NODE_PORT || process.env.PORT || 3005;
const NODE_ENV = process.env.NODE_ENV || 'development';
const API_KEY = process.env.WA_API_KEY || (NODE_ENV === 'development' ? 'accuflow-wa-dev-key-2024' : null);
if (!API_KEY) {
    console.error('FATAL: WA_API_KEY environment variable is required in production');
    process.exit(1);
}
const DJANGO_ORIGIN = process.env.DJANGO_ORIGIN || 'http://localhost:8000';
const DEV_WHATSAPP_NUMBER = process.env.DEV_WHATSAPP_NUMBER || '';

// Rate limiting & anti-ban — all configurable via env vars
const POISSON_LAMBDA_MINUTES = parseFloat(process.env.POISSON_DELAY || (NODE_ENV === 'development' ? '0.5' : '3'));
const GLOBAL_RATE_LIMIT = parseInt(process.env.RATE_LIMIT || (NODE_ENV === 'development' ? '20' : '10'));
const DAILY_MESSAGE_LIMIT = parseInt(process.env.DAILY_LIMIT || (NODE_ENV === 'development' ? '500' : '200'));
const START_HOUR_DUBAI = parseInt(process.env.SAFE_HOUR_START || (NODE_ENV === 'development' ? '0' : '8'));
const END_HOUR_DUBAI = parseInt(process.env.SAFE_HOUR_END || (NODE_ENV === 'development' ? '24' : '22'));

// Session management
const SESSION_INACTIVE_HOURS = parseInt(process.env.SESSION_INACTIVE_HOURS || '24');

// --- LOGGING ---
const logger = pino({ level: NODE_ENV === 'production' ? 'info' : 'debug' });

// --- MULTI-SESSION STATE ---
// Map<clientId, { sock, isConnected, isConnecting, currentQR, lastActive, messagesSentThisMinute }>
const activeSessions = new Map();

// In-memory job tracking for batch sends (shared across all clients)
const activeJobs = new Map();

// --- RATE LIMITER (per-client) ---
function startRateLimitReset() {
    setInterval(() => {
        activeSessions.forEach(session => {
            session.messagesSentThisMinute = 0;
        });
    }, 60000);
}

async function waitForRateLimit(session) {
    while (session.messagesSentThisMinute >= GLOBAL_RATE_LIMIT) {
        await new Promise(r => setTimeout(r, 2000));
    }
    if (session.messagesSentToday >= DAILY_MESSAGE_LIMIT) {
        throw new Error(`Daily message limit (${DAILY_MESSAGE_LIMIT}) reached. Resume tomorrow.`);
    }
}

// --- DAILY COUNTER RESET (midnight Dubai time) ---
function startDailyReset() {
    setInterval(() => {
        const now = new Date();
        const dubaiStr = now.toLocaleString('en-US', { timeZone: 'Asia/Dubai' });
        const dubaiHour = new Date(dubaiStr).getHours();
        const dubaiMin = new Date(dubaiStr).getMinutes();
        if (dubaiHour === 0 && dubaiMin < 5) {
            activeSessions.forEach(session => {
                if (session.messagesSentToday > 0) {
                    logger.info(`[${session.clientId}] Daily counter reset: ${session.messagesSentToday} msgs yesterday`);
                    session.messagesSentToday = 0;
                }
            });
        }
    }, 300000); // Check every 5 minutes
}

// --- UTILS ---
function isSafeTime() {
    if (START_HOUR_DUBAI === 0 && END_HOUR_DUBAI === 24) return true;
    const now = new Date();
    const dubaiTimeStr = now.toLocaleString("en-US", { timeZone: "Asia/Dubai" });
    const dubaiDate = new Date(dubaiTimeStr);
    const hour = dubaiDate.getHours();
    return hour >= START_HOUR_DUBAI && hour < END_HOUR_DUBAI;
}

function getPoissonDelay() {
    const poissonMs = -Math.log(Math.random()) * POISSON_LAMBDA_MINUTES * 60 * 1000;
    const minFloor = NODE_ENV === 'production' ? 60000 : 5000; // 60s prod, 5s dev
    const jitter = Math.random() * 30000; // 0-30s extra randomness
    return Math.max(minFloor, poissonMs) + jitter;
}

function formatPhone(number) {
    if (NODE_ENV === 'development' && DEV_WHATSAPP_NUMBER) {
        return DEV_WHATSAPP_NUMBER.replace(/[^0-9]/g, '') + '@s.whatsapp.net';
    }
    return String(number).replace(/[^0-9]/g, '') + '@s.whatsapp.net';
}

function isValidWhatsAppNumber(number) {
    if (!number) return false;
    const cleaned = String(number).replace(/[^0-9]/g, '');
    return cleaned.length >= 10 && cleaned.length <= 15;
}

function isValidclientId(clientId) {
    // Only allow safe characters: alphanumeric, underscore, hyphen
    return /^[a-zA-Z0-9_-]{3,50}$/.test(clientId);
}


// --- HUMAN-LIKE TYPING SIMULATION (Anti-Ban) ---
async function simulateTyping(sock, phone) {
    try {
        await sock.presenceSubscribe(phone);
        await sock.sendPresenceUpdate('composing', phone);
        const typingMs = 1000 + Math.random() * 3000; // 1-4 seconds
        await new Promise(r => setTimeout(r, typingMs));
        // Note: the act of sending the message automatically clears the composing state
        // but we explicitly send 'paused' just to be safe if the send is delayed
        await sock.sendPresenceUpdate('paused', phone);
    } catch (e) {
        // Non-critical — don't block send if presence fails
        logger.debug(`Typing simulation skipped: ${e.message}`);
    }
}

// --- MULTI-SESSION BAILEYS CONNECTION ---
async function getOrCreateSession(clientId) {
    if (activeSessions.has(clientId)) {
        const session = activeSessions.get(clientId);
        session.lastActive = Date.now();
        return session;
    }

    // Create a new session
    const session = {
        sock: null,
        isConnected: false,
        isConnecting: false,
        currentQR: null,
        lastActive: Date.now(),
        messagesSentThisMinute: 0,
        messagesSentToday: 0,
        reconnectAttempts: 0,
        clientId: clientId
    };
    activeSessions.set(clientId, session);

    // Start connection
    await connectSession(clientId);
    return session;
}

async function connectSession(clientId) {
    const session = activeSessions.get(clientId);
    if (!session || session.isConnecting) return;
    session.isConnecting = true;

    const authDir = path.join(__dirname, 'auth_info', clientId);

    try {
        // Ensure auth directory exists
        fs.mkdirSync(authDir, { recursive: true });

        const { state, saveCreds } = await useMultiFileAuthState(authDir);
        const { version } = await fetchLatestBaileysVersion();

        const sock = makeWASocket({
            version,
            logger: pino({ level: 'fatal' }),
            printQRInTerminal: false,
            auth: state,
            browser: Browsers.macOS('Desktop'),
            generateHighQualityLinkPreview: false,
            syncFullHistory: false,
            defaultQueryTimeoutMs: 60000,
            connectTimeoutMs: 60000,
            keepAliveIntervalMs: 10000
        });

        session.sock = sock;

        sock.ev.on('creds.update', saveCreds);

        sock.ev.on('connection.update', (update) => {
            const { connection, lastDisconnect, qr } = update;

            if (qr) {
                session.currentQR = qr;
                session.isConnected = false;
                logger.info(`[${clientId}] New QR code generated`);
            }

            if (connection === 'close') {
                session.isConnected = false;
                session.isConnecting = false;
                const statusCode = lastDisconnect?.error?.output?.statusCode;
                logger.warn(`[${clientId}] Connection closed (Status: ${statusCode})`);

                // Exponential backoff for reconnects
                session.reconnectAttempts = (session.reconnectAttempts || 0) + 1;
                const backoff = Math.min(3000 * Math.pow(2, session.reconnectAttempts - 1), 300000); // max 5 min

                if (statusCode === DisconnectReason.loggedOut || statusCode === 401) {
                    // Session expired — auto-clear stale auth
                    session.currentQR = null;
                    session.reconnectAttempts = 0;
                    if (fs.existsSync(authDir)) {
                        fs.rmSync(authDir, { recursive: true, force: true });
                        logger.info(`[${clientId}] 🗑️ Cleared stale auth — ready for new QR scan`);
                    }
                    setTimeout(() => connectSession(clientId), 3000);
                } else if (session.reconnectAttempts > 10) {
                    logger.error(`[${clientId}] ❌ Too many reconnect failures (${session.reconnectAttempts}). Stopping.`);
                    // Don't reconnect — likely banned or network issue
                } else {
                    logger.info(`[${clientId}] Reconnecting in ${(backoff/1000).toFixed(0)}s (attempt ${session.reconnectAttempts})...`);
                    setTimeout(() => connectSession(clientId), backoff);
                }
            } else if (connection === 'open') {
                session.isConnected = true;
                session.isConnecting = false;
                session.currentQR = null;
                session.lastActive = Date.now();
                session.reconnectAttempts = 0;
                logger.info(`[${clientId}] ✅ WhatsApp Connected`);
            }
        });

    } catch (err) {
        session.isConnecting = false;
        logger.error(`[${clientId}] Connection error: ${err.message}`);
        setTimeout(() => connectSession(clientId), 5000);
    }
}

// --- SESSION CLEANUP (unload inactive sessions) ---
function startSessionCleanup() {
    setInterval(() => {
        const now = Date.now();
        const maxInactive = SESSION_INACTIVE_HOURS * 60 * 60 * 1000;

        activeSessions.forEach((session, clientId) => {
            if (now - session.lastActive > maxInactive && !session.isConnected) {
                logger.info(`[${clientId}] Unloading inactive session (>${SESSION_INACTIVE_HOURS}h)`);
                try {
                    if (session.sock) session.sock.end(undefined);
                } catch (e) { /* ignore */ }
                activeSessions.delete(clientId);
            }
        });
    }, 3600000); // Check every hour
}

// --- API KEY MIDDLEWARE ---
function authMiddleware(req, res, next) {
    const key = req.headers['x-api-key'] || req.query.api_key;
    if (key !== API_KEY) {
        return res.status(403).json({ error: 'Invalid API key' });
    }
    next();
}

// Validate clientId param
function validateclientId(req, res, next) {
    const { clientId } = req.params;
    if (!clientId || !isValidclientId(clientId)) {
        return res.status(400).json({ error: 'Invalid client ID' });
    }
    next();
}

// --- EXPRESS APP ---
const app = express();

app.use(cors({
    origin: [DJANGO_ORIGIN, 'http://localhost:8000', 'http://127.0.0.1:8000'],
    methods: ['GET', 'POST'],
    credentials: true
}));

app.use(express.json({ limit: '1mb' }));

// Health check (no auth required — minimal info)
app.get('/health', (req, res) => {
    res.json({ status: 'ok' });
});

// --- ADMIN: LIST ALL SESSIONS ---
app.get('/api/sessions', authMiddleware, (req, res) => {
    const sessions = [];
    activeSessions.forEach((session, clientId) => {
        sessions.push({
            client_id: clientId,
            linked: session.isConnected,
            qr_available: !!session.currentQR,
            last_active: new Date(session.lastActive).toISOString(),
            messages_this_minute: session.messagesSentThisMinute
        });
    });
    res.json({ sessions, total: sessions.length });
});

// --- QR CODE ENDPOINT ---
app.get('/api/:clientId/qr.png', authMiddleware, validateclientId, async (req, res) => {
    try {
        const session = await getOrCreateSession(req.params.clientId);

        if (session.isConnected) {
            return res.json({ linked: true, message: 'WhatsApp already linked' });
        }

        if (!session.currentQR) {
            return res.status(202).json({ linked: false, message: 'QR code not yet generated. Please wait...' });
        }

        const qrBuffer = await QRCode.toBuffer(session.currentQR, {
            type: 'png',
            width: 400,
            margin: 2,
            color: { dark: '#000000', light: '#ffffff' }
        });

        res.set('Content-Type', 'image/png');
        res.set('Cache-Control', 'no-cache, no-store, must-revalidate');
        res.send(qrBuffer);

    } catch (err) {
        logger.error(`[${req.params.clientId}] QR generation error: ${err.message}`);
        res.status(500).json({ error: 'Failed to generate QR code' });
    }
});

// --- STATUS ENDPOINT ---
app.get('/api/:clientId/status', authMiddleware, validateclientId, async (req, res) => {
    const clientId = req.params.clientId;
    const session = activeSessions.get(clientId);

    if (!session) {
        return res.json({
            linked: false,
            phone: null,
            qr_available: false,
            safe_time: isSafeTime(),
            messages_this_minute: 0,
            active_jobs: 0
        });
    }

    session.lastActive = Date.now();
    res.json({
        linked: session.isConnected,
        phone: session.isConnected && session.sock?.user ? session.sock.user.id.split(':')[0] : null,
        qr_available: !!session.currentQR,
        safe_time: isSafeTime(),
        messages_this_minute: session.messagesSentThisMinute,
        active_jobs: [...activeJobs.values()].filter(j => j.clientId === clientId).length
    });
});

// --- UNLINK ENDPOINT ---
app.post('/api/:clientId/unlink', authMiddleware, validateclientId, async (req, res) => {
    const clientId = req.params.clientId;
    const session = activeSessions.get(clientId);

    try {
        if (session?.sock) {
            try { await session.sock.logout(); } catch (e) { /* ignore */ }
        }

        // Delete auth directory
        const authDir = path.join(__dirname, 'auth_info', clientId);
        if (fs.existsSync(authDir)) {
            fs.rmSync(authDir, { recursive: true, force: true });
        }

        // Remove from active sessions
        activeSessions.delete(clientId);

        res.json({ success: true, message: 'WhatsApp unlinked. Scan new QR to re-link.' });

    } catch (err) {
        logger.error(`[${clientId}] Unlink error: ${err.message}`);
        // Force cleanup
        const authDir = path.join(__dirname, 'auth_info', clientId);
        if (fs.existsSync(authDir)) {
            fs.rmSync(authDir, { recursive: true, force: true });
        }
        activeSessions.delete(clientId);
        res.json({ success: true, message: 'WhatsApp session cleared.' });
    }
});

// --- SEND LEDGER (single customer with image) ---
app.post('/api/:clientId/send-ledger', authMiddleware, validateclientId, async (req, res) => {
    try {
        const session = await getOrCreateSession(req.params.clientId);
        const { customer_data } = req.body;

        if (!customer_data) {
            return res.status(400).json({ error: 'customer_data is required' });
        }

        if (!session.isConnected) {
            return res.status(503).json({ error: 'WhatsApp not connected' });
        }

        const waNumber = customer_data.whatsappnumber;
        if (!isValidWhatsAppNumber(waNumber)) {
            return res.json({ success: false, skipped: true, message: 'Invalid/missing WhatsApp number' });
        }

        await waitForRateLimit(session);

        const phone = formatPhone(waNumber);
        const hasTransactions = customer_data.transactions && customer_data.transactions.length > 0;

        await simulateTyping(session.sock, phone);

        if (hasTransactions) {
            const imageBuffer = await generateTradeTable(customer_data);
            await session.sock.sendMessage(phone, { image: imageBuffer, caption: `BALANCE='${customer_data.balance}'` });
        } else {
            await session.sock.sendMessage(phone, {
                text: `BALANCE='${customer_data.balance}'`
            });
        }

        session.messagesSentThisMinute++;
        session.messagesSentToday++;
        session.lastActive = Date.now();
        logger.info(`[${req.params.clientId}] Sent ledger to ${waNumber}`);

        res.json({ success: true, type: hasTransactions ? 'image' : 'text' });

    } catch (err) {
        logger.error(`[${req.params.clientId}] Send ledger error: ${err.message}`);
        res.status(500).json({ error: NODE_ENV === 'production' ? 'Internal server error' : err.message });
    }
});

// --- SEND BALANCE ACCOUNTS (batch with Poisson delays) ---
app.post('/api/:clientId/send-balance-accounts', authMiddleware, validateclientId, async (req, res) => {
    try {
        const clientId = req.params.clientId;
        const session = await getOrCreateSession(clientId);
        const { accounts } = req.body;

        if (!accounts || !Array.isArray(accounts) || accounts.length === 0) {
            return res.status(400).json({ error: 'accounts array is required' });
        }
        if (accounts.length > 100) {
            return res.status(400).json({ error: `Maximum 100 accounts per batch. You sent ${accounts.length}.` });
        }

        if (!session.isConnected) {
            return res.status(503).json({ error: 'WhatsApp not connected' });
        }

        const jobId = crypto.randomUUID();
        const job = {
            id: jobId,
            clientId: clientId,
            total: accounts.length,
            sent: 0,
            failed: 0,
            skipped: 0,
            errors: [],
            status: 'running',
            startedAt: new Date().toISOString(),
            listeners: []
        };

        activeJobs.set(jobId, job);

        processBatchSend(jobId, clientId, accounts).catch(err => {
            logger.error(`[${clientId}] Batch job ${jobId} crashed: ${err.message}`);
            job.status = 'error';
        });

        res.json({
            success: true,
            job_id: jobId,
            total: accounts.length,
            message: `Sending to ${accounts.length} accounts.`
        });

    } catch (err) {
        logger.error(`[${req.params.clientId}] Batch send error: ${err.message}`);
        res.status(500).json({ error: NODE_ENV === 'production' ? 'Internal server error' : err.message });
    }
});

async function processBatchSend(jobId, clientId, accounts) {
    const job = activeJobs.get(jobId);
    const session = activeSessions.get(clientId);
    if (!job || !session) return;

    // Presence lifecycle: go "online" for the batch window
    try { await session.sock.sendPresenceUpdate('available'); } catch(e) {}

    for (let i = 0; i < accounts.length; i++) {
        const account = accounts[i];
        const accountMode = account.send_mode === 'image' ? 'image' : 'text';

        if (job.status === 'cancelled') break;

        if (!isSafeTime()) {
            notifySSE(job, {
                type: 'warning',
                message: `Outside safe hours (${START_HOUR_DUBAI}:00-${END_HOUR_DUBAI}:00 Dubai). Pausing...`,
                index: i
            });
            while (!isSafeTime() && job.status !== 'cancelled') {
                await new Promise(r => setTimeout(r, 300000));
            }
        }

        const waNumber = account.whatsappnumber;
        const accountName = account.name || 'Unknown';

        if (!isValidWhatsAppNumber(waNumber)) {
            job.skipped++;
            const msg = `Skipped "${accountName}": Invalid/missing WhatsApp number`;
            job.errors.push(msg);
            logger.info(`[${clientId}] ${msg}`);
            notifySSE(job, {
                type: 'skipped', message: msg, index: i,
                sent: job.sent, failed: job.failed, skipped: job.skipped, total: job.total
            });
            continue;
        }

        try {
            await waitForRateLimit(session);

            const phone = formatPhone(waNumber);
            const hasTransactions = account.transactions && account.transactions.length > 0;

            if (accountMode === 'image' && hasTransactions) {
                const imageBuffer = await generateTradeTable(account);
                await simulateTyping(session.sock, phone);
                await session.sock.sendMessage(phone, { image: imageBuffer, caption: `${getRotatedBalanceText()}'${account.balance}'` });
                logger.info(`[${clientId}] [Job ${jobId}] Sent IMAGE to ${accountName} (${i + 1}/${accounts.length})`);
            } else {
                await simulateTyping(session.sock, phone);
                await session.sock.sendMessage(phone, {
                    text: `${getRotatedBalanceText()}'${account.balance}'`
                });
                logger.info(`[${clientId}] [Job ${jobId}] Sent TEXT to ${accountName} (${i + 1}/${accounts.length})`);
            }

            // Send explicit paused event so WhatsApp knows composing stopped
            try { await session.sock.sendPresenceUpdate('paused', phone); } catch(e) {}

            session.messagesSentThisMinute++;
            session.messagesSentToday++;
            session.lastActive = Date.now();
            job.sent++;

            notifySSE(job, {
                type: 'sent', message: `Sent to "${accountName}"`, index: i,
                sent: job.sent, failed: job.failed, skipped: job.skipped, total: job.total
            });

        } catch (err) {
            job.failed++;
            const msg = `Failed to send to "${accountName}": ${err.message}`;
            job.errors.push(msg);
            logger.error(`[${clientId}] ${msg}`);
            notifySSE(job, {
                type: 'error', message: msg, index: i,
                sent: job.sent, failed: job.failed, skipped: job.skipped, total: job.total
            });
        }

        // Poisson delay between sends
        if (i < accounts.length - 1 && job.status !== 'cancelled') {
            const delay = getPoissonDelay();
            const delaySecs = (delay / 1000).toFixed(1);
            notifySSE(job, { type: 'delay', message: `Waiting ${delaySecs}s before next send...`, delay_ms: delay });
            await new Promise(r => setTimeout(r, delay));
        }
    }

    // Presence lifecycle: go "offline" after batch
    try { await session.sock.sendPresenceUpdate('unavailable'); } catch(e) {}

    job.status = 'completed';
    job.completedAt = new Date().toISOString();
    notifySSE(job, {
        type: 'complete',
        message: `Batch complete. Sent: ${job.sent}, Failed: ${job.failed}, Skipped: ${job.skipped}`,
        sent: job.sent, failed: job.failed, skipped: job.skipped, total: job.total
    });

    setTimeout(() => activeJobs.delete(jobId), 600000);
}

function notifySSE(job, data) {
    job.listeners.forEach(res => {
        try { res.write(`data: ${JSON.stringify(data)}\n\n`); } catch (e) { /* closed */ }
    });
}

// --- SSE PROGRESS ENDPOINT ---
app.get('/api/:clientId/send-progress/:jobId', authMiddleware, validateclientId, (req, res) => {
    const job = activeJobs.get(req.params.jobId);
    if (!job || job.clientId !== req.params.clientId) {
        return res.status(404).json({ error: 'Job not found' });
    }

    res.set({ 'Content-Type': 'text/event-stream', 'Cache-Control': 'no-cache', 'Connection': 'keep-alive' });

    res.write(`data: ${JSON.stringify({
        type: 'status', sent: job.sent, failed: job.failed,
        skipped: job.skipped, total: job.total, status: job.status
    })}\n\n`);

    job.listeners.push(res);
    req.on('close', () => {
        const idx = job.listeners.indexOf(res);
        if (idx > -1) job.listeners.splice(idx, 1);
    });
});

// --- SEND ADDRESS ROW (single text message) ---
app.post('/api/:clientId/send-address-row', authMiddleware, validateclientId, async (req, res) => {
    try {
        const session = await getOrCreateSession(req.params.clientId);
        const { whatsapp_number, row_data } = req.body;

        if (!whatsapp_number || !row_data) {
            return res.status(400).json({ error: 'whatsapp_number and row_data are required' });
        }

        if (!session.isConnected) {
            return res.status(503).json({ error: 'WhatsApp not connected' });
        }

        if (!isValidWhatsAppNumber(whatsapp_number)) {
            return res.json({ success: false, skipped: true, message: 'Invalid WhatsApp number — skipped' });
        }

        await waitForRateLimit(session);

        const phone = formatPhone(whatsapp_number);
        const { sno, description, amount, qty, date } = row_data;

        const text = [
            `📦 *Transaction Detail*`, ``,
            `S.No: ${sno || '-'}`,
            date ? `Date: ${date}` : null,
            `Description: ${description || '-'}`,
            qty ? `Qty: ${qty}` : null,
            amount ? `Amount: ${amount}` : null
        ].filter(Boolean).join('\n');

        await simulateTyping(session.sock, phone);
        await session.sock.sendMessage(phone, { text });
        session.messagesSentThisMinute++;
        session.messagesSentToday++;
        session.lastActive = Date.now();

        logger.info(`[${req.params.clientId}] Sent address row to ${whatsapp_number}`);
        res.json({ success: true });

    } catch (err) {
        logger.error(`[${req.params.clientId}] Send address row error: ${err.message}`);
        res.status(500).json({ error: NODE_ENV === 'production' ? 'Internal server error' : err.message });
    }
});

// --- SEND BATCH ADDRESS ROWS (Smart Context Delay for same-user) ---
app.post('/api/:clientId/send-address-rows', authMiddleware, validateclientId, async (req, res) => {
    try {
        const clientId = req.params.clientId;
        const session = await getOrCreateSession(clientId);
        const { whatsapp_number, rows, supplier_name } = req.body;

        if (!whatsapp_number || !rows || !Array.isArray(rows)) {
            return res.status(400).json({ error: 'whatsapp_number and rows array are required' });
        }
        if (rows.length > 200) {
            return res.status(400).json({ error: `Maximum 200 rows per batch. You sent ${rows.length}.` });
        }

        if (!session.isConnected) {
            return res.status(503).json({ error: 'WhatsApp not connected' });
        }

        if (!isValidWhatsAppNumber(whatsapp_number)) {
            return res.json({ success: false, skipped: true, message: 'Invalid WhatsApp number — skipped' });
        }

        const jobId = crypto.randomUUID();
        const job = {
            id: jobId,
            clientId: clientId,
            total: rows.length,
            sent: 0, failed: 0, skipped: 0,
            errors: [],
            status: 'running',
            startedAt: new Date().toISOString(),
            listeners: []
        };
        activeJobs.set(jobId, job);

        // Start async processing with Smart Context Delay
        (async () => {
            const phone = formatPhone(whatsapp_number);

            // Presence lifecycle: go online for the conversation
            try { await session.sock.sendPresenceUpdate('available'); } catch(e) {}

            for (let i = 0; i < rows.length; i++) {
                if (job.status === 'cancelled') break;

                const row = rows[i];
                try {
                    await waitForRateLimit(session);

                    // Simulate typing before sending each row
                    await simulateTyping(session.sock, phone);

                    const text = `${row.description || '-'}=${row.qty || '0'}`;

                    await session.sock.sendMessage(phone, { text });
                    // Send explicit paused event so WhatsApp knows composing stopped
                    try { await session.sock.sendPresenceUpdate('paused', phone); } catch(e) {}
                    
                    session.messagesSentThisMinute++;
                    session.messagesSentToday++;
                    session.lastActive = Date.now();
                    job.sent++;

                    notifySSE(job, {
                        type: 'sent', message: `Sent row ${i + 1}/${rows.length}`,
                        index: i, sent: job.sent, total: job.total
                    });

                } catch (err) {
                    job.failed++;
                    logger.error(`[${clientId}] Row ${i + 1} send failed: ${err.message}`);
                    notifySSE(job, {
                        type: 'error', message: `Row ${i + 1} failed: ${err.message}`,
                        index: i, sent: job.sent, failed: job.failed, total: job.total
                    });
                }

                // Smart Context Delay: shorter gaps for same-user sequential messages
                // Mimics a human rapidly typing related data points in a conversation
                if (i < rows.length - 1 && job.status !== 'cancelled') {
                    const delay = 1500 + Math.random() * 2500; // 1.5-4s (natural chat pace)
                    await new Promise(r => setTimeout(r, delay));
                }
            }

            // Presence lifecycle: go offline after conversation
            try { await session.sock.sendPresenceUpdate('unavailable'); } catch(e) {}

            job.status = 'completed';
            notifySSE(job, {
                type: 'complete', message: `Complete. Sent: ${job.sent}/${job.total}`,
                sent: job.sent, failed: job.failed, total: job.total
            });
            setTimeout(() => activeJobs.delete(jobId), 600000);
        })().catch(err => {
            job.status = 'error';
            logger.error(`[${clientId}] Batch rows job error: ${err.message}`);
        });

        res.json({ success: true, job_id: jobId, total: rows.length });

    } catch (err) {
        logger.error(`[${req.params.clientId}] Send address rows error: ${err.message}`);
        res.status(500).json({ error: NODE_ENV === 'production' ? 'Internal server error' : err.message });
    }
});

// --- JOB STATUS (polling) ---
app.get('/api/:clientId/job-status/:jobId', authMiddleware, validateclientId, (req, res) => {
    const job = activeJobs.get(req.params.jobId);
    if (!job || job.clientId !== req.params.clientId) {
        return res.status(404).json({ error: 'Job not found' });
    }

    res.json({
        id: job.id,
        status: job.status,
        total: job.total,
        sent: job.sent,
        failed: job.failed,
        skipped: job.skipped,
        errors: job.errors,
        started_at: job.startedAt,
        completed_at: job.completedAt || null
    });
});

// --- CANCEL JOB ---
app.post('/api/:clientId/cancel-job/:jobId', authMiddleware, validateclientId, (req, res) => {
    const job = activeJobs.get(req.params.jobId);
    if (!job || job.clientId !== req.params.clientId) {
        return res.status(404).json({ error: 'Job not found' });
    }

    job.status = 'cancelled';
    notifySSE(job, { type: 'cancelled', message: 'Job cancelled by user' });
    res.json({ success: true, message: 'Job cancelled' });
});

// --- CANCEL ALL JOBS (global stop button) ---
app.post('/api/:clientId/cancel-all-jobs', authMiddleware, validateclientId, (req, res) => {
    const clientId = req.params.clientId;
    let cancelled = 0;
    for (const [jobId, job] of activeJobs) {
        if (job.clientId === clientId && job.status === 'running') {
            job.status = 'cancelled';
            notifySSE(job, { type: 'cancelled', message: 'Job cancelled by user (stop all)' });
            cancelled++;
        }
    }
    logger.info(`[${clientId}] Cancelled ${cancelled} running job(s)`);
    res.json({ success: true, cancelled });
});

// --- STARTUP ---
async function main() {
    startRateLimitReset();
    startDailyReset();
    startSessionCleanup();

    app.listen(PORT, () => {
        logger.info(`🚀 WhatsApp API Server (Multi-Client) running on port ${PORT}`);
        logger.info(`   Environment: ${NODE_ENV}`);
        logger.info(`   CORS origin: ${DJANGO_ORIGIN}`);
        logger.info(`   Session timeout: ${SESSION_INACTIVE_HOURS}h`);
        if (DEV_WHATSAPP_NUMBER) {
            logger.info(`   ⚠️  DEV MODE: All messages routed to ${DEV_WHATSAPP_NUMBER}`);
        }
    });
}

// --- GRACEFUL SHUTDOWN ---
process.on('SIGINT', async () => {
    logger.info('Shutting down...');
    for (const [clientId, session] of activeSessions) {
        try {
            if (session.sock) await session.sock.end(undefined);
            logger.info(`[${clientId}] Session closed`);
        } catch (e) { /* ignore */ }
    }
    process.exit(0);
});

process.on('SIGTERM', async () => {
    for (const [, session] of activeSessions) {
        try { if (session.sock) await session.sock.end(undefined); } catch (e) { /* ignore */ }
    }
    process.exit(0);
});

main().catch(err => {
    logger.error(`Fatal startup error: ${err.message}`);
    process.exit(1);
});
