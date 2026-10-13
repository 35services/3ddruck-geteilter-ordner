# Geteilter Ordner

A folder called "Geteilter Ordner" on the desktop of every machine of the 3D-Druck-AG,
kept in sync with [Syncthing](https://syncthing.net/). Only `.3mf`, `.stl`, `.txt`
and `.svg` files are synced, about 5 seconds after a change. A Signal message
reports which files changed.

Made for the 3D-Druck-AG, whose machines run the image from
[jugendhackt-iso](https://github.com/35services/3ddruck-jugend-hackt-iso) (its
`ansible/tailscale.yml` puts machines into the tailnet), but it works with any
Linux machines and Macs.

```
                 ┌──────────────────────────────┐
                 │ Menti's Mac (Docker)         │
                 │  hub: Syncthing              │
                 │  notifier: events → Signal   │
                 └──────────────┬───────────────┘
        local network or Tailscale, whichever works
        ┌────────────────┬──────┴─────────┬────────────────┐
   3d-ag-lenovo      3d-ag-001        3d-ag-002          …
```

- **The hub** runs on the Menti's Mac, in Docker. Every client only knows the hub,
  so all files go through it, and stopping it stops all syncing.
- **Clients** run their own Syncthing instance just for this folder, separate from
  any other Syncthing, as a user service.
- **Connections** go directly over the local network when possible, otherwise over
  Tailscale. Syncthing's public discovery and relay servers are turned off.
- **Everyone can add, change and delete files.** The hub keeps old versions and
  deleted files for 30 days, in `.stversions` in its folder.

## Setup

The commands in this file run in the repository's folder, on the Menti's Mac,
which controls everything with Ansible. Your machines, paths and addresses are
kept out of git: start from the examples.

```sh
cp ansible/inventory.example.ini ansible/inventory.ini
cp -R ansible/host_vars.example ansible/host_vars
```

Then fill in `ansible/inventory.ini`, and in `ansible/host_vars/` keep the file
of your hub, named like it is in the inventory (`localhost.yml` for the Mac).

## The hub on the Menti's Mac

Needs Docker Desktop, Tailscale and Ansible (`brew install ansible`).

```sh
ansible-playbook -i ansible/inventory.ini ansible/hub.yml
```

This creates `~/Desktop/Geteilter Ordner` with the folder icon, starts the hub and
the notifier with `docker compose`, and configures the hub. Run it again after
changing `ansible/group_vars/all.yml` or `notifier/`.

- **Web interface:** http://127.0.0.1:8384, only reachable on the Mac. It shows the
  connected machines, and whether they connect over the local network
  (`192.168.…`) or Tailscale (`100.…`).
- **Turn it off:** `docker compose down` in the repository's folder. Nothing syncs until
  `docker compose up -d`. The clients keep their files.
- **Pause just the folder:** in the web interface, **Pause** on the folder.
- **Restore a deleted or overwritten file:** it's in `~/Desktop/Geteilter Ordner/.stversions`,
  with the time of the change in its name (`a~20261012-070113.stl`). Copy it back
  into the folder. In Finder, `Cmd-Shift-.` shows hidden folders like `.stversions`.
- **The hub only syncs while the Mac is on and awake.** Changes made in the
  meantime sync when it's back.

The hub's keys and configuration are in the Docker volume `geteilter-ordner_hub-data`,
not in the repository. `docker compose down -v` deletes them, and every client would
then have to be registered again.

Changes made on the Mac itself are noticed within a minute: Docker Desktop doesn't
pass file changes into the container reliably, so the hub also rescans every minute.

## Clients

```sh
ansible-playbook -i ansible/inventory.ini ansible/clients.yml --ask-become-pass
```

Run it on the Mac, since it registers each client at the hub through the hub's API.
It installs Syncthing, creates the folder on the desktop (`~/Schreibtisch/Geteilter Ordner`
or `~/Desktop/…`) with the folder icon, starts the user service `geteilter-ordner`
(configuration in `~/.local/state/geteilter-ordner`, web interface on
`127.0.0.1:8385`), and shares the folder with the hub.

- `ansible/inventory.ini` lists the machines by their Tailscale names. Sticks use
  the Debian Live default password `live`, so they need no prompt.
- `--skip-tags install` updates the configuration without sudo, once Syncthing is
  installed. `--tags icon` only updates the folder icon.
- `--limit stick-1.example.ts.net` runs it for one machine.

On a Linux client: `systemctl --user status geteilter-ordner` and
`journalctl --user -u geteilter-ordner`.

**Linux without systemd** (sysvinit, e.g. MX Linux) has no user services: there,
`/etc/init.d/geteilter-ordner` runs Syncthing as the user from boot
(`sudo service geteilter-ordner status`), and the folder icon is set through a
temporary session bus (`dbus-run-session`). It still needs `--ask-become-pass` or
the password in the inventory, also for `--skip-tags install`, since the start
script is a system service.

**Macs** (`[macs]` in the inventory, `ansible/client-darwin.yml`) need no admin
rights and no Homebrew:

- Syncthing comes from its official release into `~/.local/opt`: 1.30.0 on macOS 11,
  the last version for it, otherwise the current one. It syncs fine with a newer hub.
- A launchd user agent (`~/Library/LaunchAgents/de.kjg.geteilter-ordner.plist`)
  starts it; its log is `~/Library/Logs/geteilter-ordner.log`.
- The folder is on the desktop, `~/Desktop/Geteilter Ordner`, with the KJG icon.
  macOS protects the desktop: on the first run, macOS asks on the Mac whether
  `syncthing` may access the desktop folder. Until someone confirms, Syncthing
  waits, and the playbook stops with a timeout; run it again afterwards. If macOS
  doesn't ask, allow it in **System Preferences → Security & Privacy → Privacy →
  Files and Folders** (or **Full Disk Access**) with the admin account, for
  `syncthing` in `~/.local/opt/syncthing-macos-…/`.
- An earlier setup kept the folder in the home folder with a link on the desktop;
  the playbook moves it to the desktop.
- Ansible needs Python 3.9 or newer on the Mac. macOS 11 only has 3.8 (with the
  developer tools, `xcode-select --install`), so the MacBook uses a standalone
  Python from [python-build-standalone](https://github.com/astral-sh/python-build-standalone)
  in `~/.local/python-3.12`, set as `ansible_python_interpreter` in the inventory.

## Settings

`ansible/group_vars/all.yml`:

- `geteilter_ordner_file_types`: the synced file types. After changing it, run
  both playbooks, since every machine has its own copy of the list (`.stignore`).
- `geteilter_ordner_watch_delay`: seconds between a change and sending it.
- `geteilter_ordner_keep_versions_days`: how long the hub keeps old versions.
- `geteilter_ordner_hub_addresses`: where the clients find the hub, by the Mac's
  local name and its Tailscale name. Update it and run `clients.yml` if the Mac's
  names change.

Files in subfolders are synced too. Since only files count, a deleted subfolder is
noticed at the next rescan, within a minute, not right away.

## Signal notifications

The notifier (`notifier/`) watches the hub's events and, 30 seconds after the last
change, sends one message to a Signal group, e.g.:

```
Geteilter Ordner:
- 3d-ag-001: neu/geändert: herbst/hands.3mf, herbst/party hat.3mf
- Menti: gelöscht: alt.stl
```

"Menti" are changes made in the folder on the Mac. Like in
[3d-printing-simple-filament-tool](https://github.com/35services/3d-printing-simple-filament-tool),
`signal-cli` is part of the notifier's image, and its state, the linked Signal
account, is mounted from `signal/state`. `signal/` is ignored by git: it holds
real account keys, never commit it.

1. Link the notifier as a new device of a Signal account:
   ```sh
   docker compose exec notifier sh -c \
     'signal-cli --config /signal/state link -n "Geteilter Ordner" | (read uri; echo "$uri" | qrencode -t ansiutf8; cat)'
   ```
   Scan the QR code in the Signal app: **Settings → Linked devices → Link new device**.
   Use a separate link for this, rather than copying the state of another tool:
   two programs using the same state at the same time get in each other's way.
2. Find the group's ID, the `Id:` value:
   ```sh
   docker compose exec notifier signal-cli --config /signal/state -a +49… listGroups
   ```
3. Copy `signal.example.json` to `signal/signal.json` and fill in `account` (the
   phone number) and `group_id`. The notifier reads it for every message, so no
   restart is needed.

**Using an existing signal-cli login instead,** e.g. a `signal-cli` installed on the
Mac with Homebrew and linked there: set its folder in `.env` next to
`docker-compose.yml` (ignored by git), and start the notifier again with
`docker compose up -d notifier`:

```sh
SIGNAL_STATE_DIR=/Users/<name>/.local/share/signal-cli
```

The notifier then uses that state directly, not a copy, since copies of a Signal
login drift apart and break. Don't run that local signal-cli at the same time as
a message is sent. The group's ID is in `signal-cli -a +49… listGroups` on the Mac.

Without `signal/signal.json`, the notifier only logs the messages:
`docker logs -f geteilter-ordner-notifier`.

## Moving the hub

The hub can run on any machine with Docker, e.g. a Raspberry Pi instead of the
Menti's Mac, so syncing doesn't depend on the Mac being awake. Each host's paths
and the addresses the clients use to reach it are in `ansible/host_vars/` (see
`ansible/host_vars.example/`). The `hub` group in `ansible/inventory.ini` says
which machine is the hub, and `hub_next` a prepared one.

In the commands below, `pi@raspberry-pi.example.ts.net` is the new hub, and
`~/geteilter-ordner` its `hub_compose_dir`.

### Preparing the new hub

- Docker with Compose, and the user in the `docker` group, so no sudo.
- `ansible/host_vars/<name in the inventory>.yml`, from the example. Use the
  machine's cable address with a fixed DHCP lease in `hub_addresses`: `.local`
  names may resolve wrongly on machines that run Docker, and a machine on cable
  and Wi-Fi at the same time answers on both.
- Ports 22000 (TCP and UDP) must be free there. The web interface stays on its
  `127.0.0.1:8384`.
- Add it to `[hub_next]`, then copy the files, download Syncthing's image and
  build the notifier there, without starting anything:
  ```sh
  ansible-playbook -i ansible/inventory.ini ansible/hub.yml -e hub_hosts=hub_next -e hub_prepare_only=true
  ```
- Signal: `signal/signal.json` and a linked account there, or `hub_signal_state_dir`
  pointing to another tool's signal-cli login on the same machine. signal-cli
  locks the state while one of them uses it.

### Moving

The hub's identity (its keys) and its database move along, so the clients don't
need to be registered again. Two rules:

- **Never run both hubs at the same time.** They'd have the same identity.
- **Copy the files before the new hub starts.** The database lists the files the
  hub has. If it started with the database but without the files, it would see
  them as deleted and delete them on every client.

1. Stop the old hub. The clients keep their files and wait.
   ```sh
   docker compose down
   ```
2. Save the hub's identity and database from its Docker volume:
   ```sh
   docker run --rm -v geteilter-ordner_hub-data:/data -v "$PWD":/backup alpine \
     tar czf /backup/hub-data.tgz -C /data .
   ```
3. Copy the files, including `.stversions` with the old versions, and the saved
   data to the new hub:
   ```sh
   rsync -a --exclude $'Icon\r' --exclude .DS_Store \
     "$HOME/Desktop/Geteilter Ordner/" \
     "pi@raspberry-pi.example.ts.net:geteilter-ordner/Geteilter Ordner/"
   scp hub-data.tgz pi@raspberry-pi.example.ts.net:geteilter-ordner/
   ```
4. On the new hub, put the data into the hub's (still empty) volume. Syncthing
   writes as user ID 1000 there; use the user ID that owns the shared folder:
   ```sh
   ssh pi@raspberry-pi.example.ts.net 'cd ~/geteilter-ordner &&
     docker run --rm -v geteilter-ordner_hub-data:/data -v "$PWD":/backup alpine \
       sh -c "tar xzf /backup/hub-data.tgz -C /data && chown -R 1000:1000 /data" &&
     rm hub-data.tgz'
   ```
5. In `ansible/inventory.ini`, move the new hub from `[hub_next]` to `[hub]`, and
   the old one out of `[hub]`.
6. Start the new hub, then give the clients its addresses. Both need no sudo:
   ```sh
   ansible-playbook -i ansible/inventory.ini ansible/hub.yml
   ansible-playbook -i ansible/inventory.ini ansible/clients.yml --skip-tags install
   ```
7. Check: open the web interface through an SSH tunnel, all clients should be
   connected and the folder "Up to Date":
   ```sh
   ssh -L 8384:127.0.0.1:8384 pi@raspberry-pi.example.ts.net
   ```
   then http://127.0.0.1:8384.
8. Once everything syncs, the old hub's copy can go: rename its folder (e.g. to
   `Geteilter Ordner (alter Hub)`), and later delete the old volume with
   `docker volume rm geteilter-ordner_hub-data`. To use the old hub's Mac as a
   client, add it to the clients.

Moving back works the same way, the other way round.

### Operating a hub on a server

- Turn it off: `ssh pi@raspberry-pi.example.ts.net 'cd ~/geteilter-ordner && docker compose down'`
- Notifier log: `ssh pi@raspberry-pi.example.ts.net docker logs -f geteilter-ordner-notifier`
- Old versions and deleted files: `~/geteilter-ordner/Geteilter Ordner/.stversions`
- On a Raspberry Pi with an SD card, back up `~/geteilter-ordner` and the volume
  now and then, e.g. with step 2.
