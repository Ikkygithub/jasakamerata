import { useEffect, useState } from "react";
import { useLocation } from "react-router-dom";
import { Search, LayoutGrid, List } from "lucide-react";
import { api } from "@/lib/api";
import { CATEGORIES } from "@/lib/data";
import { Header, Footer } from "@/components/layout/Header";
import { PhotographerCard } from "@/components/marketplace/Cards";

export default function SearchPage() {
  const params = new URLSearchParams(useLocation().search);
  const [people, setPeople] = useState([]);
  const [mode, setMode] = useState("list");
  const [cat, setCat] = useState(params.get("category") || "");
  const [search, setSearch] = useState(params.get("search") || "");
  const [sort, setSort] = useState("relevan");

  useEffect(() => {
    api.get(`/photographers?category=${cat}&search=${encodeURIComponent(search)}&sort=${sort}`).then(setPeople).catch(() => setPeople([]));
  }, [cat, search, sort]);

  return (
    <>
      <Header />
      <main className="search-page">
        <div className="page-intro"><p className="eyebrow">JELAJAHI PORTOFOLIO</p><h1>Fotografer di Makassar.</h1><p>Pilih partner visual yang paling sesuai dengan cerita dan kebutuhanmu.</p></div>
        <div className="filterbar">
          <div className="search-small"><Search size={17} /><input value={search} onChange={(e) => setSearch(e.target.value)} placeholder="Cari nama atau kategori" data-testid="search-input" /></div>
          <select value={cat} onChange={(e) => setCat(e.target.value)} data-testid="category-filter"><option value="">Semua kategori</option>{CATEGORIES.map((c) => <option key={c.name}>{c.name}</option>)}</select>
          <select value={sort} onChange={(e) => setSort(e.target.value)} data-testid="sort-select"><option value="relevan">Paling relevan</option><option value="harga-rendah">Harga terendah</option><option value="rating">Rating tertinggi</option></select>
          <div className="view-switch">
            <button className={mode === "list" ? "active" : ""} onClick={() => setMode("list")} data-testid="list-view-button"><List size={17} /></button>
            <button className={mode === "grid" ? "active" : ""} onClick={() => setMode("grid")} data-testid="grid-view-button"><LayoutGrid size={17} /></button>
          </div>
        </div>
        <p className="result-count" data-testid="result-count">{people.length} fotografer ditemukan</p>
        <div className={mode === "grid" ? "results grid-results" : "results"}>{people.map((p) => <PhotographerCard key={p.photographer_id} p={p} />)}</div>
        {!people.length && <div className="empty"><p>Belum ada fotografer yang sesuai.</p><button className="outline-btn" onClick={() => { setCat(""); setSearch(""); }} data-testid="reset-search">Reset pencarian</button></div>}
      </main>
      <Footer />
    </>
  );
}
