#!/bin/bash

set -e

dn="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"


"$dn/__inenv" python "$dn/cli.py" "$@"