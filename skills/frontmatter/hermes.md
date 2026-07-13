---
name: quotacompass
description: Check local AI subscription and API quota usage, reset times, provider suggestions, expiring-unused nudges, and authentication health. Use when choosing an AI provider or asking how much quota remains.
version: 0.1.0
author: QuotaCompass contributors
license: MIT
metadata:
  hermes:
    tags: [productivity, ai, quota, local-first]
    requires_toolsets: [terminal]
    config:
      - key: quotacompass.url
        description: URL of the local QuotaCompass dashboard and API
        default: http://127.0.0.1:4747
        prompt: QuotaCompass URL
      - key: quotacompass.state_file
        description: Optional absolute path to current.json for file fallback
        default: ""
        prompt: QuotaCompass state file path (optional)
    blueprint:
      schedule: "0 18 * * *"
      deliver: origin
      prompt: "Run the QuotaCompass nudge check. If any quota window is more than 25% unused and resets within 24 hours, remind me which provider and window to use before reset. Stay silent if there are no nudges."
      no_agent: false
required_environment_variables:
  - name: QUOTACOMPASS_TOKEN
    prompt: Optional QuotaCompass API bearer token
    help: Required only when the local server has server.auth_token configured
    required_for: Authenticated REST fallback
---
