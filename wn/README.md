# 🚀 WhatsApp Trade Bot

## Setup & Deployment

1. **Install System Dependencies**
   Ensure you are using a strictly local environment (Node.js v18+).
   ```bash
   chmod +x setup.sh
   ./setup.sh
   ```
   *Note: This script installs `redis` (assuming Linux environment) and essential polyfills (`jsdom`, `canvas`) required for image generation in Node.*

2. **Auth Generation**
   Run the QR generator. Scan this with your WhatsApp "Linked Devices".
   ```bash
   npm run qr
   ```
   *This creates an `auth_info` directory securely.*

3. **Data Setup**
   Place your customer data in `customers.json`. You can use the generated `test-customers.json` as a starter:
   ```bash
   cp test-customers.json customers.json
   ```

4. **Start Production**
   Use PM2 to manage the process.
   ```bash
   pm2 start ecosystem.config.js
   pm2 logs trade-bot
   ```

## Features
- **Anti-Ban**: Uses Poisson distribution delays, randomized templates, and correct timezone enforcement.
- **Privacy Core**: "Local-only" processing. No cloud APIs.
- **Queuing**: BullMQ + Redis handles retries and scheduling.

## Troubleshooting
- **Redis Error**: Ensure `redis-server` is running on port 6379.
- **Image Error**: If `canvas` fails to build, install system libraries: `sudo apt-get install build-essential libcairo2-dev libpango1.0-dev`
- **Timezone**: Logs will show "Sleeping (Dubai Night)" if outside 8 AM - 10 PM Dubai time.

## Scripts
- `node qr.js` - Generate auth
- `node index.js` - Run manually (testing)
