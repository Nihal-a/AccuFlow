#!/bin/bash

# BASH COLORS
GREEN='\033[0;32m'
RED='\033[0;31m'
NC='\033[0m'

echo -e "${GREEN}🔥 STARTING SETUP SEQUENCE...${NC}"

# 1. Install Dependencies
echo -e "${GREEN}📦 Installing NPM Packages...${NC}"
npm install

# CRITICAL: Dependencies requested by user don't include JSDOM/Canvas for html2canvas in Node.
# Adding them for functionality.
echo -e "${GREEN}🔧 Installing Image Gen Polyfills (jsdom, canvas)...${NC}"
npm install jsdom canvas

# 2. Redis Setup (Check if running)
if ! command -v redis-server &> /dev/null; then
    echo -e "${RED}⚠️  Redis not found. Please install Redis manually (WSL/Linux).${NC}"
else
    echo -e "${GREEN}✅ Redis found.${NC}"
fi

# 3. Security Hardening
echo -e "${GREEN}🔒 Hardening File Permissions...${NC}"
chmod 600 customers.json 2>/dev/null || true
chmod 600 .env 2>/dev/null || true
# Lock down auth folder if it exists
if [ -d "auth_info" ]; then
    chmod 700 auth_info
fi

echo -e "${GREEN}🚀 SETUP COMPLETE. Run 'npm run qr' next!${NC}"
