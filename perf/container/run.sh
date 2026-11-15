#!/usr/bin/env bash
set -euo pipefail
cd "$(dirname "$0")/../.."
unset APRYSE_API_KEY APRYSE_LICENSE_KEY PDFTRON_LICENSE_KEY TRIAL_KEY
export LIBGL_ALWAYS_SOFTWARE=1
exec python3 -m perf.container.run "$@"
