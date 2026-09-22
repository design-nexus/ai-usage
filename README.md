# AI Usage for Omarchy

One bar icon and one panel for Codex, Grok, Antigravity, Claude Code, Copilot, and Cursor. It reads each agent's local sessions and shows today's usage, quota, models, the last 7 days, tools, and recent sessions.

## Install

```bash
omarchy plugin add https://github.com/design-nexus/ai-usage.git --enable
```

`omarchy plugin add` clones the repo into `~/.config/omarchy/plugins/design-nexus.ai-usage`. `--enable` puts the widget on the bar. Without that flag the plugin stays installed and disabled until you enable it:

```bash
omarchy plugin enable design-nexus.ai-usage
```

Move it after it is on the bar:

```bash
omarchy bar move design-nexus.ai-usage --section right
```

`left`, `center`, and `right` are the other sections. `--before` and `--after` take another widget id.

## Update and remove

```bash
omarchy plugin update design-nexus.ai-usage
omarchy plugin remove design-nexus.ai-usage
```

Update fetches the repo and shows the diff before it fast-forwards. `omarchy plugin update` with no id does that for every git-installed plugin.

## Using it

Left-click the icon to open the panel. Right-click opens settings. Middle-click refreshes.

The panel opens on the running agent whose session was updated most recently. Tabs stay where you put them until the next time the panel opens. If nothing is running, the current tab stays selected.

Activity dots on the icon light up only for agents that are enabled, installed, and currently running.

| Key | Action |
| --- | --- |
| `1`–`5` | Resume that recent session |
| `n` | New session in the terminal |
| `r` | Refresh |
| `s` | Settings, or save while settings are open |
| `q` | Close |

Codex, Grok, and Antigravity resume with `<exe> resume <id>` and can be stopped from the session row. Claude Code, Copilot, and Cursor resume with `<exe> --resume <id>` and have no stop button.

An enabled agent whose CLI is missing still has a tab. The status line says the CLI is not installed.

## Settings

Right-click the icon, or press `s`.

- **Agents.** Turn each agent on or off. A disabled agent drops its tab and activity dot and is not refreshed. All six default to on.
- **Refresh interval.** Idle polling, from 10 to 1800 seconds. A running agent refreshes about every 10 seconds.
- **Bar badge.** Active session count, today's prompts, or off.
- **Quota alerts.** Desktop warning when a reported remaining percent is low. Claude Code, Copilot, and Cursor do not raise these alerts.
- **Terminal.** Override the terminal used for new and resumed sessions. Empty uses `xdg-terminal-exec`.

## Quota

Codex, Grok, and Antigravity show the limits their local data already reports. Copilot uses the signed-in `gh` account, or `COPILOT_GITHUB_TOKEN` / `GH_TOKEN` / `GITHUB_TOKEN`. Cursor uses the login in `~/.config/cursor/auth.json`. Claude Code quota is not estimated. The panel does not invent a remaining percent when the account does not report one.
