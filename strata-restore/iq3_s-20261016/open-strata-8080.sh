#!/usr/bin/env bash
# Open TCP 8080 on INPUT for Strata LAN access (no Docker).
set -euo pipefail
if iptables -C INPUT -p tcp --dport 8080 -j ACCEPT 2>/dev/null; then
  echo "8080 ACCEPT already present"
  exit 0
fi
iptables -I INPUT -p tcp --dport 8080 -j ACCEPT
iptables -C INPUT -p tcp --dport 8080 -j ACCEPT
echo "8080 ACCEPT installed"
