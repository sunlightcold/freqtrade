#!/usr/bin/env bash
set -euo pipefail

cat >&2 <<'EOF'
DEPLOYMENT BLOCKED: Stage31 failed the current acceptance gates.

Required:
  - win rate >= 70%
  - average trades/day >= 2
  - annual return >= 100% or average daily return >= 0.5%
  - 20-pair, long/short, fee-and-slippage-aware validation

See STAGE33_34_RESEARCH_REPORT.md. No replacement strategy is approved yet.
EOF
exit 2
