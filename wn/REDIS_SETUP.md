# 🔴 Redis Setup Guide for Windows

To run the production bot, you need a Redis server running.

## Option 1: Native Windows Installer (Easiest)
This installs a compatible version of Redis directly on Windows without Linux.

1.  **Download Installer**:
    Go to this release page: [Redis-x64-3.2.100.msi](https://github.com/microsoftarchive/redis/releases/download/win-3.2.100/Redis-x64-3.2.100.msi)
    *(Note: This is an older Microsoft port, but perfectly fine for this bot).*

2.  **Run Installer**:
    - Double click the `.msi` file.
    - Check "Add the Redis installation folder to the PATH environment variable".
    - Finish installation.

3.  **Verify**:
    - Open a **new** terminal.
    - Type: `redis-cli ping`
    - If it replies `PONG`, you are ready!

## Option 2: Memurai (Modern/Pro)
If you want a modern Redis version on native Windows.

1.  Go to [Memurai.com](https://www.memurai.com/get-memurai).
2.  Download the **Developer Edition** (Free).
3.  Install and Run. It works exactly like Redis.

## Option 3: WSL (Linux Subsystem) - Best Practice
for long-term stability.

1.  Open PowerShell as Administrator.
2.  Run `wsl --install` (and restart if asked).
3.  Open Ubuntu (from Start Menu) and run:
    ```bash
    sudo apt-get update
    sudo apt-get install redis-server
    sudo service redis-server start
    ```

---
**After Setup:**
Run the bot again:
```cmd
node index.js
```
