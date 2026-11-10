# CDSG — Académie d'Aix-Marseille

Dossier des Classes Défense et Sécurité Globales : classes actives, en sommeil et en projet,
avec pour chacune l'établissement, le chef d'établissement, les professeurs référents et l'unité marraine.

Site : https://thierryarmant.github.io/CDSG-Aix-Marseille/

## Contenu du dépôt

| Fichier | Rôle |
|---|---|
| `index.html` | Page de présentation, synthèse, assistant de questions, fiches |
| `data/classes.js` | **Les fiches** (une ligne par classe) — c'est ici qu'on met à jour |
| `data/recherche.js` | Résumés de la veille (générés automatiquement) |
| `classes/<fiche>/veille.json` | Dossier de chaque classe : tout ce qui a été trouvé en ligne |
| `recherche/recherche_web.py` | Script de recherche web + extraction par le modèle |
| `.github/workflows/recherche.yml` | Lance la recherche depuis l'onglet **Actions** |

## Mise en ligne (une seule fois)

1. Déposer tous les fichiers à la racine du dépôt `CDSG-Aix-Marseille` (garder les dossiers `data/`, `recherche/`, `.github/`).
2. **Settings → Pages** : Source = *Deploy from a branch*, branche `main`, dossier `/ (root)`.
3. **Settings → Secrets and variables → Actions → New repository secret** :
   nom `ALBERT_API_KEY`, valeur = la clé Albert. La clé ne doit **jamais** être écrite dans un fichier du dépôt.

## Veille en ligne : le dossier de chaque classe

Chaque classe a son dossier `classes/<identifiant>/veille.json`. On y trouve, cumulés d'une recherche à l'autre, les
sorties, cérémonies, conventions, articles et rapports trouvés en ligne, avec la date, un court extrait et la source.
Les **Observations** de la fiche et les encadrés « Dernière sortie / convention / article » en sont tirés.

- **Depuis une fiche** : bouton **Chercher en ligne** (on peut coller des liens d'articles à lire en priorité). Résultat en 3 à 6 minutes.
- **Pour plusieurs fiches** : onglet **Actions → Recherche web → Run workflow** (`verifier`, `dormante`, `projet`, `active`, `toutes`).

Modèle utilisé par défaut avec Albert : `openweight-large`. Pour en changer : Settings → Secrets and variables → Actions → onglet *Variables* → `API_MODEL`.

En local :
```bash
export ALBERT_API_KEY="..."
python3 recherche/recherche_web.py --fiche college-jean-giono-orange --liens "https://..."
python3 recherche/recherche_web.py --question "Quelle est la dernière sortie de la classe de Sault ?"
```

## Jeton GitHub (pour modifier les fiches et lancer les recherches depuis le site)

github.com → Settings → Developer settings → Personal access tokens → **Fine-grained tokens** → Generate new token :
dépôt `cdsg-aix-marseille` uniquement ; permissions **Contents : Read and write** et **Actions : Read and write**.
Le coller dans le site (au-dessus des fiches). Il reste dans le navigateur.

## Mettre à jour une fiche

Dans `data/classes.js`, modifier la ligne de l'établissement. Champs :
`dep`, `etab`, `ville`, `ce` (chef d'établissement), `ref` (référents), `unite`, `conv` (convention),
`statut` (`active` / `dormante` / `projet`), `verifier` (`true` si à confirmer), `suivi` (formateur), `site` (site de l'établissement, aide la recherche), `note` (notes de suivi).
Le plus simple : bouton **Modifier la fiche** sur le site.
