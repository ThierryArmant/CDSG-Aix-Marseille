# Base documentaire CDSG — périmètre et état

Demandes de référence de Thierry, 15 novembre 2026.

## Périmètre demandé
- Mémento et vade-mecum CDSG ; textes officiels, conventions, création, fonctionnement, suivi.
- Vocabulaire militaire ; armes et armées ; corps, divisions, brigades, régiments, unités, bases, bâtiments et formations.
- Grades, galons, appellations et équivalences Terre, Air, Marine, gendarmerie et services.
- Unités et parrainages CDSG : France, outre-mer, académies, régions, départements, priorité Aix-Marseille et 13/84/04/05.
- Organisation territoriale : zones, autorités, DMD, points de contact ; coordonnées à vérifier au moment de la demande.
- Monter des projets : pédagogie, concours, prix, labels, aides financières, dons, mécénat, aides matérielles, transport, voyages.

## Trois niveaux effectivement installés
1. `data/memoire.json` : sept repères validés et datés, avec sources. Le modèle reçoit uniquement les entrées validées avec source et date. Aucun apprentissage automatique à partir de ses réponses.
2. `data/referentiel_sources.json` : 43 sources identifiées, par thème et mots-clefs. Les guides pertinents sont consultés avant la recherche générale. Pour un PDF, recherche de passages sur toutes les pages et restitution des numéros de pages. Une source inscrite au catalogue n’est pas pour autant intégralement dépouillée ni une donnée toujours actuelle.
3. `data/opportunites.json` : vingt-trois dispositifs ou pistes, avec porteur, périmètre, source et état de vérification. Les montants et échéances sont volontairement non figés. Les prix ne sont pas tous des aides financières.

Les fiches et conventions du dossier restent distinctes de la documentation nationale. Une unité militaire implantée dans une commune n’est pas automatiquement une unité marraine. Une liste de lieux ne permet pas de compter toutes les unités.

## Couverture réelle et travail restant
- Le vade-mecum DSNJ 2022 est identifié ; le mémento exact évoqué par Thierry devra être rapproché de cette édition ou d’une autre version. Ne pas prétendre avoir chargé une édition non obtenue.
- Les textes officiels sont des sources consultables avec leur version ; un guide ne remplace pas un texte en vigueur.
- Le catalogue donne accès aux annuaires institutionnels Terre, Air et Marine et à celui des DMD. Ce n’est pas encore une base exhaustive de chaque unité et de chaque parrainage de France.
- Le répertoire national des parrainages reste à construire par preuve : établissement, UAI si disponible, académie, département, unité, armée/service, implantation de l’unité, date de convention, statut, source et date de vérification.
- Les aides locales, fondations, associations et concours supplémentaires sont à compléter territoire par territoire et session par session.
- Pour un dispositif : porteur, public, nature d’aide, dépenses éligibles, territoire, montant/plafond si vérifié, calendrier, dossier, contact, possibilités de cumul et dernière vérification.
- Les planches des galons sont des sources visuelles : ne pas prétendre reconnaître un insigne à partir du seul texte extrait.

## Contrôles et limites
Tests : filtrage de la mémoire non validée, orientation vers les guides, lecture d’une page PDF lointaine, recherche question, absence de clé, erreurs, doublons et citations issues réellement de la page.
La mémoire est une base documentaire consultée, pas un réentraînement d’Albert ni la garantie de réponses infaillibles. Les coordonnées, responsables, rattachements et appels annuels doivent être recontrôlés sur leurs sources.


## Coordination documentaire Albert

Albert prépare les requêtes, reçoit les pages de ses outils web et les fiches de la bibliothèque, puis examine les lacunes et contradictions. Une seconde vague ciblée est possible (3 requêtes et 4 pages supplémentaires maximum ; première vague : 8 pages). La réponse relie les fiches concernées et les sources numérotées. La trace des requêtes, lacunes et pages consultées est conservée dans le résultat, sans raisonnement interne ni secret. Les fiches ne sont pas réécrites par une simple question.

Le paramètre max_tokens de la réponse finale est fixé à 12 000 : plafond de sortie, pas budget global de toute la recherche ni taille garantie du contexte. La réponse reste concise. Ce réglage doit être accepté par le modèle configuré. Les moteurs web sont des outils orchestrés par Albert, pas des agents autonomes distincts. Les vérifications automatisées locales couvrent la transmission d’une lacune, le retour des preuves et le lien vers la fiche ; une vérification en service reste nécessaire après publication.
