#!/usr/bin/env bash
# SYNTHETIC PAPER-TRADE LEDGER. Real money never moved. Educational only. Not investment advice.
#
# preflight.sh — runs before scripts/morning.py.
#
# Checks:
#   1. Token files have 0600 perms (or warns if missing)
#   2. ledger/paper-pnl.csv has NO row for today (we haven't already run)
#   3. yesterday's close row exists (warns if not)
#   4. git working tree is clean (no uncommitted changes)
#
# Exit codes:
#   0   all checks passed
#   1   hard failure (perms wrong, today already in ledger, dirty git tree)
#   2   soft failure / warning only — propagated unless --strict
#
# Usage:
#   scripts/preflight.sh
#   scripts/preflight.sh --strict          # warnings -> failures
#   scripts/preflight.sh --date 2026-05-28 # override "today"

set -uo pipefail

REPO_ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
LEDGER="$REPO_ROOT/ledger/paper-pnl.csv"
TOKEN_DIR="${SPX_TOKEN_DIR:-$HOME/.spx-tokens}"

STRICT=0
TODAY=""
while [ $# -gt 0 ]; do
    case "$1" in
        --strict) STRICT=1; shift ;;
        --date)   TODAY="$2"; shift 2 ;;
        -h|--help)
            grep '^#' "$0" | sed 's/^# \{0,1\}//'
            exit 0
            ;;
        *) echo "preflight: unknown arg '$1'" >&2; exit 1 ;;
    esac
done

if [ -z "$TODAY" ]; then
    TODAY="$(TZ=America/New_York date +%Y-%m-%d)"
fi
YESTERDAY="$(TZ=America/New_York date -v-1d +%Y-%m-%d 2>/dev/null \
    || date -d 'yesterday' +%Y-%m-%d 2>/dev/null \
    || python3 -c 'import datetime; print((datetime.date.today() - datetime.timedelta(days=1)).isoformat())')"

red()   { printf "\033[31m%s\033[0m\n" "$1"; }
green() { printf "\033[32m%s\033[0m\n" "$1"; }
yellow(){ printf "\033[33m%s\033[0m\n" "$1"; }

hard_fail=0
warn=0

echo "preflight: repo=$REPO_ROOT today=$TODAY yesterday=$YESTERDAY"

# -------------------------------------------------------------------------
# 1. Token file perms
# -------------------------------------------------------------------------
echo
echo "[1/4] Token file permissions ($TOKEN_DIR)"
if [ ! -d "$TOKEN_DIR" ]; then
    yellow "  WARN: token dir $TOKEN_DIR does not exist; nothing to check"
    warn=1
else
    bad_perm=0
    while IFS= read -r -d '' tok; do
        # POSIX-portable octal mode (works on BSD/GNU stat)
        mode=$(stat -f '%Lp' "$tok" 2>/dev/null || stat -c '%a' "$tok" 2>/dev/null)
        if [ "$mode" != "600" ]; then
            red "  FAIL: $tok has mode $mode (expected 600)"
            bad_perm=1
        else
            green "  OK:   $tok mode 600"
        fi
    done < <(find "$TOKEN_DIR" -maxdepth 2 -type f -print0)
    if [ "$bad_perm" -eq 1 ]; then
        hard_fail=1
    fi
fi

# -------------------------------------------------------------------------
# 2. Ledger has NO row for today
# -------------------------------------------------------------------------
echo
echo "[2/4] Ledger free of today's row"
if [ ! -f "$LEDGER" ]; then
    yellow "  WARN: ledger $LEDGER not found; first-run scenario assumed"
    warn=1
else
    if awk -F, -v d="$TODAY" 'NR>1 && $1==d {found=1} END {exit !found}' "$LEDGER"; then
        red "  FAIL: ledger already has a row for $TODAY — morning.py would conflict"
        hard_fail=1
    else
        green "  OK:   no row for $TODAY"
    fi
fi

# -------------------------------------------------------------------------
# 3. Yesterday's close row exists
# -------------------------------------------------------------------------
echo
echo "[3/4] Yesterday's close row"
if [ ! -f "$LEDGER" ]; then
    yellow "  WARN: ledger missing — skipping yesterday check"
    warn=1
else
    if awk -F, -v d="$YESTERDAY" 'NR>1 && $1==d {found=1} END {exit !found}' "$LEDGER"; then
        green "  OK:   yesterday ($YESTERDAY) present in ledger"
    else
        yellow "  WARN: yesterday ($YESTERDAY) NOT in ledger — close_track may have been skipped"
        warn=1
    fi
fi

# -------------------------------------------------------------------------
# 4. Git working tree clean
# -------------------------------------------------------------------------
echo
echo "[4/4] Git clean state"
if ! git -C "$REPO_ROOT" rev-parse --is-inside-work-tree >/dev/null 2>&1; then
    yellow "  WARN: $REPO_ROOT is not a git repo"
    warn=1
else
    dirty=$(git -C "$REPO_ROOT" status --porcelain)
    if [ -n "$dirty" ]; then
        red "  FAIL: uncommitted changes:"
        echo "$dirty" | sed 's/^/    /'
        hard_fail=1
    else
        green "  OK:   working tree clean"
    fi
fi

echo
if [ "$hard_fail" -eq 1 ]; then
    red "preflight: HARD FAIL"
    exit 1
fi
if [ "$warn" -eq 1 ]; then
    if [ "$STRICT" -eq 1 ]; then
        red "preflight: warnings present + --strict -> FAIL"
        exit 1
    fi
    yellow "preflight: warnings only (use --strict to fail)"
    exit 2
fi
green "preflight: ALL CHECKS PASSED"
exit 0
