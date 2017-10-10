#!/usr/bin/dumb-init /bin/sh
set -e

if [ -n "$CONFIG_JSON" ]; then
	echo "$CONFIG_JSON" > "config.json"
fi

su-exec rundeck-consul python app.py config.json
