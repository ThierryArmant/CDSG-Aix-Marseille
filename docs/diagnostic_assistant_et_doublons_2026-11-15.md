# Assistant et doublons — 15 novembre 2026

## Branchement
Capture utilisateur : Failed to fetch sur le bouton Chercher. Prérequête OPTIONS de l’API Albert : HTTP 405 sans autorisation CORS. En revanche, journal du traitement serveur du 15 novembre : connexion au modèle OK.
Autre défaut : restauration de la session animateur exécutée avant l’initialisation du champ jeton, puis jeton écrasé par la valeur locale. Restauration déplacée après initialisation.
Chercher passe maintenant par le serveur si l’accès est connecté. Un bouton Connecter l’IA réutilise l’accès animateur existant. Sans connexion, le blocage est explicite ; aucune réponse IA simulée par mots-clés. Les clés Albert restent dans les secrets GitHub. Les traitements en échec produisent un résultat explicite et le suivi peut détecter un workflow échoué.

## Essai réel
Diagnostic exécuté avec les clés du dépôt et la question de l’utilisateur sur les unités militaires du Vaucluse. Première exécution : réponse générée avec sept sources, mais total fondé sur un annuaire synthétique de lieux : résultat non retenu. Correction : exclusion des pages de l’annuaire Exa des preuves, sources institutionnelles prioritaires, consigne de ne pas transformer une liste de lieux en total exhaustif. Le second diagnostic vérifie le circuit corrigé.
La question interactive n’exécute plus la veille complète de chaque fiche : cela réduisait fortement sa réactivité. Ses sources restent jointes à la réponse. L’enrichissement reste assuré par les actions dédiées et la veille nocturne.

## Répétitions
La photographie générale d’une page était attribuée à tous les événements extraits. La revue de presse créait ensuite une carte pour chacun : un même article apparaissait plusieurs fois.
Correction : une carte par article, sans supprimer les différents événements de la chronologie ; une même image affichée une seule fois dans la liste ; images automatiques communes à plusieurs établissements masquées sur les fiches, photos choisies manuellement préservées. Les variantes typographiques d’un même prix sont regroupées en conservant les sources. Les rangs différents, dates différentes et événements distincts restent séparés.
Protection de l’extraction : les citations doivent être retrouvées dans le texte de la page ; une date de convention copiée de la fiche ne constitue plus une preuve externe.

## Mesure avant/après sur les dossiers présents
- Cartes de revue de presse : 466 vers 228, par regroupement des cartes d’une même page.
- Occurrences d’images dans ces cartes : 370 vers 147.
- Événements : 827 enregistrements source conservés ; 824 éléments distincts à l’affichage.
- Distinctions des résumés : 56 vers 54 ; variantes de deux prix regroupées.
Ces nombres ne constituent pas une validation historique de toutes les données collectées. Aucun dossier de veille original effacé par ce passage.

## Vérifications
Cinq tests Python et six tests JavaScript : serveur, session, absence de clé, erreurs explicites, périmètre de recherche, refus des citations de fiche non présentes dans la page, doublons typographiques, rangs/dates distincts, regroupement des articles et photos manuelles. Syntaxes Python et JavaScript vérifiées.
