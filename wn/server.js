/**
 * AccuFlow WhatsApp Express Server
 * 
 * HTTP API wrapper around existing Baileys WhatsApp automation.
 * Replaces qr.js for auth — handles QR scanning + message sending in one process.
 * 
 * Endpoints:
 *   GET  /qr.png                    - Returns QR code as PNG image
 *   GET  /status                    - Returns { linked: true/false }
 *   POST /unlink                    - Unlinks WhatsApp session
 *   POST /api/send-ledger           - Sends ledger image to a customer
 *   POST /api/send-balance-accounts - Sends balance to multiple accounts (sequential + Poisson delays)
 *   POST /api/send-address-row      - Sends a single address row as text
 *   GET  /api/send-progress/:jobId  - SSE endpoint for batch send progress
 * 
 * No Redis/BullMQ dependency — in-memory sequential sending with Poisson delays.
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
const PORT = process.env.NODE_PORT || process.env.PORT || 3001;
const NODE_ENV = process.env.NODE_ENV || 'development';
const API_KEY = process.env.WA_API_KEY || 'accuflow-wa-dev-key-2024';
const DJANGO_ORIGIN = process.env.DJANGO_ORIGIN || 'http://localhost:8000';
const DEV_WHATSAPP_NUMBER = process.env.DEV_WHATSAPP_NUMBER || '';

// Rate limiting & anti-ban — all configurable via env vars
const POISSON_LAMBDA_MINUTES = parseFloat(process.env.POISSON_DELAY || (NODE_ENV === 'development' ? '0.5' : '3'));
const GLOBAL_RATE_LIMIT = parseInt(process.env.RATE_LIMIT || (NODE_ENV === 'development' ? '20' : '10'));
const START_HOUR_DUBAI = parseInt(process.env.SAFE_HOUR_START || (NODE_ENV === 'development' ? '0' : '8'));
const END_HOUR_DUBAI = parseInt(process.env.SAFE_HOUR_END || (NODE_ENV === 'development' ? '24' : '22'));

// --- LOGGING ---
const logger = pino({ level: NODE_ENV === 'production' ? 'info' : 'debug' });

// --- GLOBAL STATE ---
let sock = null;
let currentQR = null;
let isConnected = false;
let isConnecting = false;
let messagesSentThisMinute = 0;
let rateLimitResetInterval = null;

// In-memory job tracking for batch sends
const activeJobs = new Map();

// --- RATE LIMITER ---
function startRateLimitReset() {
    if (rateLimitResetInterval) clearInterval(rateLimitResetInterval);
    rateLimitResetInterval = setInterval(() => {
        messagesSentThisMinute = 0;
    }, 60000);
}

async function waitForRateLimit() {
    while (messagesSentThisMinute >= GLOBAL_RATE_LIMIT) {
        await new Promise(r => setTimeout(r, 2000));
    }
}

// --- UTILS ---
function isSafeTime() {
    // If window is 0-24, it's always safe
    if (START_HOUR_DUBAI === 0 && END_HOUR_DUBAI === 24) return true;
    const now = new Date();
    const dubaiTimeStr = now.toLocaleString("en-US", { timeZone: "Asia/Dubai" });
    const dubaiDate = new Date(dubaiTimeStr);
    const hour = dubaiDate.getHours();
    return hour >= START_HOUR_DUBAI && hour < END_HOUR_DUBAI;
}

function getPoissonDelay() {
    return -Math.log(Math.random()) * POISSON_LAMBDA_MINUTES * 60 * 1000;
}

function formatPhone(number) {
    // If in dev mode and DEV_WHATSAPP_NUMBER is set, override all numbers
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

const CAPTIONS = [
    "📈 Your latest trade summary is ready. Please review above.",
    "📊 Account update: Here is your recent activity snapshot.",
    "💼 Daily trade report generated. Balance details attached."
];

// --- BAILEYS CONNECTION ---
async function connectToWhatsApp() {
    if (isConnecting) return;
    isConnecting = true;

    try {
        const { state, saveCreds } = await useMultiFileAuthState(path.join(__dirname, 'auth_info'));
        const { version } = await fetchLatestBaileysVersion();

        sock = makeWASocket({
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

        sock.ev.on('creds.update', saveCreds);

        sock.ev.on('connection.update', (update) => {
            const { connection, lastDisconnect, qr } = update;

            if (qr) {
                currentQR = qr;
                isConnected = false;
                logger.info('New QR code generated');
            }

            if (connection === 'close') {
                isConnected = false;
                isConnecting = false;
                const statusCode = lastDisconnect?.error?.output?.statusCode;
                logger.warn(`Connection closed (Status: ${statusCode})`);

                if (statusCode === DisconnectReason.loggedOut || statusCode === 401) {
                    // Session expired — clear auth and wait for new QR scan
                    currentQR = null;
                    logger.info('Logged out. Delete auth_info to re-authenticate.');
                    // Auto-reconnect to generate new QR
                    setTimeout(() => connectToWhatsApp(), 3000);
                } else {
                    // Network error or other — auto-reconnect
                    logger.info('Reconnecting in 3s...');
                    setTimeout(() => connectToWhatsApp(), 3000);
                }
            } else if (connection === 'open') {
                isConnected = true;
                isConnecting = false;
                currentQR = null;
                logger.info('✅ WhatsApp Connected');
            }
        });

    } catch (err) {
        isConnecting = false;
        logger.error(`Connection error: ${err.message}`);
        setTimeout(() => connectToWhatsApp(), 5000);
    }
}

// --- API KEY MIDDLEWARE ---
function authMiddleware(req, res, next) {
    const key = req.headers['x-api-key'] || req.query.api_key;
    if (key !== API_KEY) {
        return res.status(403).json({ error: 'Invalid API key' });
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

app.use(express.json({ limit: '10mb' }));

// Health check (no auth required)
app.get('/health', (req, res) => {
    res.json({ status: 'ok', uptime: process.uptime() });
});

// --- QR CODE ENDPOINT ---
app.get('/qr.png', authMiddleware, async (req, res) => {
    try {
        if (isConnected) {
            // Already linked — return a simple "linked" image or JSON
            return res.json({ linked: true, message: 'WhatsApp already linked' });
        }

        if (!currentQR) {
            return res.status(202).json({ linked: false, message: 'QR code not yet generated. Please wait...' });
        }

        // Generate QR as PNG buffer
        const qrBuffer = await QRCode.toBuffer(currentQR, {
            type: 'png',
            width: 400,
            margin: 2,
            color: {
                dark: '#000000',
                light: '#ffffff'
            }
        });

        res.set('Content-Type', 'image/png');
        res.set('Cache-Control', 'no-cache, no-store, must-revalidate');
        res.send(qrBuffer);

    } catch (err) {
        logger.error(`QR generation error: ${err.message}`);
        res.status(500).json({ error: 'Failed to generate QR code' });
    }
});

// --- STATUS ENDPOINT ---
app.get('/status', authMiddleware, (req, res) => {
    res.json({
        linked: isConnected,
        phone: isConnected && sock?.user ? sock.user.id.split(':')[0] : null,
        qr_available: !!currentQR,
        safe_time: isSafeTime(),
        messages_this_minute: messagesSentThisMinute,
        active_jobs: activeJobs.size
    });
});

// --- UNLINK ENDPOINT ---
app.post('/unlink', authMiddleware, async (req, res) => {
    try {
        if (sock) {
            await sock.logout();
        }

        // Delete auth_info directory
        const authDir = path.join(__dirname, 'auth_info');
        if (fs.existsSync(authDir)) {
            fs.rmSync(authDir, { recursive: true, force: true });
        }

        isConnected = false;
        currentQR = null;

        // Reconnect to generate new QR
        setTimeout(() => connectToWhatsApp(), 2000);

        res.json({ success: true, message: 'WhatsApp unlinked. Scan new QR to re-link.' });

    } catch (err) {
        logger.error(`Unlink error: ${err.message}`);
        // Even on error, try to clean up
        const authDir = path.join(__dirname, 'auth_info');
        if (fs.existsSync(authDir)) {
            fs.rmSync(authDir, { recursive: true, force: true });
        }
        isConnected = false;
        currentQR = null;
        setTimeout(() => connectToWhatsApp(), 2000);
        res.json({ success: true, message: 'WhatsApp session cleared.' });
    }
});

// --- SEND LEDGER (single customer with image) ---
app.post('/api/send-ledger', authMiddleware, async (req, res) => {
    try {
        const { customer_data } = req.body;

        if (!customer_data) {
            return res.status(400).json({ error: 'customer_data is required' });
        }

        if (!isConnected) {
            return res.status(503).json({ error: 'WhatsApp not connected' });
        }

        const waNumber = customer_data.whatsappnumber;
        if (!isValidWhatsAppNumber(waNumber)) {
            return res.json({
                success: false,
                skipped: true,
                message: `Invalid/missing WhatsApp number for this account`
            });
        }

        await waitForRateLimit();

        const phone = formatPhone(waNumber);
        const hasTransactions = customer_data.transactions && customer_data.transactions.length > 0;

        if (hasTransactions) {
            const imageBuffer = await generateTradeTable(customer_data);
            const caption = CAPTIONS[Math.floor(Math.random() * CAPTIONS.length)];
            await sock.sendMessage(phone, { image: imageBuffer, caption });
        } else {
            await sock.sendMessage(phone, {
                text: `📋 Account Balance Update\n\nYour current balance is: *${customer_data.balance}*\n\n(No recent transactions to display)`
            });
        }

        messagesSentThisMinute++;
        logger.info(`Sent ledger to ${waNumber}: ${hasTransactions ? 'IMAGE' : 'TEXT'}`);

        res.json({ success: true, type: hasTransactions ? 'image' : 'text' });

    } catch (err) {
        logger.error(`Send ledger error: ${err.message}`);
        res.status(500).json({ error: err.message });
    }
});

// --- SEND BALANCE ACCOUNTS (batch with Poisson delays) ---
app.post('/api/send-balance-accounts', authMiddleware, async (req, res) => {
    try {
        const { accounts } = req.body;

        if (!accounts || !Array.isArray(accounts) || accounts.length === 0) {
            return res.status(400).json({ error: 'accounts array is required' });
        }

        if (!isConnected) {
            return res.status(503).json({ error: 'WhatsApp not connected' });
        }

        // Create job
        const jobId = crypto.randomUUID();
        const job = {
            id: jobId,
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

        // Start async sending (don't await — return immediately)
        processBatchSend(jobId, accounts).catch(err => {
            logger.error(`Batch job ${jobId} crashed: ${err.message}`);
            job.status = 'error';
        });

        res.json({
            success: true,
            job_id: jobId,
            total: accounts.length,
            message: `Sending to ${accounts.length} accounts.`
        });

    } catch (err) {
        logger.error(`Batch send error: ${err.message}`);
        res.status(500).json({ error: err.message });
    }
});

async function processBatchSend(jobId, accounts) {
    const job = activeJobs.get(jobId);
    if (!job) return;

    for (let i = 0; i < accounts.length; i++) {
        const account = accounts[i];
        // Per-account send mode (default: 'text')
        const accountMode = account.send_mode === 'image' ? 'image' : 'text';

        // Check if job was cancelled
        if (job.status === 'cancelled') break;

        // Check safe time
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

        // Validate number
        if (!isValidWhatsAppNumber(waNumber)) {
            job.skipped++;
            const msg = `Skipped "${accountName}": Invalid/missing WhatsApp number`;
            job.errors.push(msg);
            logger.info(msg);
            notifySSE(job, {
                type: 'skipped',
                message: msg,
                index: i,
                sent: job.sent,
                failed: job.failed,
                skipped: job.skipped,
                total: job.total
            });
            continue;
        }

        try {
            await waitForRateLimit();

            const phone = formatPhone(waNumber);
            const hasTransactions = account.transactions && account.transactions.length > 0;

            // Per-account: 'image' mode uses image when transactions exist, otherwise text
            if (accountMode === 'image' && hasTransactions) {
                const imageBuffer = await generateTradeTable(account);
                const caption = CAPTIONS[Math.floor(Math.random() * CAPTIONS.length)];
                await sock.sendMessage(phone, { image: imageBuffer, caption });
                logger.info(`[Job ${jobId}] Sent IMAGE to ${accountName} (${i + 1}/${accounts.length})`);
            } else {
                const balanceStr = account.balance || '0.0000';
                const balanceNum = parseFloat(balanceStr);
                const emoji = balanceNum > 0 ? '📈' : balanceNum < 0 ? '📉' : '📋';
                await sock.sendMessage(phone, {
                    text: `${emoji} *Account Balance Update*\n\nName: *${accountName}*\nBalance: *${balanceStr}*\n\n_Sent via AccuFlow_`
                });
                logger.info(`[Job ${jobId}] Sent TEXT to ${accountName} (${i + 1}/${accounts.length})`);
            }

            messagesSentThisMinute++;
            job.sent++;
            logger.info(`[Job ${jobId}] Sent to ${accountName} (${i + 1}/${accounts.length})`);

            notifySSE(job, {
                type: 'sent',
                message: `Sent to "${accountName}"`,
                index: i,
                sent: job.sent,
                failed: job.failed,
                skipped: job.skipped,
                total: job.total
            });

        } catch (err) {
            job.failed++;
            const msg = `Failed to send to "${accountName}": ${err.message}`;
            job.errors.push(msg);
            logger.error(msg);

            notifySSE(job, {
                type: 'error',
                message: msg,
                index: i,
                sent: job.sent,
                failed: job.failed,
                skipped: job.skipped,
                total: job.total
            });
        }

        // Poisson delay between sends (not after last one)
        if (i < accounts.length - 1 && job.status !== 'cancelled') {
            const delay = getPoissonDelay();
            const delaySecs = (delay / 1000).toFixed(1);
            notifySSE(job, {
                type: 'delay',
                message: `Waiting ${delaySecs}s before next send...`,
                delay_ms: delay
            });
            await new Promise(r => setTimeout(r, delay));
        }
    }

    job.status = 'completed';
    job.completedAt = new Date().toISOString();
    notifySSE(job, {
        type: 'complete',
        message: `Batch complete. Sent: ${job.sent}, Failed: ${job.failed}, Skipped: ${job.skipped}`,
        sent: job.sent,
        failed: job.failed,
        skipped: job.skipped,
        total: job.total
    });

    // Cleanup job after 10 minutes
    setTimeout(() => activeJobs.delete(jobId), 600000);
}

function notifySSE(job, data) {
    job.listeners.forEach(res => {
        try {
            res.write(`data: ${JSON.stringify(data)}\n\n`);
        } catch (e) { /* connection closed */ }
    });
}

// --- SSE PROGRESS ENDPOINT ---
app.get('/api/send-progress/:jobId', authMiddleware, (req, res) => {
    const job = activeJobs.get(req.params.jobId);
    if (!job) {
        return res.status(404).json({ error: 'Job not found' });
    }

    res.set({
        'Content-Type': 'text/event-stream',
        'Cache-Control': 'no-cache',
        'Connection': 'keep-alive'
    });

    // Send current status immediately
    res.write(`data: ${JSON.stringify({
        type: 'status',
        sent: job.sent,
        failed: job.failed,
        skipped: job.skipped,
        total: job.total,
        status: job.status
    })}\n\n`);

    // Register listener
    job.listeners.push(res);

    req.on('close', () => {
        const idx = job.listeners.indexOf(res);
        if (idx > -1) job.listeners.splice(idx, 1);
    });
});

// --- SEND ADDRESS ROW (single text message) ---
app.post('/api/send-address-row', authMiddleware, async (req, res) => {
    try {
        const { whatsapp_number, row_data } = req.body;

        if (!whatsapp_number || !row_data) {
            return res.status(400).json({ error: 'whatsapp_number and row_data are required' });
        }

        if (!isConnected) {
            return res.status(503).json({ error: 'WhatsApp not connected' });
        }

        if (!isValidWhatsAppNumber(whatsapp_number)) {
            return res.json({
                success: false,
                skipped: true,
                message: 'Invalid WhatsApp number — skipped'
            });
        }

        await waitForRateLimit();

        const phone = formatPhone(whatsapp_number);
        const { sno, description, amount, qty, date } = row_data;

        const text = [
            `📦 *Transaction Detail*`,
            ``,
            `S.No: ${sno || '-'}`,
            date ? `Date: ${date}` : null,
            `Description: ${description || '-'}`,
            qty ? `Qty: ${qty}` : null,
            amount ? `Amount: ${amount}` : null
        ].filter(Boolean).join('\n');

        await sock.sendMessage(phone, { text });
        messagesSentThisMinute++;

        logger.info(`Sent address row to ${whatsapp_number}`);
        res.json({ success: true });

    } catch (err) {
        logger.error(`Send address row error: ${err.message}`);
        res.status(500).json({ error: err.message });
    }
});

// --- SEND BATCH ADDRESS ROWS ---
app.post('/api/send-address-rows', authMiddleware, async (req, res) => {
    try {
        const { whatsapp_number, rows, supplier_name } = req.body;

        if (!whatsapp_number || !rows || !Array.isArray(rows)) {
            return res.status(400).json({ error: 'whatsapp_number and rows array are required' });
        }

        if (!isConnected) {
            return res.status(503).json({ error: 'WhatsApp not connected' });
        }

        if (!isValidWhatsAppNumber(whatsapp_number)) {
            return res.json({
                success: false,
                skipped: true,
                message: 'Invalid WhatsApp number — skipped'
            });
        }

        // Create job for tracking
        const jobId = crypto.randomUUID();
        const job = {
            id: jobId,
            total: rows.length,
            sent: 0,
            failed: 0,
            skipped: 0,
            errors: [],
            status: 'running',
            startedAt: new Date().toISOString(),
            listeners: []
        };
        activeJobs.set(jobId, job);

        // Start async processing
        (async () => {
            const phone = formatPhone(whatsapp_number);

            // Send header message
            try {
                await waitForRateLimit();
                const header = `📋 *Address View Report*${supplier_name ? `\nSupplier: *${supplier_name}*` : ''}\nTotal Items: ${rows.length}\n${'─'.repeat(20)}`;
                await sock.sendMessage(phone, { text: header });
                messagesSentThisMinute++;
            } catch (e) {
                logger.error(`Header send failed: ${e.message}`);
            }

            for (let i = 0; i < rows.length; i++) {
                if (job.status === 'cancelled') break;

                const row = rows[i];
                try {
                    await waitForRateLimit();

                    const text = [
                        `${row.sno || i + 1}. ${row.description || '-'}`,
                        row.qty ? `   Qty: ${row.qty}` : null,
                        row.date ? `   Date: ${row.date}` : null,
                    ].filter(Boolean).join('\n');

                    await sock.sendMessage(phone, { text });
                    messagesSentThisMinute++;
                    job.sent++;

                    notifySSE(job, {
                        type: 'sent',
                        message: `Sent row ${i + 1}/${rows.length}`,
                        index: i,
                        sent: job.sent,
                        total: job.total
                    });

                } catch (err) {
                    job.failed++;
                    logger.error(`Row ${i + 1} send failed: ${err.message}`);
                    notifySSE(job, {
                        type: 'error',
                        message: `Row ${i + 1} failed: ${err.message}`,
                        index: i,
                        sent: job.sent,
                        failed: job.failed,
                        total: job.total
                    });
                }

                // Delay between rows (shorter than balance sends)
                if (i < rows.length - 1) {
                    const delay = 2000 + Math.random() * 3000; // 2-5 seconds
                    await new Promise(r => setTimeout(r, delay));
                }
            }

            job.status = 'completed';
            notifySSE(job, {
                type: 'complete',
                message: `Complete. Sent: ${job.sent}/${job.total}`,
                sent: job.sent,
                failed: job.failed,
                total: job.total
            });
            setTimeout(() => activeJobs.delete(jobId), 600000);
        })().catch(err => {
            job.status = 'error';
            logger.error(`Batch rows job error: ${err.message}`);
        });

        res.json({ success: true, job_id: jobId, total: rows.length });

    } catch (err) {
        logger.error(`Send address rows error: ${err.message}`);
        res.status(500).json({ error: err.message });
    }
});

// --- JOB STATUS (polling alternative to SSE) ---
app.get('/api/job-status/:jobId', authMiddleware, (req, res) => {
    const job = activeJobs.get(req.params.jobId);
    if (!job) {
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
app.post('/api/cancel-job/:jobId', authMiddleware, (req, res) => {
    const job = activeJobs.get(req.params.jobId);
    if (!job) {
        return res.status(404).json({ error: 'Job not found' });
    }

    job.status = 'cancelled';
    notifySSE(job, { type: 'cancelled', message: 'Job cancelled by user' });
    res.json({ success: true, message: 'Job cancelled' });
});

// --- STARTUP ---
async function main() {
    startRateLimitReset();
    await connectToWhatsApp();

    app.listen(PORT, () => {
        logger.info(`🚀 WhatsApp API Server running on port ${PORT}`);
        logger.info(`   Environment: ${NODE_ENV}`);
        logger.info(`   CORS origin: ${DJANGO_ORIGIN}`);
        if (DEV_WHATSAPP_NUMBER) {
            logger.info(`   ⚠️  DEV MODE: All messages routed to ${DEV_WHATSAPP_NUMBER}`);
        }
    });
}

// --- GRACEFUL SHUTDOWN ---
process.on('SIGINT', async () => {
    logger.info('Shutting down...');
    if (rateLimitResetInterval) clearInterval(rateLimitResetInterval);
    if (sock) {
        try { await sock.end(undefined); } catch (e) { /* ignore */ }
    }
    process.exit(0);
});

process.on('SIGTERM', async () => {
    if (sock) {
        try { await sock.end(undefined); } catch (e) { /* ignore */ }
    }
    process.exit(0);
});

main().catch(err => {
    logger.error(`Fatal startup error: ${err.message}`);
    process.exit(1);
});
