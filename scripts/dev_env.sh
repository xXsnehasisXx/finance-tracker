# Source this before running anything that talks to Gemini over gRPC behind corporate TLS interception:
#   source scripts/dev_env.sh
# It only points the TLS libraries at the CA bundle (verification stays enabled). No-op if the bundle does not exist.
_bundle="$HOME/.config/finance-tracker/ca-bundle.pem"
if [ -f "$_bundle" ]; then
  export SSL_CERT_FILE="$_bundle" REQUESTS_CA_BUNDLE="$_bundle" GRPC_DEFAULT_SSL_ROOTS_FILE_PATH="$_bundle"
  echo "TLS: using $_bundle"
else
  echo "TLS: no corporate CA bundle at $_bundle (default roots in use)"
fi
unset _bundle
