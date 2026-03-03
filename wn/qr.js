import { makeWASocket, useMultiFileAuthState, Browsers, fetchLatestBaileysVersion } from '@whiskeysockets/baileys';
import pino from 'pino';
import qrcode from 'qrcode-terminal';

console.log("🚀 Starting WhatsApp Auth...");

async function connectToWhatsApp() {
    const { state, saveCreds } = await useMultiFileAuthState('auth_info');
    const { version, isLatest } = await fetchLatestBaileysVersion();

    console.log(`Using WA version: ${version.join('.')} (Latest: ${isLatest})`);

    const sock = makeWASocket({
        version,
        logger: pino({ level: 'error' }),
        printQRInTerminal: false,
        auth: state,
        // Using macOS Desktop as it's often the most stable/accepted
        browser: Browsers.macOS('Desktop'),
        connectTimeoutMs: 60000,
        defaultQueryTimeoutMs: 60000,
        keepAliveIntervalMs: 10000
    });

    sock.ev.on('creds.update', saveCreds);

    sock.ev.on('connection.update', (update) => {
        const { connection, lastDisconnect, qr } = update;

        if (qr) {
            console.log('\n=============================================');
            console.log('SCAN THIS QR CODE WITH YOUR WHATSAPP PHONE');
            console.log('Settings > Linked Devices > Link a Device');
            console.log('=============================================\n');
            qrcode.generate(qr, { small: true });
        }

        if (connection === 'close') {
            const statusCode = lastDisconnect?.error?.output?.statusCode;
            console.log(`❌ Connection Closed (Status: ${statusCode})`);

            // Reconnect if not logged out
            if (statusCode !== 401) {
                console.log("Attempting to reconnect in 3s...");
                setTimeout(connectToWhatsApp, 3000);
            } else {
                console.log("Logged out. Please delete auth_info and try again.");
                process.exit(1);
            }
        } else if (connection === 'open') {
            console.log('\n✅ SUCCESS: Connected to WhatsApp!');
            console.log('Auth saved to /auth_info. You can now run: node index.js\n');
            process.exit(0);
        }
    });

    // Error handling for the socket itself
    sock.ev.on('error', (err) => {
        console.error("Socket Error:", err);
    });
}

connectToWhatsApp().catch(err => {
    console.error("Critical Start Error:", err);
});
