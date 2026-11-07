#!/bin/sh
# Documented page-cache drop for laboratory os_cache_cold attempts.
set -eu
sync
echo 3 | sudo tee /proc/sys/vm/drop_caches
