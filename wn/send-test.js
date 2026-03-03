import { makeWASocket, useMultiFileAuthState, Browsers, fetchLatestBaileysVersion } from '@whiskeysockets/baileys';
import pino from 'pino';
import { generateTradeTable } from './image.js';

const TEST_SCENARIOS = [
    {
        name: "Case 1: Has Transactions (Should send Image)",
        whatsappnumber: "919846080265",
        balance: "5,420.00",
        opening_balance: "4,000.00",
        transactions: [
            { type: "JL", details: "Market Entry", qty: "10", rate: "142.00", debit: "1,420.00", credit: "", balance: "5,420.00" }
        ]
    },
    {
        name: "Case 2: No Transactions (Should send Text)",
        whatsappnumber: "919846111348",
        balance: "1,250.50",
        opening_balance: "1,250.50",
        transactions: []
    }
];

async function runRobustnessTest() {
    console.log(`🚀 Starting Robustness Test (Conditional Image/Text)...`);

    // Setup
    const { state, saveCreds } = await useMultiFileAuthState('auth_info');
    const { version } = await fetchLatestBaileysVersion();
    const sock = makeWASocket({ version, logger: pino({ level: 'silent' }), auth: state, browser: Browsers.macOS('Desktop') });
    sock.ev.on('creds.update', saveCreds);

    sock.ev.on('connection.update', async (update) => {
        if (update.connection === 'open') {
            console.log('✅ Connected to WhatsApp!');

            for (const customer of TEST_SCENARIOS) {
                console.log(`\nTesting ${customer.name} -> +${customer.whatsappnumber}`);
                const phone = customer.whatsappnumber + "@s.whatsapp.net";

                try {
                    const hasTransactions = customer.transactions && customer.transactions.length > 0;

                    if (hasTransactions) {
                        console.log("🎨 Generating Table Image...");
                        const imageBuffer = await generateTradeTable(customer);
                        await sock.sendMessage(phone, {
                            image: imageBuffer,
                            caption: `� Trade Summary for Account ${customer.whatsappnumber}`
                        });
                        console.log("🎉 SUCCESS: Image Sent.");
                    } else {
                        console.log("📝 Sending Balance Text...");
                        await sock.sendMessage(phone, {
                            text: `📋 Account Balance Update\n\nYour current balance is: *${customer.balance}*\n\n(No recent transactions to display)`
                        });
                        console.log("🎉 SUCCESS: Text Sent.");
                    }

                    // Delay for stability
                    await new Promise(r => setTimeout(r, 3000));
                } catch (err) {
                    console.error("❌ Error:", err.message);
                }
            }
            console.log("\n🏁 All tests complete. Exiting...");
            process.exit(0);
        }
    });
}

runRobustnessTest();
