import QtQuick
import Quickshell.Io

Item {
  id: root
  visible: false
  property string providerId: ""
  property var settings: ({})
  property bool refreshing: false
  property bool available: false
  property var data: ({})
  property string color: "#888888"
  property string name: providerId
  property string providerName: name
  property bool ready: data.ready === true
  property bool active: data.active === true
  property bool hasActiveSession: data.hasActiveSession === true
  property string activeStatus: data.activeStatus || "Idle"
  property bool hasLocalStats: data.hasLocalStats === true
  property string usageStatusText: data.usageStatusText || ""
  property string authHelpText: data.authHelpText || ""
  property string currentModel: data.currentModel || ""
  property double lastUpdatedMs: data.updatedAt ? Date.parse(data.updatedAt) : 0
  property double lastFullRefreshMs: data.lastFullRefreshMs || lastUpdatedMs
  property var quotaGroups: data.quotaGroups || []
  property var recentSessions: data.recentSessions || []
  property var activeSessions: data.activeSessions || []
  property int todayPrompts: Number(data.todayPrompts || 0)
  property int todayTotalTokens: Number(data.todayTotalTokens || 0)
  property int todaySteps: Number(data.todaySteps || 0)
  property int totalPrompts: Number(data.totalPrompts || 0)
  property var recentDays: data.recentDays || []
  property var toolUsage: data.toolUsage || ({})
  property var modelUsage: data.modelUsage || ({})
  property var modelList: data.modelList || []
  property string scannerScriptPath: ""
  property string executable: data.display ? data.display.executable : providerId
  property bool canKill: data.canKill !== false
  property string quotaNote: data.quotaNote || ""
  property string planTier: data.planTier || ""
  property int premiumRequests: Number(data.premiumRequests || 0)
  readonly property bool agentEnabled: {
    var key = ({
      codex: "enableCodex",
      grok: "enableGrok",
      antigravity: "enableAntigravity",
      claude: "enableClaude",
      copilot: "enableCopilot",
      cursor: "enableCursor"
    })[providerId]
    if (!key) return true
    var value = settings ? settings[key] : undefined
    return value !== false
  }
  readonly property string scanner: String(Qt.resolvedUrl("../scripts/usage_scanner.py")).replace("file://", "")
  Process {
    id: process
    stdout: StdioCollector { waitForEnd: true; onStreamFinished: root.apply(text) }
    onExited: root.refreshing = false
  }
  function apply(text) {
    try {
      var next = JSON.parse(text)
      data = next; available = next.available === true
      color = next.display && next.display.color ? next.display.color : color
      name = next.name || name
    } catch (e) { data = { error: "Scanner response could not be read", usageStatusText: String(e) }; available = false }
  }
  function refresh(force) {
    if (process.running) return
    var cmd = ["python3", scanner, providerId]
    if (force) cmd.push("--force")
    var skipsQuota = providerId === "claude" || providerId === "copilot" || providerId === "cursor"
    if (settings.enableQuotaAlerts !== false && !skipsQuota) cmd.push("--notify-low-quota", String(settings.quotaAlertThreshold || 15))
    refreshing = true; process.command = cmd; process.running = true
  }
}
