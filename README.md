# CDSG — Académie d'Aix-Marseille

Dossier des Classes Défense et Sécurité Globales : classes actives, en sommeil et en projet,
avec pour chacune l'établissement, le chef d'établissement, les professeurs référents et l'unité marraine.

Site : https://thierryarmant.github.io/CDSG-Aix-Marseille/

## Contenu du dépôt

| Fichier | Rôle |
|---|---|
| `index.html` | Page de présentation, synthèse, assistant de questions, fiches |
| `data/classes.js` | **Les fiches** (une ligne par classe) — c'est ici qu'on met à jour |
| `data/recherche.js` | Compléments trouvés sur le web (généré automatiquement) |
| `recherche/recherche_web.py` | Script de recherche web + extraction par le modèle |
| `.github/workflows/recherche.yml` | Lance la recherche depuis l'onglet **Actions** |

## Mise en ligne (une seule fois)

1. Déposer tous les fichiers à la racine du dépôt `CDSG-Aix-Marseille` (garder les dossiers `data/`, `recherche/`, `.github/`).
2. **Settings → Pages** : Source = *Deploy from a branch*, branche `main`, dossier `/ (root)`.
3. **Settings → Secrets and variables → Actions → New repository secret** :
   nom `ALBERT_API_KEY`, valeur = la clé Albert. La clé ne doit **jamais** être écrite dans un fichier du dépôt.

## Compléter les fiches par recherche web

Onglet **Actions → Recherche web → Run workflow**, puis choisir :
- `verifier` : seulement les classes « à vérifier » (conseillé pour commencer) ;
- `dormante`, `projet`, `active` ou `toutes`.

Le résultat est enregistré dans `data/recherche.js` et apparaît dans chaque fiche (encadré « Compléments trouvés en ligne »).
Ces compléments sont à confirmer auprès des établissements avant d'être reportés dans `data/classes.js`.

En local :
```bash
export ALBERT_API_KEY="..."
python3 recherche/recherche_web.py --verifier
python3 recherche/recherche_web.py --fiche lycee-thiers-marseille
python3 recherche/recherche_web.py --question "Quelles classes n'ont pas d'unité marraine ?"
```
Autre fournisseur compatible : `export API_BASE_URL=https://api.mistral.ai/v1` (et sa clé dans `ALBERT_API_KEY`).

## Poser des questions sur le site

- **Sans clé** : la recherche par mots-clés retrouve les fiches (ville, établissement, nom, unité, statut, département) et ouvre la bonne fiche.
- **Avec clé** : dans « Réglages du service de réponse », coller la clé une fois ; elle reste dans le navigateur de la personne, jamais sur le site. Les réponses sont alors rédigées et renvoient vers les fiches.

## Mettre à jour une fiche

Dans `data/classes.js`, modifier la ligne de l'établissement. Champs :
`dep`, `etab`, `ville`, `ce` (chef d'établissement), `ref` (référents), `unite`, `conv` (convention),
`statut` (`active` / `dormante` / `projet`), `verifier` (`true` si à confirmer), `suivi` (formateur), `note`.
