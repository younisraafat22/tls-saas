"use client";

import { useCallback, useEffect, useMemo, useState } from "react";
import { Mail, Reply, Search, CheckCircle2, MessageSquare, Languages, Trash2 } from "lucide-react";
import { adminApi } from "@/lib/api";
import { useLanguage } from "@/lib/i18n";

const labelsByLocale: Record<string, any> = {
  en: {
    title: "Support Inquiries",
    sub: "Messages received from website and desktop app users",
    search: "Search by name/email/subject",
    noData: "No inquiries found",
    replyTitle: "Reply to inquiry",
    replySubject: "Reply subject",
    replyMessage: "Reply message",
    closeAfter: "Close inquiry after reply",
    send: "Send reply",
    close: "Mark closed",
    source: "Source",
    language: "Language",
    status: "Status",
    from: "From",
  },
  ar: {
    title: "استفسارات الدعم",
    sub: "الرسائل الواردة من الموقع وتطبيق سطح المكتب",
    search: "ابحث بالاسم أو البريد أو الموضوع",
    noData: "لا توجد استفسارات",
    replyTitle: "الرد على الاستفسار",
    replySubject: "عنوان الرد",
    replyMessage: "نص الرد",
    closeAfter: "إغلاق الاستفسار بعد الرد",
    send: "إرسال الرد",
    close: "إغلاق",
    source: "المصدر",
    language: "اللغة",
    status: "الحالة",
    from: "من",
  },
  de: {
    title: "Support-Anfragen",
    sub: "Nachrichten von Website- und Desktop-App-Nutzern",
    search: "Suche nach Name/E-Mail/Betreff",
    noData: "Keine Anfragen gefunden",
    replyTitle: "Auf Anfrage antworten",
    replySubject: "Antwort-Betreff",
    replyMessage: "Antwortnachricht",
    closeAfter: "Nach Antwort schließen",
    send: "Antwort senden",
    close: "Schließen",
    source: "Quelle",
    language: "Sprache",
    status: "Status",
    from: "Von",
  },
};

export default function AdminInquiriesPage() {
  const { locale } = useLanguage();
  const L = labelsByLocale[locale] || labelsByLocale.en;

  const [items, setItems] = useState<any[]>([]);
  const [loading, setLoading] = useState(true);
  const [filter, setFilter] = useState("new");
  const [search, setSearch] = useState("");
  const [selected, setSelected] = useState<any | null>(null);
  const [replySubject, setReplySubject] = useState("");
  const [replyMessage, setReplyMessage] = useState("");
  const [closeAfterReply, setCloseAfterReply] = useState(true);
  const [sending, setSending] = useState(false);

  const load = useCallback(async () => {
    setLoading(true);
    try {
      const data = await adminApi.getInquiries(1, filter === "all" ? "" : filter, search);
      setItems(data?.items || []);
    } finally {
      setLoading(false);
    }
  }, [filter, search]);

  useEffect(() => { load(); }, [load]);

  useEffect(() => {
    const id = setInterval(() => {
      load();
    }, 15000);
    return () => clearInterval(id);
  }, [load]);

  const statusColor = (status: string) => {
    if (status === "new") return "text-amber-300 bg-amber-500/10";
    if (status === "replied") return "text-primary-300 bg-primary-500/10";
    return "text-accent-green bg-accent-green/10";
  };

  const selectInquiry = (row: any) => {
    setSelected(row);
    setReplySubject(`Re: ${row.subject || "Support request"}`);
    setReplyMessage("");
    setCloseAfterReply(true);
  };

  const sendReply = async () => {
    if (!selected || !replySubject.trim() || !replyMessage.trim()) return;
    setSending(true);
    try {
      await adminApi.replyInquiry(selected.id, {
        subject: replySubject.trim(),
        message: replyMessage.trim(),
        close_after_reply: closeAfterReply,
      });
      setSelected(null);
      await load();
    } finally {
      setSending(false);
    }
  };

  const closeInquiry = async (id: number) => {
    await adminApi.closeInquiry(id);
    if (selected?.id === id) setSelected(null);
    load();
  };

  const setInquiryStatus = async (id: number, status: "new" | "replied" | "closed") => {
    await adminApi.updateInquiryStatus(id, status);
    setItems((prev) => prev.map((i) => (i.id === id ? { ...i, status } : i)));
    if (selected?.id === id) setSelected((prev: any) => prev ? { ...prev, status } : prev);
  };

  const deleteInquiry = async (id: number) => {
    await adminApi.deleteInquiry(id);
    setItems((prev) => prev.filter((i) => i.id !== id));
    if (selected?.id === id) setSelected(null);
  };

  const counts = useMemo(() => ({
    all: items.length,
    new: items.filter((i) => i.status === "new").length,
    replied: items.filter((i) => i.status === "replied").length,
    closed: items.filter((i) => i.status === "closed").length,
  }), [items]);

  return (
    <div className="space-y-6">
      <div>
        <h1 className="text-2xl font-display font-bold flex items-center gap-2"><Mail className="w-6 h-6 text-primary-400" /> {L.title}</h1>
        <p className="text-gray-400 text-sm mt-1">{L.sub}</p>
      </div>

      <div className="glass-card p-3 flex flex-wrap gap-2 items-center">
        {[
          { key: "new", label: `New (${counts.new})` },
          { key: "replied", label: `Replied (${counts.replied})` },
          { key: "closed", label: `Closed (${counts.closed})` },
          { key: "all", label: `All (${counts.all})` },
        ].map((f) => (
          <button
            key={f.key}
            onClick={() => setFilter(f.key)}
            className={`px-3 py-1.5 rounded-lg text-sm ${filter === f.key ? "bg-primary-500/20 text-primary-300" : "text-gray-400 hover:text-white hover:bg-white/5"}`}
          >
            {f.label}
          </button>
        ))}
        <div className="ml-auto relative min-w-[240px] max-sm:w-full">
          <Search className="w-4 h-4 text-gray-500 absolute left-3 top-1/2 -translate-y-1/2" />
          <input
            value={search}
            onChange={(e) => setSearch(e.target.value)}
            placeholder={L.search}
            className="input-field pl-9 text-sm"
          />
        </div>
      </div>

      <div className="grid grid-cols-1 xl:grid-cols-5 gap-6">
        <div className="xl:col-span-2 glass-card overflow-hidden">
          {loading ? (
            <div className="p-8 text-center text-gray-400">Loading inquiries...</div>
          ) : items.length === 0 ? (
            <div className="p-8 text-center text-gray-500">{L.noData}</div>
          ) : (
            <div className="divide-y divide-white/5">
              {items.map((row) => (
                <button
                  key={row.id}
                  onClick={() => selectInquiry(row)}
                  className={`w-full text-left p-4 hover:bg-white/[0.03] transition ${selected?.id === row.id ? "bg-white/[0.04]" : ""}`}
                >
                  <div className="flex items-center justify-between gap-2">
                    <div className="font-semibold text-white truncate">{row.subject || "No subject"}</div>
                    <span className={`text-xs px-2 py-0.5 rounded-full ${statusColor(row.status)}`}>{row.status}</span>
                  </div>
                  <div className="text-sm text-gray-400 mt-1 truncate">{L.from}: {row.name} ({row.email})</div>
                  <div className="text-xs text-gray-500 mt-1">{new Date(row.created_at).toLocaleString()}</div>
                </button>
              ))}
            </div>
          )}
        </div>

        <div className="xl:col-span-3 glass-card p-5">
          {!selected ? (
            <div className="h-full min-h-[320px] text-gray-500 flex items-center justify-center text-center">
              <div>
                <MessageSquare className="w-8 h-8 mx-auto mb-2 text-gray-600" />
                Select an inquiry to view and reply
              </div>
            </div>
          ) : (
            <div className="space-y-4">
              <div className="flex items-center justify-between gap-3">
                <h2 className="text-lg font-semibold">{selected.subject || "No subject"}</h2>
                <div className="flex items-center gap-2">
                  <button onClick={() => setInquiryStatus(selected.id, "new")} className="text-xs px-2.5 py-1.5 rounded-lg bg-amber-500/15 text-amber-300 hover:bg-amber-500/25">New</button>
                  <button onClick={() => setInquiryStatus(selected.id, "replied")} className="text-xs px-2.5 py-1.5 rounded-lg bg-primary-500/15 text-primary-300 hover:bg-primary-500/25">Replied</button>
                  <button onClick={() => closeInquiry(selected.id)} className="text-xs px-2.5 py-1.5 rounded-lg bg-accent-green/15 text-accent-green hover:bg-accent-green/25 inline-flex items-center gap-1">
                    <CheckCircle2 className="w-3.5 h-3.5" /> {L.close}
                  </button>
                  <button onClick={() => deleteInquiry(selected.id)} className="text-xs px-2.5 py-1.5 rounded-lg bg-red-500/15 text-red-300 hover:bg-red-500/25 inline-flex items-center gap-1">
                    <Trash2 className="w-3.5 h-3.5" /> Delete
                  </button>
                </div>
              </div>
              <div className="text-sm text-gray-300">{L.from}: {selected.name} ({selected.email})</div>
              <div className="text-xs text-gray-500 flex items-center gap-4">
                <span className="inline-flex items-center gap-1"><Mail className="w-3.5 h-3.5" /> {L.source}: {selected.source}</span>
                <span className="inline-flex items-center gap-1"><Languages className="w-3.5 h-3.5" /> {L.language}: {selected.locale}</span>
              </div>
              <div className="p-3 rounded-xl bg-dark-900/60 border border-white/5 text-gray-200 whitespace-pre-wrap">
                {selected.message}
              </div>

              <div className="pt-2 border-t border-white/10 space-y-3">
                <h3 className="font-semibold text-primary-300 flex items-center gap-2"><Reply className="w-4 h-4" /> {L.replyTitle}</h3>
                <input
                  className="input-field"
                  value={replySubject}
                  onChange={(e) => setReplySubject(e.target.value)}
                  placeholder={L.replySubject}
                />
                <textarea
                  className="input-field min-h-[140px]"
                  value={replyMessage}
                  onChange={(e) => setReplyMessage(e.target.value)}
                  placeholder={L.replyMessage}
                />
                <label className="text-sm text-gray-300 inline-flex items-center gap-2 cursor-pointer">
                  <input type="checkbox" checked={closeAfterReply} onChange={(e) => setCloseAfterReply(e.target.checked)} />
                  {L.closeAfter}
                </label>
                <button
                  onClick={sendReply}
                  disabled={sending || !replySubject.trim() || !replyMessage.trim()}
                  className="btn-gradient px-4 py-2.5 text-sm inline-flex items-center gap-2 disabled:opacity-50"
                >
                  <Reply className="w-4 h-4" /> {sending ? "Sending..." : L.send}
                </button>
              </div>
            </div>
          )}
        </div>
      </div>
    </div>
  );
}

