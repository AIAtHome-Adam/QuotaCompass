#!/usr/bin/env sh
set -eu

action="${1:-install}"
config_path="${2:-}"
command_path="${QUOTACOMPASS_COMMAND:-$(command -v quotacompass || true)}"

case "$action" in
  preview|install|uninstall) ;;
  *) echo "usage: $0 [preview|install|uninstall] [config-path]" >&2; exit 2 ;;
esac

if [ -z "$command_path" ] && [ "$action" != "uninstall" ]; then
  echo "quotacompass is not on PATH; set QUOTACOMPASS_COMMAND" >&2
  exit 2
fi

case "$command_path$config_path" in
  *'"'*|*'
'*) echo "command and config paths cannot contain quotes or newlines" >&2; exit 2 ;;
esac

xml_escape() {
  printf '%s' "$1" | sed -e 's/&/\&amp;/g' -e 's/</\&lt;/g' -e 's/>/\&gt;/g'
}

render_plist() {
  command_xml="$(xml_escape "$command_path")"
  config_xml="$(xml_escape "$config_path")"
  printf '%s\n' '<?xml version="1.0" encoding="UTF-8"?>'
  printf '%s\n' '<!DOCTYPE plist PUBLIC "-//Apple//DTD PLIST 1.0//EN" "http://www.apple.com/DTDs/PropertyList-1.0.dtd">'
  printf '%s\n' '<plist version="1.0"><dict>'
  printf '%s\n' '  <key>Label</key><string>com.quotacompass.server</string>'
  printf '  <key>ProgramArguments</key><array><string>%s</string>' "$command_xml"
  if [ -n "$config_xml" ]; then
    printf '<string>--config</string><string>%s</string>' "$config_xml"
  fi
  printf '%s\n' '<string>serve</string></array>'
  printf '%s\n' '  <key>RunAtLoad</key><true/>'
  printf '%s\n' '  <key>KeepAlive</key><true/>'
  printf '%s\n' '  <key>ProcessType</key><string>Background</string>'
  printf '%s\n' '</dict></plist>'
}

render_unit() {
  printf '%s\n' '[Unit]' 'Description=Local-first QuotaCompass quota service' 'After=network-online.target' '' '[Service]' 'Type=simple'
  if [ -n "$config_path" ]; then
    printf 'ExecStart="%s" --config "%s" serve\n' "$command_path" "$config_path"
  else
    printf 'ExecStart="%s" serve\n' "$command_path"
  fi
  printf '%s\n' 'Restart=on-failure' 'RestartSec=5' 'NoNewPrivileges=true' '' '[Install]' 'WantedBy=default.target'
}

if [ "$(uname -s)" = "Darwin" ]; then
  target="$HOME/Library/LaunchAgents/com.quotacompass.server.plist"
  if [ "$action" = "uninstall" ]; then
    launchctl bootout "gui/$(id -u)" "$target" 2>/dev/null || true
    rm -f "$target"
    exit 0
  fi
  if [ "$action" = "preview" ]; then
    render_plist
    exit 0
  fi
  mkdir -p "$(dirname "$target")"
  render_plist >"$target"
  launchctl bootstrap "gui/$(id -u)" "$target"
  exit 0
fi

unit_dir="${XDG_CONFIG_HOME:-$HOME/.config}/systemd/user"
unit="$unit_dir/quotacompass.service"
if [ "$action" = "uninstall" ]; then
  systemctl --user disable --now quotacompass.service 2>/dev/null || true
  rm -f "$unit"
  systemctl --user daemon-reload
  exit 0
fi
if [ "$action" = "preview" ]; then
  render_unit
  exit 0
fi
mkdir -p "$unit_dir"
render_unit >"$unit"
systemctl --user daemon-reload
systemctl --user enable --now quotacompass.service
