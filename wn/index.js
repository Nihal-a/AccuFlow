import { makeWASocket, useMultiFileAuthState, DisconnectReason } from '@whiskeysockets/baileys';
import { Queue, Worker } from 'bullmq';
import fs from 'fs';
import pino from 'pino';
import { generateTradeTable } from './image.js';

// --- CONFIG ---
const START_HOUR_DUBAI = 8;
const END_HOUR_DUBAI = 22; // 10 PM
const MAX_RETRIES = 3;
const POISSON_LAMBDA_MINUTES = 3;

// --- LOGGING ---
const logger = pino({ level: 'info' });

// --- REDIS CONNECTION ---
const redisOptions = { host: '127.0.0.1', port: 6379 };

// --- QUEUE SETUP ---
const tradeQueue = new Queue('trade-alerts', { connection: redisOptions });

// --- BAILEYS CONNECTION ---
let sock;
async function connectToWhatsApp() {
    const { state, saveCreds } = await useMultiFileAuthState('auth_info');

    sock = makeWASocket({
        logger: pino({ level: 'fatal' }), // Silent for production
        printQRInTerminal: false,
        auth: state,
        generateHighQualityLinkPreview: false, // Anti-ban
        syncFullHistory: false, // Startup speed
        defaultQueryTimeoutMs: 60000
    });

    sock.ev.on('creds.update', saveCreds);
    sock.ev.on('connection.update', async (update) => {
        const { connection, lastDisconnect } = update;
        if (connection === 'close') {
            const shouldReconnect = (lastDisconnect.error)?.output?.statusCode !== DisconnectReason.loggedOut;
            logger.warn(`Connection closed. Reconnecting: ${shouldReconnect}`);
            if (shouldReconnect) connectToWhatsApp();
        } else if (connection === 'open') {
            logger.info('✅ WhatsApp Connected');
        }
    });
}

// --- UTILS ---
function isSafeTime() {
    // Get current time in Dubai
    const now = new Date();
    const dubaiTimeState = now.toLocaleString("en-US", { timeZone: "Asia/Dubai" });
    const dubaiDate = new Date(dubaiTimeState);
    const hour = dubaiDate.getHours();

    // Allow if between 8AM and 10PM (22:00)
    return hour >= START_HOUR_DUBAI && hour < END_HOUR_DUBAI;
}

function getPoissonDelay() {
    // Random delay based on Poisson distribution approx (Exponential distribution for inter-arrival times)
    // Mean = 3 minutes (180000ms)
    // Exp(lambda) -> time = -ln(U) / lambda
    // We want mean = 1/lambda = 3 mins.
    // So time = -ln(Math.random()) * 3 * 60 * 1000
    return -Math.log(Math.random()) * POISSON_LAMBDA_MINUTES * 60 * 1000;
}

const CAPTIONS = [
    "📈 Your latest trade summary is ready. Please review above.",
    "📊 Account update: Here is your recent activity snapshot.",
    "💼 Daily trade report generated. Balance details attached."
];

// --- WORKER ---
const worker = new Worker('trade-alerts', async job => {
    const { customer } = job.data;
    const phone = customer.whatsappnumber.replace(/[^0-9]/g, '') + "@s.whatsapp.net";

    // 1. Timezone Check
    if (!isSafeTime()) {
        const delay = 60 * 60 * 1000; // Retry in 1 hour
        logger.info(`Sleeping (Dubai Night): ${customer.whatsappnumber}`);
        await tradeQueue.add('trade-alert', { customer }, { delay });
        return;
    }

    // 2. Opt-in Check
    if (!customer.optin_verified) {
        logger.info(`Skipped (No Opt-in): ${customer.whatsappnumber}`);
        return;
    }

    try {
        if (!sock) await connectToWhatsApp();

        // Wait for connection if needed
        let retries = 0;
        while (!sock?.user && retries < 10) {
            await new Promise(r => setTimeout(r, 1000));
            retries++;
        }

        const hasTransactions = customer.transactions && customer.transactions.length > 0;

        if (hasTransactions) {
            // 3. Generate Image
            const imageBuffer = await generateTradeTable(customer);
            const template = CAPTIONS[Math.floor(Math.random() * CAPTIONS.length)];

            // 4. Send Message (Image + Caption)
            await sock.sendMessage(phone, {
                image: imageBuffer,
                caption: template
            });
        } else {
            // 4. Send Message (Text Only)
            await sock.sendMessage(phone, {
                text: `📋 Account Balance Update\n\nYour current balance is: *${customer.balance}*\n\n(No recent transactions to display)`
            });
        }

        logger.info(`Sent to +${customer.whatsappnumber}: ${hasTransactions ? 'IMAGE' : 'TEXT'}`);

    } catch (err) {
        logger.error(`Failed to send to ${customer.whatsappnumber}: ${err.message}`);
        throw err; // Trigger BullMQ retry
    }

}, {
    connection: redisOptions,
    limiter: {
        max: 1,
        duration: 5000 // Max 1 msg per 5 seconds globally to be safe
    }
});

// --- MAIN SCHEDULER ---
async function main() {
    await connectToWhatsApp();

    try {
        const raw = fs.readFileSync('customers.json');
        const customers = JSON.parse(raw);

        logger.info(`🔥 Queuing ${customers.length} customers with Poisson delays...`);

        let accumulatingDelay = 0;
        for (const customer of customers) {
            // Add individual poisson delay to space them out
            accumulatingDelay += getPoissonDelay();

            await tradeQueue.add('trade-alert',
                { customer },
                {
                    delay: accumulatingDelay,
                    attempts: MAX_RETRIES,
                    backoff: {
                        type: 'exponential',
                        delay: 60000
                    }
                }
            );
        }

        console.log(`✅ All jobs queued. Estimated finish: ${(accumulatingDelay / 60000).toFixed(1)} mins`);

    } catch (e) {
        console.error("Error reading customers.json:", e);
    }
}

// Handle shutdown
process.on('SIGINT', async () => {
    await sock.end(undefined);
    await worker.close();
    process.exit(0);
});

// Start if executed directly
main();
