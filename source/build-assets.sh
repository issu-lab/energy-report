#!/usr/bin/env bash
set -euo pipefail

source_dir="$(cd "$(dirname "$0")" && pwd)"
assets_dir="$(cd "$source_dir/../assets" && pwd)"
profile_dir="$(mktemp -d)"

render() {
  local name="$1"
  local width="$2"
  local height="$3"
  firefox --headless --no-remote --profile "$profile_dir" --window-size "${width},${height}" --screenshot "$assets_dir/${name}.png" "file://$source_dir/${name}.svg"
}

render energy-report-banner-light 5120 1280
render energy-report-banner-dark 5120 1280
render energy-report-social-preview 1280 640
