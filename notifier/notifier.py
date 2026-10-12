#!/usr/bin/env python3
"""Sends a Signal message when files in the Geteilter Ordner change.

Watches the hub's event stream for changed files, from any client and from the
hub's own folder, waits until nothing has changed for QUIET_SECONDS, then sends
one message per batch to a Signal group with signal-cli.

Settings, as environment variables:
  HUB_URL        the hub's API (default http://hub:8384)
  HUB_CONFIG     the hub's config.xml, for its API key
  FOLDER_ID      the shared folder (default geteilter-ordner)
  QUIET_SECONDS  seconds without changes before sending (default 30)
  HUB_NAME       name for changes made in the hub's own folder (default Menti)
  SIGNAL_CONFIG  JSON with "account" and "group_id" (default /config/signal.json)
  SIGNAL_STATE   signal-cli's state folder with the linked account (default /signal-state)

Without a valid signal.json, changes are only logged, nothing is sent.
"""

import json
import os
import re
import subprocess
import sys
import time
import urllib.error
import urllib.request

HUB_URL = os.environ.get("HUB_URL", "http://hub:8384")
HUB_CONFIG = os.environ.get("HUB_CONFIG", "/hub/config/config.xml")
FOLDER_ID = os.environ.get("FOLDER_ID", "geteilter-ordner")
QUIET_SECONDS = int(os.environ.get("QUIET_SECONDS", "30"))
HUB_NAME = os.environ.get("HUB_NAME", "Menti")
SIGNAL_CONFIG = os.environ.get("SIGNAL_CONFIG", "/config/signal.json")
SIGNAL_STATE = os.environ.get("SIGNAL_STATE", "/signal-state")
# files listed per device and action, the rest is counted
MAX_FILES = 10


def log(message):
    print(time.strftime("%Y-%m-%d %H:%M:%S"), message, flush=True)


def read_api_key():
    """Waits until the hub has written its configuration with the API key."""
    while True:
        try:
            with open(HUB_CONFIG, encoding="utf-8") as f:
                match = re.search(r"<apikey>(.*?)</apikey>", f.read())
            if match:
                return match.group(1)
        except OSError:
            pass
        log(f"Waiting for the hub's API key in {HUB_CONFIG}")
        time.sleep(5)


API_KEY = read_api_key()


def api(path, timeout=10):
    request = urllib.request.Request(HUB_URL + path, headers={"X-API-Key": API_KEY})
    with urllib.request.urlopen(request, timeout=timeout) as response:
        return json.load(response)


def device_names():
    """Maps device IDs to names, with the hub's own changes named HUB_NAME."""
    names = {d["deviceID"]: d["name"] or d["deviceID"][:7] for d in api("/rest/config/devices")}
    names[api("/rest/system/status")["myID"]] = HUB_NAME
    return names


def name_of(names, modified_by):
    # events name the device by its short ID, the first part of the full ID
    for device_id, name in names.items():
        if device_id.startswith(modified_by):
            return name
    return modified_by


def latest_event_id():
    """Starts after the newest event, so a restart doesn't report old changes."""
    events = api("/rest/events?limit=1&timeout=1&events=LocalChangeDetected,RemoteChangeDetected", timeout=15)
    return events[-1]["id"] if events else 0


def wait_for_events(since, timeout):
    path = f"/rest/events?since={since}&timeout={timeout}&events=LocalChangeDetected,RemoteChangeDetected"
    return api(path, timeout=timeout + 15)


def format_message(changes, names):
    lines = ["Geteilter Ordner:"]
    for modified_by, actions in changes.items():
        parts = []
        for action, label in (("changed", "neu/geändert"), ("deleted", "gelöscht")):
            paths = sorted(actions[action])
            if not paths:
                continue
            shown = ", ".join(paths[:MAX_FILES])
            if len(paths) > MAX_FILES:
                shown += f" und {len(paths) - MAX_FILES} weitere"
            parts.append(f"{label}: {shown}")
        if parts:
            lines.append(f"- {name_of(names, modified_by)}: " + "; ".join(parts))
    return "\n".join(lines)


def load_signal_config():
    try:
        with open(SIGNAL_CONFIG, encoding="utf-8") as f:
            config = json.load(f)
    except OSError:
        return None
    except json.JSONDecodeError as e:
        log(f"Invalid JSON in {SIGNAL_CONFIG}: {e}")
        return None
    if not config.get("account") or not config.get("group_id"):
        return None
    return config


def send(text):
    config = load_signal_config()
    if not config:
        log(f"Not sent, no account and group_id in {SIGNAL_CONFIG}:\n{text}")
        return
    command = ["signal-cli", "--config", SIGNAL_STATE, "-a", config["account"],
               "send", "-g", config["group_id"], "-m", text]
    try:
        result = subprocess.run(command, capture_output=True, text=True, timeout=120)
    except subprocess.TimeoutExpired:
        log("signal-cli didn't finish within 120 seconds")
        return
    if result.returncode == 0:
        log(f"Sent:\n{text}")
    else:
        log(f"signal-cli failed (exit {result.returncode}): {(result.stderr or result.stdout).strip()}")


def main():
    while True:
        try:
            since = latest_event_id()
            break
        except (urllib.error.URLError, OSError) as e:
            log(f"Waiting for the hub's API: {e}")
            time.sleep(5)
    log(f"Watching folder {FOLDER_ID} on {HUB_URL}, starting after event {since}")

    # device's short ID -> {"changed": set of paths, "deleted": set of paths}
    changes = {}
    last_change = 0.0

    while True:
        timeout = QUIET_SECONDS if changes else 60
        try:
            events = wait_for_events(since, timeout)
        except (urllib.error.URLError, OSError, json.JSONDecodeError) as e:
            log(f"Hub not reachable, retrying: {e}")
            time.sleep(10)
            continue

        for event in events:
            since = max(since, event["id"])
            data = event["data"]
            # only files of the shared folder; folders change all the time, since
            # they're ignored and only the files of the synced types count
            if data.get("folderID", data.get("folder")) != FOLDER_ID or data.get("type") != "file":
                continue
            actions = changes.setdefault(data.get("modifiedBy", "?"), {"changed": set(), "deleted": set()})
            path = data["path"]
            if data.get("action") == "deleted":
                actions["changed"].discard(path)
                actions["deleted"].add(path)
            else:
                actions["deleted"].discard(path)
                actions["changed"].add(path)
            last_change = time.time()

        if changes and time.time() - last_change >= QUIET_SECONDS:
            try:
                send(format_message(changes, device_names()))
            except (urllib.error.URLError, OSError) as e:
                log(f"Couldn't read the device names, retrying: {e}")
                continue
            changes = {}


if __name__ == "__main__":
    try:
        main()
    except KeyboardInterrupt:
        sys.exit(0)
