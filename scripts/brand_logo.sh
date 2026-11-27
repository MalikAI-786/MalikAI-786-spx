#!/usr/bin/env bash
# Recolor the Malik monogram to the brand orange (#E0662E) on navy and
# size it for the email masthead.
#   scripts/brand_logo.sh <source logo> <output png>
# Source: Drive file "Malik Logo.PNG" (light monogram on dark background).
set -euo pipefail
src="$1"; out="$2"
read -r w h < <(identify -format '%w %h\n' "$src")
tmp="$(mktemp -d)"
convert "$src" -colorspace gray -level 18%,42% "$tmp/mask.png"
convert -size "${w}x${h}" xc:'#0F1B2D' \
  \( -size "${w}x${h}" xc:'#E0662E' "$tmp/mask.png" -alpha off -compose CopyOpacity -composite \) \
  -compose over -composite -resize 160x160 "$out"
rm -rf "$tmp"
sha256sum "$out"
