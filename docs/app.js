"use strict";

// GitHub Pages veröffentlicht nur docs/, data/news.json liegt außerhalb. Auf Pages kommen die Daten
// deshalb direkt aus dem Repo (raw, CORS offen, max. 5 Minuten gecacht) – die Seite muss für neue
// Daten nie neu deployt werden. Lokal (Server im Repo-Root) wird zuerst ../data/news.json versucht.
// ?data=<url> überschreibt beides, zum Testen mit eigenen Datensätzen.
const RAW_URL = "https://raw.githubusercontent.com/dav1dsb/kaderkiosk/main/data/news.json";
const REFRESH_AFTER_MS = 5 * 60 * 1000;

const KATEGORIEN = [
  { id: "verletzung", label: "Verletzung", on: "#fff" },
  { id: "sperre", label: "Sperre", on: "#1C1A17" },
  { id: "aufstellung", label: "Aufstellung", on: "#fff" },
  { id: "pressekonferenz", label: "Pressekonferenz", on: "#1C1A17" },
  { id: "ergebnis", label: "Ergebnis", on: "#fff" },
  { id: "transfer", label: "Transfer", on: "#fff" },
];
const KATEGORIE_BY_ID = Object.fromEntries(KATEGORIEN.map((k) => [k.id, k]));

// Logos in docs/logos/<kürzel>.svg, von Wikimedia Commons (Lizenzen: docs/logos/QUELLEN.md). Vereine ohne
// frei lizenziertes aktuelles Logo bekommen das Kürzel in Vereinsfarben als Ersatz.
const LOGOS = new Set(["FCB", "BVB", "VFB", "TSG", "M05", "FCU", "BMG", "HSV", "KOE", "SVW", "S04", "SVE", "SCP"]);

// Namen wie in den Scrapern; Kürzel und Vereinsfarben (Haupt-, Nebenfarbe) für Streifen, Wappen und Sprungleiste.
const VEREINE = {
  "FC Bayern München": ["FCB", "#DC052D", "#0066B2"],
  "Borussia Dortmund": ["BVB", "#FDE100", "#000000"],
  "RB Leipzig": ["RBL", "#DD0741", "#001F47"],
  "VfB Stuttgart": ["VFB", "#E32219", "#FFFFFF"],
  "TSG Hoffenheim": ["TSG", "#1961B5", "#FFFFFF"],
  "Bayer 04 Leverkusen": ["B04", "#E32221", "#000000"],
  "SC Freiburg": ["SCF", "#D1001F", "#000000"],
  "Eintracht Frankfurt": ["SGE", "#000000", "#E1000F"],
  "FC Augsburg": ["FCA", "#BA3733", "#46714D"],
  "1. FSV Mainz 05": ["M05", "#C3141E", "#FFFFFF"],
  "1. FC Union Berlin": ["FCU", "#EB1923", "#FFFFFF"],
  "Borussia Mönchengladbach": ["BMG", "#000000", "#1B8B3A"],
  "Hamburger SV": ["HSV", "#0A3F86", "#000000"],
  "1. FC Köln": ["KOE", "#ED1C24", "#FFFFFF"],
  "SV Werder Bremen": ["SVW", "#1D9053", "#FFFFFF"],
  "FC Schalke 04": ["S04", "#004D9D", "#FFFFFF"],
  "SV 07 Elversberg": ["SVE", "#000000", "#FFFFFF"],
  "SC Paderborn 07": ["SCP", "#005CA9", "#000000"],
};
const OHNE_VEREIN = "Ohne Vereinszuordnung";

const state = { entries: [], filter: "alle", loadedAt: 0 };
const $ = (id) => document.getElementById(id);

function el(tag, attrs = {}, ...children) {
  const node = document.createElement(tag);
  for (const [key, value] of Object.entries(attrs)) {
    if (value === undefined || value === null || value === false) continue;
    if (key === "class") node.className = value;
    else if (key === "style") Object.assign(node.style, value);
    else if (key.startsWith("--")) node.style.setProperty(key, value);
    else node.setAttribute(key, value === true ? "" : value);
  }
  node.append(...children.filter((c) => c !== null && c !== undefined));
  return node;
}

// ---------- Daten ----------

function dataUrls() {
  const override = new URLSearchParams(location.search).get("data");
  if (override) return [override];
  if (location.hostname.endsWith("github.io")) return [RAW_URL];
  return ["../data/news.json", RAW_URL];
}

async function fetchEntries() {
  let lastError;
  for (const url of dataUrls()) {
    try {
      let res;
      try {
        res = await fetch(url, { cache: "no-store" });
      } catch {
        throw new Error("Keine Verbindung zum Server. Prüfe die Internetverbindung.");
      }
      if (!res.ok) throw new Error(`Der Server antwortet mit Fehler ${res.status}.`);
      const data = await res.json().catch(() => null);
      if (!Array.isArray(data)) throw new Error("Die Datei mit den Meldungen ist beschädigt.");
      return data.filter(isValid);
    } catch (err) {
      lastError = err;
    }
  }
  throw lastError;
}

function isValid(e) {
  return e && typeof e === "object" && typeof e.quelle === "string" && safeUrl(e.quelle)
    && !Number.isNaN(Date.parse(e.erfasst_am));
}

function safeUrl(value) {
  try {
    const url = new URL(value);
    return url.protocol === "https:" || url.protocol === "http:" ? url : null;
  } catch {
    return null;
  }
}

// ---------- Formatierung ----------

const DAY_MS = 24 * 60 * 60 * 1000;
const fmtTime = new Intl.DateTimeFormat("de-DE", { hour: "2-digit", minute: "2-digit" });
const fmtWeekday = new Intl.DateTimeFormat("de-DE", { weekday: "short", day: "2-digit", month: "2-digit" });
const fmtDate = new Intl.DateTimeFormat("de-DE", { day: "2-digit", month: "2-digit", year: "numeric" });

function when(date) {
  const startOfToday = new Date().setHours(0, 0, 0, 0);
  const t = date.getTime();
  if (t >= startOfToday) return `heute ${fmtTime.format(date)}`;
  if (t >= startOfToday - DAY_MS) return `gestern ${fmtTime.format(date)}`;
  if (t >= startOfToday - 6 * DAY_MS) return fmtWeekday.format(date).replace(",", "");
  return fmtDate.format(date);
}

function sourceLabel(url) {
  return url.hostname.replace(/^www\./, "");
}

// Die Scraper bauen die Beschreibung als "Überschrift – Teaser".
function splitBeschreibung(text) {
  const i = (text || "").indexOf(" – ");
  return i === -1 ? [text || "", ""] : [text.slice(0, i), text.slice(i + 3)];
}

function kategorieLabel(id) {
  if (KATEGORIE_BY_ID[id]) return KATEGORIE_BY_ID[id].label;
  return id ? id.charAt(0).toUpperCase() + id.slice(1) : "Sonstiges";
}

// ---------- Darstellung ----------

function renderChips() {
  const counts = {};
  for (const e of state.entries) counts[e.kategorie] = (counts[e.kategorie] || 0) + 1;

  const chip = (id, label, count, cat) => el("button", {
    type: "button",
    class: "chip",
    "aria-pressed": String(state.filter === id),
    disabled: count === 0 && state.filter !== id,
    "data-filter": id,
    "--cat": cat?.color,
    "--chip-on": cat?.on,
  },
    cat ? el("span", { class: "chip__swatch", "aria-hidden": "true" }) : null,
    el("span", {}, label),
    el("span", { class: "chip__count" }, String(count)),
  );

  $("chips").replaceChildren(
    chip("alle", "Alle", state.entries.length, null),
    ...KATEGORIEN.map((k) => chip(k.id, k.label, counts[k.id] || 0, { color: `var(--${k.id})`, on: k.on })),
  );
}

function groupByVerein(entries) {
  const groups = new Map();
  for (const e of entries) {
    const name = e.verein || OHNE_VEREIN;
    if (!groups.has(name)) groups.set(name, []);
    groups.get(name).push(e);
  }
  for (const list of groups.values()) list.sort((a, b) => Date.parse(b.erfasst_am) - Date.parse(a.erfasst_am));
  // Vereine mit der neuesten Meldung zuerst; Einträge ohne Verein immer ans Ende.
  return [...groups.entries()].sort(([na, a], [nb, b]) => {
    if (na === OHNE_VEREIN) return 1;
    if (nb === OHNE_VEREIN) return -1;
    return Date.parse(b[0].erfasst_am) - Date.parse(a[0].erfasst_am);
  });
}

function vereinStyle(name) {
  const [code, c1, c2] = VEREINE[name] || ["", "#8A8474", "#D9D3C6"];
  return { code, "--c1": c1, "--c2": c2 };
}

// Helle Vereinsfarben (BVB-Gelb, Weiß) brauchen dunkle Schrift auf dem Kürzel-Ersatz.
function textOn(hex) {
  const [r, g, b] = [1, 3, 5].map((i) => parseInt(hex.slice(i, i + 2), 16) / 255)
    .map((c) => (c <= 0.03928 ? c / 12.92 : ((c + 0.055) / 1.055) ** 2.4));
  return 0.2126 * r + 0.7152 * g + 0.0722 * b > 0.4 ? "#1C1A17" : "#FFFFFF";
}

function crest(name) {
  const { code, ...colors } = vereinStyle(name);
  if (LOGOS.has(code)) {
    return el("span", { class: "crest" },
      el("img", { src: `logos/${code.toLowerCase()}.svg`, alt: "", width: "32", height: "32", loading: "lazy", decoding: "async" }));
  }
  if (!code) return null;
  return el("span", { class: "crest crest--mono", "aria-hidden": "true", ...colors, "--crest-on": textOn(colors["--c1"]) }, code);
}

function slug(name) {
  return "v-" + name.toLowerCase().normalize("NFKD").replace(/[^\w]+/g, "-").replace(/^-|-$/g, "");
}

function renderItem(e) {
  const url = safeUrl(e.quelle);
  const [titel, teaser] = splitBeschreibung(e.beschreibung);
  const date = new Date(e.erfasst_am);
  const cat = KATEGORIE_BY_ID[e.kategorie];
  return el("li", { class: "item" },
    el("div", { class: "item__meta" },
      el("span", { class: "item__cat", "--cat": cat ? `var(--${cat.id})` : undefined }, kategorieLabel(e.kategorie)),
      e.status ? el("span", { class: "item__status" }, e.status) : null,
    ),
    el("p", { class: "item__title" }, e.spieler ? `${e.spieler}: ${titel}` : titel),
    teaser ? el("p", { class: "item__teaser" }, teaser) : null,
    el("p", { class: "item__foot" },
      el("a", { class: "item__source", href: url.href, target: "_blank", rel: "noopener noreferrer" }, sourceLabel(url)),
      el("time", { class: "item__time", datetime: date.toISOString(), title: date.toLocaleString("de-DE") }, when(date)),
    ),
  );
}

function renderSections() {
  const visible = state.filter === "alle"
    ? state.entries
    : state.entries.filter((e) => e.kategorie === state.filter);
  const groups = groupByVerein(visible);
  const notice = $("notice");
  const idle = $("idle");

  const sections = groups.map(([name, list]) => {
    const { code, ...colors } = vereinStyle(name);
    return el("section", { class: "club", id: slug(name), "aria-labelledby": slug(name) + "-h", ...colors },
      el("header", { class: "club__head" },
        crest(name),
        el("h2", { class: "club__name", id: slug(name) + "-h" }, name),
        el("span", { class: "club__count" }, list.length === 1 ? "1 Meldung" : `${list.length} Meldungen`),
      ),
      el("ul", { class: "items" }, ...list.map(renderItem)),
    );
  });
  $("sections").replaceChildren(...sections);

  // Sprungleiste nur mit mehreren Abschnitten sinnvoll.
  const nav = $("clubnav");
  const navLinks = groups.filter(([name]) => name !== OHNE_VEREIN).map(([name, list]) => {
    const { code } = vereinStyle(name);
    return el("a", { href: "#" + slug(name), title: name },
      crest(name),
      el("span", { class: "clubnav__code" }, code || name),
      el("span", { class: "clubnav__count" }, String(list.length)),
    );
  });
  nav.replaceChildren(...navLinks);
  nav.hidden = navLinks.length < 2;

  if (state.entries.length === 0) {
    showNotice("Noch keine Meldungen. Die Daten werden alle 15 Minuten aktualisiert.");
  } else if (visible.length === 0) {
    const label = kategorieLabel(state.filter);
    notice.replaceChildren(
      `Aktuell keine Meldungen zur Kategorie ${label}.`,
      el("button", { type: "button", "data-filter": "alle" }, "Alle Meldungen zeigen"),
    );
    notice.hidden = false;
  } else {
    notice.hidden = true;
  }

  // Vereine ohne aktuelle Meldungen kompakt statt als leere Abschnitte; im Filter nur als Zahl.
  const ohne = Object.keys(VEREINE).filter((name) => !groups.some(([n]) => n === name));
  if (ohne.length && visible.length) {
    if (state.filter === "alle") {
      idle.replaceChildren(el("strong", {}, "Ohne aktuelle Meldungen: "), ohne.join(", "));
    } else {
      const n = ohne.length === 1 ? "1 weiterer Verein" : `${ohne.length} weitere Vereine`;
      idle.replaceChildren(`${n} ohne Meldungen zur Kategorie ${kategorieLabel(state.filter)}.`);
    }
    idle.hidden = false;
  } else {
    idle.hidden = true;
  }
}

function renderStand() {
  const newest = state.entries.reduce((max, e) => Math.max(max, Date.parse(e.erfasst_am)), 0);
  $("stand").textContent = newest
    ? `Neueste Meldung: ${when(new Date(newest))}`
    : `Geladen: heute ${fmtTime.format(new Date(state.loadedAt))}`;
}

function showNotice(text, retry = false) {
  const notice = $("notice");
  notice.replaceChildren(text);
  if (retry) notice.append(el("button", { type: "button", id: "retry" }, "Erneut laden"));
  notice.hidden = false;
}

function render() {
  renderChips();
  renderSections();
  renderStand();
}

// ---------- Ablauf ----------

function filterFromHash() {
  const id = decodeURIComponent(location.hash.replace(/^#kategorie=/, ""));
  return location.hash.startsWith("#kategorie=") && (id === "alle" || KATEGORIE_BY_ID[id]) ? id : "alle";
}

function setFilter(id) {
  state.filter = id;
  history.replaceState(null, "", id === "alle" ? location.pathname + location.search : `#kategorie=${id}`);
  render();
}

async function load() {
  try {
    state.entries = await fetchEntries();
    state.loadedAt = Date.now();
    render();
  } catch (err) {
    $("stand").textContent = "Meldungen nicht geladen";
    if (!state.entries.length) {
      $("sections").replaceChildren();
      $("clubnav").hidden = true;
      $("idle").hidden = true;
      renderChips();
    }
    showNotice(`Die Meldungen konnten nicht geladen werden. ${err.message} `, true);
  }
}

document.addEventListener("click", (event) => {
  const target = event.target.closest("[data-filter], #retry");
  if (!target) return;
  if (target.id === "retry") load();
  else setFilter(target.dataset.filter);
});

// Vom Homescreen geöffnete Seiten bleiben oft lange im Speicher: beim Zurückkehren neu laden.
document.addEventListener("visibilitychange", () => {
  if (document.visibilityState === "visible" && Date.now() - state.loadedAt > REFRESH_AFTER_MS) load();
});

state.filter = filterFromHash();
$("heute").textContent = new Intl.DateTimeFormat("de-DE", { weekday: "long", day: "numeric", month: "long" }).format(new Date());
renderChips();
load();
