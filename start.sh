#!/bin/sh
set -e

if [ -n "$CONFIG_JSON" ]; then
	echo "$CONFIG_JSON" > "config.json"
fi

su-exec nobody python app.py --config config.json
