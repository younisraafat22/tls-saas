"use client";

import { useState, useEffect, useRef, useCallback } from "react";
import { adminApi } from "@/lib/api";
import { useWebSocket } from "@/hooks/useWebSocket";
import {
  Terminal, RefreshCw, Trash2, Download, ChevronDown,
  ChevronUp, Wifi, WifiOff, Circle,
} from "lucide-react";

interface LogEntry {
  ts: string;
  level: string;
  branch: string;
  message: string;
}

type Tab = "monitor" | "system";
type LineCount = 50 | 100 | 200 | 500;

function levelColor(level: string): string {
  switch (level?.toUpperCase()) {
    case "ERROR":   return "text-red-400";
    case "WARNING":
    case "WARN":    return "text-yellow-400";
    case "INFO":    return "text-green-400";
    case "DEBUG":   return "text-blue-400";
    default:        return "text-gray-300";
  }
}

function levelBg(level: string): string {
  switch (level?.toUpperCase()) {
    case "ERROR":   return "bg-red-500/10 border-red-500/20";
    case "WARNING":
    case "WARN":    return "bg-yellow-500/10 border-yellow-500/20";
    case "INFO":    return "bg-green-500/10 border-green-500/20";
    case "DEBUG":   return "bg-blue-500/10 border-blue-500/20";
    default:        return "bg-white/3 border-white/5";
  }
}

function sysLogLevel(line: string): string {
  const l = line.toLowerCase();
  if (l.includes(" error") || l.includes("[error]"))    return "ERROR";
  if (l.includes(" warning") || l.includes("[warn"))    return "WARNING";
  if (l.includes(" info") || l.includes("[info]"))      return "INFO";
  if (l.includes(" debug") || l.includes("[debug]"))    return "DEBUG";
  return "DEFAULT";
}

function formatTs(ts: string): string {
  try {
    return new Date(ts).toLocaleTimeString("en-GB", { hour12: false });
  } catch {
    return ts?.slice(11, 19) ?? "";
  }
}

export default function AdminLogsPage() {
  const [tab, setTab] = useState<Tab>("system");
  const [lineCount, setLineCount] = useState<LineCount>(200);
  const [autoScroll, setAutoScroll] = useState(true);
  const [autoRefresh, setAutoRefresh] = useState(true);

  // Monitor logs (in-memory from scheduler)
  const [monitorLogs, setMonitorLogs] = useState<LogEntry[]>([]);
  const [monitorLoading, setMonitorLoading] = useState(false);

  // System logs (journalctl)
  const [systemLines, setSystemLines] = useState<string[]>([]);
  const [systemLoading, setSystemLoading] = useState(false);
  const [lastRefresh, setLastRefresh] = useState<Date | null>(null);

  const logEndRef = useRef<HTMLDivElement>(null);
  const intervalRef = useRef<NodeJS.Timeout | null>(null);

  const { connected, lastMessage } = useWebSocket(true);

  // Live monitor logs via WebSocket
  useEffect(() => {
    if (!lastMessage) return;
    if (lastMessage.type === "monitor_log") {
      const entry: LogEntry = {
        ts: lastMessage.ts,
        level: lastMessage.level,
        branch: lastMessage.branch || "",
        message: lastMessage.message,
      };
      setMonitorLogs((prev) => [...prev.slice(-299), entry]);
    }
  }, [lastMessage]);

  const fetchMonitorLogs = useCallback(async () => {
    setMonitorLoading(true);
    try {
      const data = await adminApi.getCheckerLogs(lineCount);
      if (Array.isArray(data)) setMonitorLogs(data);
    } catch {}
    setMonitorLoading(false);
  }, [lineCount]);

  const fetchSystemLogs = useCallback(async () => {
    setSystemLoading(true);
    try {
      const data: any = await adminApi.getSystemLogs(lineCount);
      setSystemLines(data?.lines ?? []);
      setLastRefresh(new Date());
    } catch {}
    setSystemLoading(false);
  }, [lineCount]);

  // Initial load
  useEffect(() => {
    fetchMonitorLogs();
    fetchSystemLogs();
  }, [fetchMonitorLogs, fetchSystemLogs]);

  // Auto-refresh system logs
  useEffect(() => {
    if (intervalRef.current) clearInterval(intervalRef.current);
    if (autoRefresh && tab === "system") {
      intervalRef.current = setInterval(fetchSystemLogs, 10000);
    }
    return () => { if (intervalRef.current) clearInterval(intervalRef.current); };
  }, [autoRefresh, tab, fetchSystemLogs]);

  // Auto-scroll
  useEffect(() => {
    if (autoScroll && logEndRef.current) {
      logEndRef.current.scrollIntoView({ behavior: "smooth" });
    }
  }, [monitorLogs, systemLines, autoScroll]);

  const copyLogs = () => {
    const text = tab === "system"
      ? systemLines.join("\n")
      : monitorLogs.map(e => `[${e.ts}] [${e.level}] ${e.branch ? `[${e.branch}] ` : ""}${e.message}`).join("\n");
    navigator.clipboard.writeText(text).catch(() => {});
  };

  const downloadLogs = () => {
    const text = tab === "system"
      ? systemLines.join("\n")
      : monitorLogs.map(e => `[${e.ts}] [${e.level}] ${e.branch ? `[${e.branch}] ` : ""}${e.message}`).join("\n");
    const blob = new Blob([text], { type: "text/plain" });
    const url = URL.createObjectURL(blob);
    const a = document.createElement("a");
    a.href = url;
    a.download = `tls-${tab}-logs-${new Date().toISOString().slice(0, 10)}.txt`;
    a.click();
    URL.revokeObjectURL(url);
  };

  return (
    <div className="p-6 space-y-5 max-w-7xl mx-auto">
      {/* Header */}
      <div className="flex items-center justify-between flex-wrap gap-3">
        <div className="flex items-center gap-3">
          <div className="w-10 h-10 rounded-xl bg-primary-500/10 flex items-center justify-center">
            <Terminal className="w-5 h-5 text-primary-400" />
          </div>
          <div>
            <h1 className="text-xl font-display font-bold text-white">Backend Logs</h1>
            <p className="text-sm text-gray-500">Live backend and monitoring logs</p>
          </div>
        </div>

        {/* Controls */}
        <div className="flex items-center gap-2 flex-wrap">
          {/* WS indicator */}
          <div className={`flex items-center gap-1.5 text-xs px-2 py-1 rounded-lg border ${connected ? "bg-green-500/10 border-green-500/20 text-green-400" : "bg-red-500/10 border-red-500/20 text-red-400"}`}>
            {connected ? <Wifi className="w-3 h-3" /> : <WifiOff className="w-3 h-3" />}
            {connected ? "Live" : "Offline"}
          </div>

          {/* Line count */}
          <select
            value={lineCount}
            onChange={(e) => setLineCount(Number(e.target.value) as LineCount)}
            className="bg-dark-700 border border-white/10 text-gray-300 text-sm rounded-lg px-2 py-1.5"
          >
            <option value={50}>50 lines</option>
            <option value={100}>100 lines</option>
            <option value={200}>200 lines</option>
            <option value={500}>500 lines</option>
          </select>

          {/* Auto-scroll */}
          <button
            onClick={() => setAutoScroll(!autoScroll)}
            className={`flex items-center gap-1.5 text-xs px-2 py-1.5 rounded-lg border transition-all ${autoScroll ? "bg-primary-500/10 border-primary-500/20 text-primary-400" : "bg-dark-700 border-white/10 text-gray-400"}`}
          >
            {autoScroll ? <ChevronDown className="w-3 h-3" /> : <ChevronUp className="w-3 h-3" />}
            Auto-scroll
          </button>

          {/* Auto-refresh (system tab only) */}
          {tab === "system" && (
            <button
              onClick={() => setAutoRefresh(!autoRefresh)}
              className={`flex items-center gap-1.5 text-xs px-2 py-1.5 rounded-lg border transition-all ${autoRefresh ? "bg-primary-500/10 border-primary-500/20 text-primary-400" : "bg-dark-700 border-white/10 text-gray-400"}`}
            >
              <Circle className={`w-2 h-2 ${autoRefresh ? "fill-primary-400" : "fill-gray-500"}`} />
              Auto-refresh
            </button>
          )}

          {/* Refresh */}
          <button
            onClick={tab === "system" ? fetchSystemLogs : fetchMonitorLogs}
            disabled={tab === "system" ? systemLoading : monitorLoading}
            className="btn-secondary flex items-center gap-1.5 text-xs px-2.5 py-1.5"
          >
            <RefreshCw className={`w-3.5 h-3.5 ${(tab === "system" ? systemLoading : monitorLoading) ? "animate-spin" : ""}`} />
            Refresh
          </button>

          {/* Download */}
          <button onClick={downloadLogs} className="btn-secondary flex items-center gap-1.5 text-xs px-2.5 py-1.5">
            <Download className="w-3.5 h-3.5" />
            Download
          </button>

          {/* Clear monitor logs */}
          {tab === "monitor" && (
            <button onClick={() => setMonitorLogs([])} className="btn-secondary flex items-center gap-1.5 text-xs px-2.5 py-1.5 text-red-400 border-red-500/20 hover:bg-red-500/10">
              <Trash2 className="w-3.5 h-3.5" />
              Clear
            </button>
          )}
        </div>
      </div>

      {/* Tabs */}
      <div className="flex gap-1 bg-dark-800 border border-white/5 rounded-xl p-1 w-fit">
        {([["system", "System Logs (journalctl)"], ["monitor", "Monitoring Logs (live)"]] as [Tab, string][]).map(([key, label]) => (
          <button
            key={key}
            onClick={() => setTab(key)}
            className={`px-4 py-1.5 rounded-lg text-sm font-medium transition-all ${tab === key ? "bg-primary-500/20 text-primary-400" : "text-gray-400 hover:text-white"}`}
          >
            {label}
          </button>
        ))}
      </div>

      {/* Log pane */}
      <div className="bg-dark-900 border border-white/5 rounded-2xl overflow-hidden">
        {/* Pane header */}
        <div className="flex items-center justify-between px-4 py-2.5 border-b border-white/5 bg-dark-800">
          <span className="text-xs text-gray-500 font-mono">
            {tab === "system"
              ? `${systemLines.length} lines${lastRefresh ? ` · refreshed ${lastRefresh.toLocaleTimeString()}` : ""}`
              : `${monitorLogs.length} entries · ${connected ? "live via WebSocket" : "WebSocket disconnected"}`}
          </span>
          <button onClick={copyLogs} className="text-xs text-gray-500 hover:text-gray-300 transition-colors">
            Copy all
          </button>
        </div>

        {/* Log output */}
        <div className="h-[60vh] overflow-y-auto font-mono text-xs p-3 space-y-0.5">
          {tab === "system" ? (
            systemLoading && systemLines.length === 0 ? (
              <div className="flex items-center justify-center h-full text-gray-500">
                <RefreshCw className="w-4 h-4 animate-spin mr-2" /> Loading system logs...
              </div>
            ) : systemLines.length === 0 ? (
              <div className="flex items-center justify-center h-full text-gray-600">No logs available</div>
            ) : (
              systemLines.map((line, i) => {
                const lvl = sysLogLevel(line);
                return (
                  <div key={i} className={`px-2 py-0.5 rounded border ${levelBg(lvl)} leading-relaxed`}>
                    <span className={`${levelColor(lvl)} break-all whitespace-pre-wrap`}>{line}</span>
                  </div>
                );
              })
            )
          ) : (
            monitorLoading && monitorLogs.length === 0 ? (
              <div className="flex items-center justify-center h-full text-gray-500">
                <RefreshCw className="w-4 h-4 animate-spin mr-2" /> Loading monitoring logs...
              </div>
            ) : monitorLogs.length === 0 ? (
              <div className="flex items-center justify-center h-full text-gray-600">
                No monitoring logs yet — start the scheduler to see activity here
              </div>
            ) : (
              monitorLogs.map((entry, i) => (
                <div key={i} className={`px-2 py-0.5 rounded border ${levelBg(entry.level)} leading-relaxed`}>
                  <span className="text-gray-600">{formatTs(entry.ts)} </span>
                  <span className={`font-semibold ${levelColor(entry.level)}`}>[{entry.level?.toUpperCase() || "INFO"}] </span>
                  {entry.branch && <span className="text-primary-400/70">[{entry.branch}] </span>}
                  <span className="text-gray-200 break-all whitespace-pre-wrap">{entry.message}</span>
                </div>
              ))
            )
          )}
          <div ref={logEndRef} />
        </div>
      </div>
    </div>
  );
}
