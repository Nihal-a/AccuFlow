module.exports = {
  apps: [{
    name: "trade-bot",
    script: "./index.js",
    instances: 1,
    exec_mode: "fork",
    watch: false,
    max_memory_restart: "500M",
    env: {
      NODE_ENV: "production",
      TZ: "Asia/Dubai"
    },
    exp_backoff_restart_delay: 100
  }]
}
