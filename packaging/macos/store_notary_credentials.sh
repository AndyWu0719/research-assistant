#!/usr/bin/env bash
set -euo pipefail

: "${APPLE_ID:?APPLE_ID is required}"
: "${APPLE_TEAM_ID:?APPLE_TEAM_ID is required}"
: "${APPLE_APP_SPECIFIC_PASSWORD:?APPLE_APP_SPECIFIC_PASSWORD is required}"

PROFILE="${APPLE_KEYCHAIN_PROFILE:-research-assistant-notary}"

xcrun notarytool store-credentials "$PROFILE" \
  --apple-id "$APPLE_ID" \
  --team-id "$APPLE_TEAM_ID" \
  --password "$APPLE_APP_SPECIFIC_PASSWORD"

printf 'Stored notary credentials in keychain profile: %s\n' "$PROFILE"
