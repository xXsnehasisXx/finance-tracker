#!/usr/bin/env bash
# Builds ~/.config/finance-tracker/ca-bundle.pem = certifi's public roots + ONLY the corporate roots whose SHA-256
# fingerprint is listed in scripts/ca_allowlist.txt. Certificates only (no private keys are ever exported); the bundle
# lives outside the repository; SSL verification stays ON. Needed only behind TLS interception (gRPC/Gemini).
#
# Refuses to run until the fingerprints in ca_allowlist.txt were confirmed against the IT-published list:
#   scripts/make_ca_bundle.sh --confirmed
set -euo pipefail

REPO="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
ALLOWLIST="$REPO/scripts/ca_allowlist.txt"
OUT_DIR="${HOME}/.config/finance-tracker"
OUT="$OUT_DIR/ca-bundle.pem"
PY="$REPO/.venv/bin/python"

if [[ "${1:-}" != "--confirmed" ]]; then
  echo "Refusing to run: confirm the SHA-256 fingerprints in $ALLOWLIST with IT, then re-run with --confirmed." >&2
  exit 2
fi

mkdir -p "$OUT_DIR" && chmod 700 "$OUT_DIR"
TMP="$(mktemp -d)"; trap 'rm -rf "$TMP"' EXIT

CERTIFI="$("$PY" -c 'import certifi; print(certifi.where())')"
cp "$CERTIFI" "$TMP/bundle.pem"

allowed=$(grep -Eo '([0-9A-Fa-f]{2}:){31}[0-9A-Fa-f]{2}' "$ALLOWLIST" | tr 'a-f' 'A-F')
[[ -n "$allowed" ]] || { echo "No fingerprints found in $ALLOWLIST" >&2; exit 1; }

# Candidate certificates from the keychains (PEM public certs only), split into one file per certificate.
security find-certificate -a -p /Library/Keychains/System.keychain /Library/Keychains/System.keychain > "$TMP/all.pem" 2>/dev/null || true
security find-certificate -a -p > "$TMP/all_user.pem" 2>/dev/null || true
cat "$TMP/all_user.pem" >> "$TMP/all.pem"
awk -v d="$TMP" '/BEGIN CERTIFICATE/{n++; f=sprintf("%s/c%04d.pem", d, n)} f{print > f} /END CERTIFICATE/{f=""}' "$TMP/all.pem"

added=0
for fp in $allowed; do
  found=0
  for c in "$TMP"/c*.pem; do
    [[ -e "$c" ]] || continue
    have=$(openssl x509 -in "$c" -noout -fingerprint -sha256 2>/dev/null | cut -d= -f2 | tr 'a-f' 'A-F')
    if [[ "$have" == "$fp" ]]; then
      { echo; openssl x509 -in "$c" -subject -issuer -noout | sed 's/^/# /'; cat "$c"; } >> "$TMP/bundle.pem"
      echo "added  $fp  $(openssl x509 -in "$c" -noout -subject)"
      found=1; added=$((added + 1)); break
    fi
  done
  [[ $found -eq 1 ]] || echo "WARNING: allow-listed certificate not found in keychain: $fp" >&2
done

[[ $added -gt 0 ]] || { echo "None of the allow-listed certificates were found; bundle not written." >&2; exit 1; }
install -m 644 "$TMP/bundle.pem" "$OUT"
echo "Wrote $OUT (certifi roots + $added allow-listed corporate root(s))."
