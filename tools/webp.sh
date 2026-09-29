#!/bin/sh
# Pack baked PNGs into WebP (colour at q90, ORM at q95).
#   sh tools/webp.sh <data dir>
set -e
D=$1
cwebp -quiet -q 90 "$D/ship_base.png" -o "$D/ship_base.webp"
cwebp -quiet -q 95 "$D/ship_orm.png" -o "$D/ship_orm.webp"
du -ch "$D"/*.webp | tail -1
