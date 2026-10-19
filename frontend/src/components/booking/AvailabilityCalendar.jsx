import { useEffect, useState } from "react";
import { ChevronLeft, ChevronRight } from "lucide-react";
import { api } from "@/lib/api";

const DAYS = ["Sen", "Sel", "Rab", "Kam", "Jum", "Sab", "Min"];
const pad = (n) => String(n).padStart(2, "0");
const todayStr = () => new Date().toISOString().slice(0, 10);

export function AvailabilityCalendar({ slug, value, onChange, refreshKey = 0, allowPast = false }) {
  const [cursor, setCursor] = useState(() => { const d = new Date(); return { y: d.getFullYear(), m: d.getMonth() }; });
  const [slots, setSlots] = useState([]);
  const month = `${cursor.y}-${pad(cursor.m + 1)}`;

  useEffect(() => {
    api.get(`/photographers/${slug}/availability?month=${month}`).then(setSlots).catch(() => setSlots([]));
  }, [slug, month, refreshKey]);

  const first = new Date(cursor.y, cursor.m, 1);
  const offset = (first.getDay() + 6) % 7;
  const total = new Date(cursor.y, cursor.m + 1, 0).getDate();
  const cells = [...Array(offset).fill(null), ...Array.from({ length: total }, (_, i) => i + 1)];
  const shift = (n) => setCursor(({ y, m }) => { const d = new Date(y, m + n, 1); return { y: d.getFullYear(), m: d.getMonth() }; });
  const daySlots = slots.filter((s) => s.date === value);

  return (
    <div className="cal" data-testid="availability-calendar">
      <div className="cal-head">
        <button type="button" onClick={() => shift(-1)} data-testid="calendar-prev-month"><ChevronLeft size={16} /></button>
        <b data-testid="calendar-month-label">{first.toLocaleDateString("id-ID", { month: "long", year: "numeric" })}</b>
        <button type="button" onClick={() => shift(1)} data-testid="calendar-next-month"><ChevronRight size={16} /></button>
      </div>
      <div className="cal-grid">
        {DAYS.map((d) => <span className="cal-dow" key={d}>{d}</span>)}
        {cells.map((d, i) => {
          if (!d) return <span key={`e${i}`} />;
          const ds = `${month}-${pad(d)}`;
          const busy = slots.filter((s) => s.date === ds);
          const full = busy.some((s) => s.start <= "00:00" && s.end >= "23:59");
          const past = !allowPast && ds < todayStr();
          const cls = ["cal-day", busy.length && "busy", full && "full", ds === value && "selected"].filter(Boolean).join(" ");
          return <button type="button" key={ds} className={cls} disabled={past} onClick={() => onChange(ds)} data-testid={`calendar-day-${ds}`}>{d}</button>;
        })}
      </div>
      <div className="cal-legend"><span><i className="dot free" /> Tersedia</span><span><i className="dot busy" /> Sebagian terisi</span><span><i className="dot full" /> Penuh</span></div>
      {value && (
        <div className="cal-slots" data-testid="calendar-day-slots">
          {daySlots.length ? daySlots.map((s, i) => <span key={i}>{s.type === "booked" ? "Terpesan" : "Diblokir"} {s.start}–{s.end}</span>) : <span className="free-text">Belum ada jadwal terisi di tanggal ini.</span>}
        </div>
      )}
    </div>
  );
}
