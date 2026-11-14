# Dépendances des ressources et détection des ruptures

Le **graphe de dépendances** enregistre la façon dont vos ressources se référencent les unes les
autres — un sprite est une image *de* l'animation, un sprite est le fichier image source *du* tileset, un
tileset est utilisé *par* une tilemap — et l'**indicateur de rupture** vous avertit passivement
quand la modification d'une ressource en casserait une autre qui pointe vers elle. Les deux sont
accessibles depuis le menu **Bibliothèque**, à côté des panneaux de la
[bibliothèque de ressources](asset-library.md) sur lesquels ils s'appuient.

> **Ce qu'est une dépendance.** Une dépendance est une **référence orientée** d'une ressource du
> catalogue vers une autre : la ressource *qui référence* (la source) pointe vers la ressource
> *référencée* (la cible). La référence mémorise aussi le contenu de la cible au moment où elle a
> été créée, afin que la bibliothèque puisse savoir plus tard si la cible a changé. Les
> dépendances forment un **graphe orienté acyclique** — la bibliothèque refuse d'enregistrer une
> référence qui créerait un cycle (une ressource ne peut pas, directement ou transitivement,
> finir par dépendre d'elle-même).

## Ouvrir le graphe de dépendances

Le menu **Bibliothèque** comporte aussi un commutateur de panneau **Graphe des dépendances**. La vue
**Graphe des dépendances** visualise les références pour l'ensemble du catalogue ou pour la seule
ressource actuellement sélectionnée dans le panneau
[Bibliothèque de ressources](asset-library.md), dans deux directions :

| Relation | Se lit | Affiche |
| --- | --- | --- |
| **Dépendances (dépend de)** | ce que cette ressource *référence* | les ressources vers lesquelles pointe la ressource sélectionnée |
| **Dépendants (référencés par)** | ce qui *référence* cette ressource | les ressources qui pointent vers la ressource sélectionnée |

Les deux relations sont affichées sous forme de listes stables, triées par ordre alphabétique. Par
défaut, la vue montre les voisins **directs** ; les mêmes relations peuvent se lire de façon
transitive (la chaîne complète — par exemple toutes les ressources sur lesquelles une tilemap
s'appuie en définitive, via ses tilesets et leurs sprites sources).

> **Pourquoi le graphe ne se bloque jamais.** Comme le graphe stocké est toujours acyclique, la
> vue ne liste que les voisins directs que renvoie le modèle — elle n'effectue elle-même aucun
> parcours récursif. Même un ensemble de références délibérément enchevêtrées ne peut pas la faire
> tourner en boucle : un cycle est détecté au moment où la référence est enregistrée et signalé
> clairement, et une chaîne très profonde est bornée plutôt que suivie indéfiniment.

## L'indicateur de rupture passif

Lorsque vous modifiez une ressource, tout ce qui la référence peut désormais pointer vers un
contenu qui ne correspond plus. La bibliothèque l'indique **passivement** — elle signale le
problème, elle ne **bloque pas** votre modification :

- **Les ruptures sont signalées, jamais bloquées.** Vous pouvez toujours effectuer la
  modification ; l'indicateur vous indique simplement qu'une référence est désormais rompue pour
  que vous décidiez quoi faire. Rien n'est empêché, et aucune boîte de dialogue modale ne vous
  interrompt.
- **Il se rafraîchit à chaque changement du catalogue.** L'indicateur se réévalue chaque fois que
  le catalogue ou le graphe change, si bien qu'il reflète toujours l'état actuel — vous n'avez
  jamais à lui demander de revérifier.
- **Il s'affiche sur place.** La vue Graphe des dépendances montre un résumé des ruptures et
  l'état de chaque référence, et la liste de la [Bibliothèque de ressources](asset-library.md)
  comporte une colonne **Statut**, si bien qu'une ressource rompue est visible là où vous
  parcourez le catalogue.

Une référence est signalée comme rompue pour l'une de deux raisons :

| Raison | Signification |
| --- | --- |
| **cible manquante** | la ressource référencée n'est plus dans le catalogue (elle a été supprimée). Le graphe des dépendances l'affiche comme « Rompues (cible manquante) ». |
| **cible modifiée** | la ressource référencée est toujours présente, mais son contenu a changé depuis la création de la référence. Le graphe des dépendances l'affiche comme « Rompues (cible modifiée) ». |

Une ressource dont toutes les références sont encore valides n'affiche aucun indicateur ; seule une
référence réellement rompue est signalée, de sorte que l'avertissement reste significatif (aucun
faux positif).

## Accessibilité, thèmes et langue

Chaque contrôle de la vue Graphe des dépendances porte un nom accessible et s'utilise au clavier, chaque libellé peut être entièrement traduit, et la vue ainsi que la colonne Statut s'affichent
correctement dans les thèmes clair et sombre.

## Voir aussi

Le suivi des dépendances et la détection des ruptures s'appuient sur le catalogue de la
[bibliothèque de ressources](asset-library.md). La fonctionnalité complémentaire — un **historique
des versions** en ajout seul pour chaque ressource, ainsi que la **réutilisation entre projets**,
l'**exportation / importation** et un **stockage cloud facultatif** (non connecté dans cette
version) — est documentée dans
[Versionnage des ressources et réutilisation entre projets](asset-versioning.md). Une ressource
réutilisée est une référence comme une autre : l'indicateur de rupture décrit ici signale donc une
réutilisation dont la cible disparaît ou change par la suite.
