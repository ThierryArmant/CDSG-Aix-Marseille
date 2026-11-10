#!/usr/bin/env python3
"""
Veille web des classes défense (CDSG) — académie d'Aix-Marseille.

Pour une fiche (ou plusieurs), le script :
  1. cherche sur le web : classe défense, sorties, cérémonies, convention, unité marraine,
     articles de presse ; explore aussi le site de l'établissement s'il est renseigné ;
  2. lit les pages trouvées (et les liens donnés à la main) ;
  3. demande au modèle (Albert API ou autre service compatible OpenAI) d'en extraire
     chaque élément utile : sortie, cérémonie, convention, article, rapport, projet… ;
  4. range tout dans le dossier de la classe : classes/<identifiant>/veille.json
     (cumulatif : on ne perd rien d'une recherche à l'autre) ;
  5. met à jour data/recherche.js (résumé + « dernière sortie / convention / article »)
     que le site affiche et que l'assistant utilise pour répondre.

Bibliothèque standard uniquement (Python 3.9+).

Variables d'environnement :
  ALBERT_API_KEY   clé (obligatoire)
  API_BASE_URL     défaut https://albert.api.etalab.gouv.fr/v1 (Mistral : https://api.mistral.ai/v1)
  API_MODEL        facultatif

Exemples :
  python3 recherche/recherche_web.py --fiche college-jean-giono-orange
  python3 recherche/recherche_web.py --fiche college-jean-giono-orange --liens "https://…article1 https://…article2"
  python3 recherche/recherche_web.py --verifier
  python3 recherche/recherche_web.py --question "Quelle classe a fait la dernière sortie à la BA 115 ?"
"""
import argparse, datetime, html, json, os, re, sys, time, unicodedata
import urllib.parse, urllib.request
from html.parser import HTMLParser
from pathlib import Path

RACINE = Path(__file__).resolve().parent.parent
FICHIER_CLASSES = RACINE / "data" / "classes.js"
FICHIER_RESUME = RACINE / "data" / "recherche.js"
DOSSIER_CLASSES = RACINE / "classes"
UA = "Mozilla/5.0 (X11; Linux x86_64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/124 Safari/537.36"

BASE = os.environ.get("API_BASE_URL", "https://albert.api.etalab.gouv.fr/v1").rstrip("/")
CLE = os.environ.get("ALBERT_API_KEY") or os.environ.get("API_KEY")
MODELE = os.environ.get("API_MODEL", "") or ("openweight-large" if "etalab.gouv.fr" in BASE else "")
TYPES = ["sortie", "ceremonie", "convention", "article", "rapport", "projet", "partenaire", "autre"]
MOTS_DEFENSE = re.compile(r"d[ée]fense|cdsg|militaire|arm[ée]e|base a[ée]rienne|r[ée]giment|gendarmerie|pompier|marine|"
                          r"l[ée]gion|c[ée]r[ée]monie|comm[ée]mor|m[ée]moire|11 novembre|8 mai|rallye|trin[ôo]me|convention", re.I)


# ───────────────────────── fichiers ─────────────────────────
def slug(s):
    s = unicodedata.normalize("NFD", s.lower())
    s = "".join(c for c in s if unicodedata.category(c) != "Mn")
    return re.sub(r"[^a-z0-9]+", "-", s).strip("-")


def lire_classes():
    src = FICHIER_CLASSES.read_text(encoding="utf-8")
    debut = src.index("window.CDSG = [") + len("window.CDSG = ")
    bloc = src[debut:src.rindex("]") + 1]
    bloc = re.sub(r"(?m)^\s*//[^\n]*", "", bloc)
    try:
        classes = json.loads(bloc)
    except json.JSONDecodeError:
        bloc = re.sub(r'([{,]\s*)([a-zA-Z_]+)\s*:', r'\1"\2":', bloc)
        bloc = re.sub(r",\s*([}\]])", r"\1", bloc)
        classes = json.loads(bloc)
    for c in classes:
        c["id"] = c.get("id") or slug(c["etab"] + " " + c["ville"])
    return classes


def lire_resumes():
    if not FICHIER_RESUME.exists(): return {}
    m = re.search(r"window\.CDSG_WEB\s*=\s*(\{.*\});", FICHIER_RESUME.read_text(encoding="utf-8"), re.S)
    return json.loads(m.group(1)) if m else {}


def ecrire_resumes(r):
    FICHIER_RESUME.write_text(
        "// Résumés de la veille web — généré par recherche/recherche_web.py (détail : classes/<fiche>/veille.json)\n"
        "window.CDSG_WEB = " + json.dumps(r, ensure_ascii=False, indent=1) + ";\n", encoding="utf-8")


def lire_veille(cid):
    f = DOSSIER_CLASSES / cid / "veille.json"
    if f.exists():
        return json.loads(f.read_text(encoding="utf-8"))
    return {"fiche": cid, "elements": [], "recherches": []}


def ecrire_veille(cid, v):
    d = DOSSIER_CLASSES / cid
    d.mkdir(parents=True, exist_ok=True)
    (d / "veille.json").write_text(json.dumps(v, ensure_ascii=False, indent=1), encoding="utf-8")


# ───────────────────────── web ─────────────────────────
def http_get(url, timeout=15):
    req = urllib.request.Request(url, headers={"User-Agent": UA, "Accept-Language": "fr-FR,fr;q=0.9"})
    with urllib.request.urlopen(req, timeout=timeout) as r:
        brut = r.read(800_000)
        return brut.decode(r.headers.get_content_charset() or "utf-8", errors="replace"), r.geturl()


class Page(HTMLParser):
    def __init__(self):
        super().__init__(); self.txt = []; self.liens = []; self.skip = 0; self.titre = ""; self._t = False; self._a = None
    def handle_starttag(self, tag, a):
        a = dict(a)
        if tag in ("script", "style", "noscript", "svg"): self.skip += 1
        if tag == "title": self._t = True
        if tag == "a" and a.get("href"): self._a = [a["href"], ""]
    def handle_endtag(self, tag):
        if tag in ("script", "style", "noscript", "svg") and self.skip: self.skip -= 1
        if tag == "title": self._t = False
        if tag == "a" and self._a: self.liens.append(tuple(self._a)); self._a = None
    def handle_data(self, d):
        if self._t: self.titre += d.strip()
        if self._a is not None: self._a[1] += " " + d.strip()
        if not self.skip and d.strip(): self.txt.append(d.strip())


def lire_page(url, maxi=7000):
    try:
        brut, final = http_get(url)
        p = Page(); p.feed(brut)
        texte = re.sub(r"\s+", " ", " ".join(p.txt))
        liens = [(urllib.parse.urljoin(final, h), t.strip()) for h, t in p.liens]
        return {"url": final, "titre": p.titre[:200], "texte": texte[:maxi], "liens": liens}
    except Exception:
        return None


def recherche_web(requete, n=5):
    """DuckDuckGo (HTML puis version lite), sans clé."""
    trouves = []
    for base in ("https://html.duckduckgo.com/html/?", "https://lite.duckduckgo.com/lite/?"):
        try:
            page, _ = http_get(base + urllib.parse.urlencode({"q": requete, "kl": "fr-fr"}))
        except Exception:
            continue
        for l in re.findall(r'href="([^"]+)"', page):
            l = html.unescape(l)
            if "uddg=" in l:
                l = urllib.parse.unquote(urllib.parse.parse_qs(urllib.parse.urlparse(l).query).get("uddg", [l])[0])
            if l.startswith("http") and "duckduckgo" not in l and l not in trouves:
                trouves.append(l)
        if trouves: break
    return trouves[:n]


def explorer_site(site, maxi=6):
    """Pages du site de l'établissement qui parlent de défense, sorties, cérémonies…"""
    if not site: return []
    if not site.startswith("http"): site = "https://" + site
    accueil = lire_page(site)
    if not accueil: return []
    hote = urllib.parse.urlparse(accueil["url"]).netloc
    cand = []
    for u, t in accueil["liens"]:
        if urllib.parse.urlparse(u).netloc == hote and MOTS_DEFENSE.search(u + " " + t) and u not in cand:
            cand.append(u)
    return [accueil["url"]] + cand[:maxi]


# ───────────────────────── modèle ─────────────────────────
def api(chemin, corps=None):
    req = urllib.request.Request(BASE + chemin, method="POST" if corps else "GET",
        data=json.dumps(corps).encode() if corps else None,
        headers={"Authorization": "Bearer " + CLE, "Content-Type": "application/json"})
    with urllib.request.urlopen(req, timeout=180) as r:
        return json.loads(r.read())


def choisir_modele():
    global MODELE
    if MODELE: return MODELE
    ids = [m["id"] for m in api("/models").get("data", [])
           if not m.get("type") or re.search(r"text-generation|chat", m.get("type", ""))]
    for motif in (r"openweight-large", r"gpt-oss-120b", r"mistral-large", r"mistral-medium", r"large"):
        for i in ids:
            if re.search(motif, i, re.I): MODELE = i; return MODELE
    MODELE = ids[0]; return MODELE


def demander(systeme, utilisateur, jsonmode=True, max_tokens=1500):
    corps = {"model": choisir_modele(), "temperature": 0.1, "max_tokens": max_tokens,
             "messages": [{"role": "system", "content": systeme}, {"role": "user", "content": utilisateur}]}
    for essai in range(3):
        try:
            rep = api("/chat/completions", corps)["choices"][0]["message"]["content"]
            if not jsonmode: return rep
            m = re.search(r"\{.*\}", rep, re.S)
            return json.loads(m.group(0)) if m else None
        except Exception as e:
            print(f"   ! modèle : {e} — nouvel essai", file=sys.stderr); time.sleep(5 * (essai + 1))
    return None


SYSTEME_EXTRACTION = """Tu fais la veille d'une classe défense et sécurité globales (CDSG) de l'académie d'Aix-Marseille.
On te donne la fiche de la classe et le texte d'UNE page web.
Relève tout ce qui concerne la classe défense de CET établissement (pas un homonyme, pas un autre collège) :
sorties, visites de base ou de régiment, cérémonies (11 novembre, 8 mai…), signature ou renouvellement de convention,
unité marraine, rallye citoyen, concours, projets, articles de presse, rapports ou bilans, noms des professeurs référents.
N'invente rien : uniquement ce qui est écrit dans la page.
Réponds en JSON :
{"concerne": true|false,
 "elements": [
   {"type": "sortie|ceremonie|convention|article|rapport|projet|partenaire|autre",
    "date": "AAAA-MM-JJ, AAAA-MM ou AAAA (date de l'événement ; sinon de la publication) ou null",
    "titre": "titre court en français",
    "extrait": "courte citation exacte de la page (25 mots maximum)",
    "resume": "1 à 2 phrases en français avec les faits utiles (qui, quoi, où, avec quelle unité)"}],
 "referents": "noms de professeurs cités ou null",
 "unite": "unité marraine citée ou null"}"""


def analyser_page(c, page):
    fiche = {k: c.get(k) for k in ("etab", "ville", "dep", "ce", "ref", "unite", "conv")}
    r = demander(SYSTEME_EXTRACTION,
                 "Fiche :\n" + json.dumps(fiche, ensure_ascii=False) +
                 f"\n\nPage : {page['url']}\nTitre : {page['titre']}\n\n{page['texte']}")
    if not r or not r.get("concerne"): return None
    for e in r.get("elements", []):
        e["source"] = page["url"]; e["page"] = page["titre"]
        if e.get("type") not in TYPES: e["type"] = "autre"
        e["extrait"] = " ".join((e.get("extrait") or "").split()[:25])
    return r


def cle_element(e):
    return (e.get("source", ""), slug(e.get("titre", ""))[:60])


def date_tri(e):
    d = (e.get("date") or "0000")[:10]
    return d + "-00-00"[len(d) - 4:] if len(d) < 10 else d


def faire_resume(c, v):
    els = sorted(v["elements"], key=date_tri, reverse=True)
    derniers = {}
    for t in ("sortie", "ceremonie", "convention", "article", "rapport", "projet"):
        e = next((x for x in els if x["type"] == t), None)
        if e: derniers[t] = {k: e.get(k) for k in ("date", "titre", "resume", "source")}
    synthese = None
    if els:
        lignes = "\n".join(f"- [{e['type']}] {e.get('date') or '?'} — {e.get('titre')} : {e.get('resume')}" for e in els[:40])
        synthese = demander("Tu rédiges en français, en 3 phrases factuelles maximum, l'état de la classe défense "
                            "à partir des éléments de veille : activité la plus récente, partenaires, faits marquants. "
                            "N'invente rien. Réponds en texte simple.",
                            f"Classe : {c['etab']} ({c['ville']})\nÉléments :\n{lignes}", jsonmode=False, max_tokens=300)
    return {"date": datetime.date.today().strftime("%d/%m/%Y"),
            "resume": (synthese or "").strip(),
            "nb": len(els),
            "derniere_activite": els[0].get("date") if els else None,
            "derniers": derniers,
            "sources": list(dict.fromkeys(e["source"] for e in els))[:8]}


# ───────────────────────── traitement d'une fiche ─────────────────────────
def traiter_fiche(c, liens_manuels=(), profondeur=6):
    nom, ville = c["etab"], c["ville"]
    unite = c.get("unite") if c.get("unite") not in (None, "", "—") else ""
    requetes = [
        f'"{nom}" {ville} classe défense',
        f'{nom} {ville} CDSG',
        f'{nom} {ville} sortie {unite or "base militaire"}',
        f'{nom} {ville} cérémonie 11 novembre élèves',
        f'{nom} {ville} convention classe défense {unite}',
        f'{nom} {ville} classe défense La Provence OR Vaucluse Matin OR Dauphiné',
    ]
    urls = list(liens_manuels)
    for u in explorer_site(c.get("site")):
        if u not in urls: urls.append(u)
    for q in requetes:
        for u in recherche_web(q.strip()):
            if u not in urls: urls.append(u)
        time.sleep(1.2)
    v = lire_veille(c["id"])
    deja = {cle_element(e) for e in v["elements"]}
    vues = set(v.get("pages_lues", []))
    a_lire = [u for u in urls if u in liens_manuels or u not in vues][: profondeur + len(liens_manuels)]
    print(f"   {len(urls)} pages trouvées, {len(a_lire)} à lire")
    nouveaux = 0
    for u in a_lire:
        page = lire_page(u)
        vues.add(u)
        if not page or len(page["texte"]) < 200: continue
        if u not in liens_manuels and not (MOTS_DEFENSE.search(page["texte"]) and slug(nom.split()[-1]) in slug(page["texte"])):
            continue  # la page ne parle ni de défense ni de l'établissement
        r = analyser_page(c, page)
        if not r: continue
        for e in r.get("elements", []):
            e["trouve_le"] = datetime.date.today().isoformat()
            if cle_element(e) not in deja:
                v["elements"].append(e); deja.add(cle_element(e)); nouveaux += 1
        if r.get("referents"): v["referents_cites"] = r["referents"]
        if r.get("unite"): v["unite_citee"] = r["unite"]
    v["elements"].sort(key=date_tri, reverse=True)
    v["pages_lues"] = sorted(vues)
    v["recherches"].append({"date": datetime.date.today().isoformat(), "pages": len(a_lire), "nouveaux": nouveaux})
    v["fiche"] = c["id"]; v["etablissement"] = f"{nom} ({ville})"
    ecrire_veille(c["id"], v)
    print(f"   + {nouveaux} élément(s) nouveau(x), {len(v['elements'])} au total")
    return v


def question_libre(question, classes, resumes):
    lignes = []
    for c in classes:
        w = resumes.get(c["id"], {})
        der = "; ".join(f"dernier(e) {t}: {d.get('date')} {d.get('titre')}" for t, d in w.get("derniers", {}).items())
        lignes.append(f'[{c["id"]}] {c["etab"]} | {c["ville"]} | {c["dep"]} | {c["statut"]} | CE {c.get("ce")} | réf. {c.get("ref")} '
                      f'| unité {c.get("unite")} | conv. {c.get("conv")} | {c.get("note","")} | veille: {w.get("resume","")} {der}')
    print(demander("Tu réponds à un inspecteur sur le dossier des CDSG de l'académie d'Aix-Marseille, uniquement à partir des fiches. "
                   "Réponds en français, brièvement. Termine par une ligne 'FICHES: id1, id2'.",
                   "Fiches :\n" + "\n".join(lignes) + "\n\nQuestion : " + question, jsonmode=False) or "Pas de réponse.")


def main():
    ap = argparse.ArgumentParser(description="Veille web des CDSG")
    ap.add_argument("--fiche", help="identifiant d'une fiche (ex. college-jean-giono-orange)")
    ap.add_argument("--liens", default="", help="liens d'articles à lire en priorité (séparés par des espaces)")
    ap.add_argument("--statut", choices=["active", "dormante", "projet"])
    ap.add_argument("--verifier", action="store_true")
    ap.add_argument("--max", type=int, default=0)
    ap.add_argument("--profondeur", type=int, default=6, help="pages lues par fiche")
    ap.add_argument("--question")
    a = ap.parse_args()
    if not CLE:
        sys.exit("Clé absente : export ALBERT_API_KEY=\"…\" (ou secret GitHub ALBERT_API_KEY).")

    classes = lire_classes()
    resumes = lire_resumes()
    print(f"{len(classes)} fiches · {BASE} · modèle {choisir_modele()}")
    if a.question:
        question_libre(a.question, classes, resumes); return

    cible = [c for c in classes
             if (not a.fiche or c["id"] == a.fiche)
             and (not a.statut or c["statut"] == a.statut)
             and (not a.verifier or c.get("verifier"))]
    if a.fiche and not cible: sys.exit(f"Fiche inconnue : {a.fiche}")
    if a.max: cible = cible[:a.max]
    liens = [l for l in re.split(r"[\s,]+", a.liens) if l.startswith("http")]
    print(f"{len(cible)} fiche(s) à traiter")
    for i, c in enumerate(cible, 1):
        print(f"[{i}/{len(cible)}] {c['etab']} ({c['ville']})")
        v = traiter_fiche(c, liens if a.fiche else (), a.profondeur)
        resumes[c["id"]] = faire_resume(c, v)
        ecrire_resumes(resumes)
    print("Terminé.")


if __name__ == "__main__":
    main()
