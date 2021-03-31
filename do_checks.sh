#!/bin/bash

# Exit early on errors
#set -eu

# Python buffers stdout. Without this, you won't see what you "print" in the Activity Logs
export PYTHONUNBUFFERED=true

# Install Python 3 virtual env
#VIRTUALENV=.data/venv

#if [ ! -d $VIRTUALENV ]; then
#  python3 -m venv $VIRTUALENV
#fi

#if [ ! -f $VIRTUALENV/bin/pip ]; then
#  curl --silent --show-error --retry 5 https://bootstrap.pypa.io/get-pip.py | $VIRTUALENV/bin/python
#fi

# Install the requirements
#$VIRTUALENV/bin/pip install -r requirements.txt

# Run a glorious Python 3 server
#$VIRTUALENV/bin/gunicorn attnfeeddj:app --access-logfile '-' --log-level 'debug'
while [ true ]
  do
    /usr/bin/wget --quiet --output-document .data/last_check.txt https://intelligent-insidious-concavenator.glitch.me/check
    /usr/bin/wget --quiet --output-document .data/last_replies.txt https://intelligent-insidious-concavenator.glitch.me/process_replies
    /usr/bin/wget --quiet --output-document .data/last_searches.txt https://intelligent-insidious-concavenator.glitch.me/process_searches
    sleep 60
  done
#/usr/bin/wget --quiet --output-document .data/last_timeslines.txt https://intelligent-insidious-concavenator.glitch.me/process_timelines