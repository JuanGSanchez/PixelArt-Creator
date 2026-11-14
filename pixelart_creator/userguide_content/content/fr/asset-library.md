# La bibliothèque de ressources : parcourir, étiqueter et rechercher

La **bibliothèque de ressources** est un catalogue, à l'échelle du studio, de vos ressources
réutilisables — sprites, animations, tilesets, tilemaps et palettes — réunies au même endroit.
Inscrivez les entités que vous avez déjà créées comme **ressources nommées**, organisez-les avec
des **étiquettes** libres, et retrouvez rapidement la bonne grâce à la **recherche et au filtre**.
La bibliothèque et ses trois panneaux sont accessibles depuis le menu **Bibliothèque**.

> **Ce qu'est une ressource.** Une ressource est une **entrée de catalogue** qui *référence* l'une
> des entités que vous avez déjà créées — elle ne fait pas une seconde copie de votre œuvre.
> Chaque entrée porte un **identifiant stable**, un **type** (sprite, animation, tileset, tilemap
> ou palette), un **nom** d'affichage, ses **étiquettes** et quelques métadonnées. L'entrée pointe
> vers la forme enregistrée canonique de l'entité (les mêmes données `.pixproj` que celles
> utilisées par le reste de l'application) — la bibliothèque n'ajoute aucun nouveau format
> d'enregistrement pour l'œuvre elle-même.

## Ouvrir la bibliothèque

Le menu **Bibliothèque** comporte un commutateur de panneau pour chacun de ces trois panneaux,
qui affiche ou masque un panneau :

| Entrée de menu | Panneau | À quoi il sert |
| --- | --- | --- |
| **Bibliothèque de ressources** | la liste du catalogue | Parcourir chaque ressource par nom, type et étiquettes. |
| **Recherche de ressources** | les contrôles de recherche / de filtre | Restreindre la liste par nom, étiquette et/ou type. |
| **Étiquetage des ressources** | l'éditeur d'étiquettes | Ajouter et retirer des étiquettes sur la ressource sélectionnée. |

Chaque entrée est un commutateur de panneau ordinaire (comme pour les autres panneaux de flux de
travail de l'application), de sorte que vous pouvez agencer les trois panneaux à votre guise. Les
panneaux partagent **un seul** catalogue en mémoire : une modification faite dans un panneau est
donc immédiatement reflétée dans les autres.

## Inscrire une ressource

Pour que quoi que ce soit apparaisse dans le catalogue, il faut d'abord l'**inscrire**. Trois
endroits de l'application lancent une inscription, et tous trois aboutissent à la même invite
**Inscrire une ressource**, partagée :

- **Inscrire le document actif**, dans le menu **Bibliothèque**, inscrit le document ouvert dans
  l'onglet actif. Inscrire plus tard le même document ajoute une nouvelle révision à son entrée
  de catalogue existante au lieu de créer un doublon — voir
  [Versionnage des ressources et réutilisation entre projets](asset-versioning.md).
- **Inscrire la sélection**, également dans le menu **Bibliothèque**, n'inscrit que les pixels
  situés dans votre sélection actuelle. Pour une sélection non rectangulaire, tout ce qui se
  trouve hors des pixels sélectionnés est transparent dans la ressource inscrite. Sans sélection,
  il n'y a rien à inscrire.
- **Ajouter aussi à la bibliothèque de ressources**, une case à cocher de la boîte de dialogue
  d'exportation (voir [Exportation et intégration au pipeline](export-and-pipeline.md)), inscrit
  le fichier exporté au cours de la même opération que l'exportation.

Tous trois ouvrent la même boîte de dialogue **Inscrire une ressource**, qui demande :

| Champ | Ce qu'il demande |
| --- | --- |
| **Nom** | Un nom d'affichage pour la nouvelle entrée de catalogue. |
| **Type** | L'un des cinq types de ressource — Sprite, Animation, Tileset, Tilemap, Palette. |
| **Étiquettes** | Un ensemble facultatif d'étiquettes séparées par des virgules, contrôlé selon les mêmes plafonds de longueur et de nombre que le panneau d'étiquetage ci-dessous. |

La boîte de dialogue valide au fur et à mesure de la saisie : un nom vide, ou un ensemble
d'étiquettes qui dépasse les plafonds de longueur / de nombre, désactive le bouton **Inscrire** et
affiche une raison claire jusqu'à ce que vous corrigiez. Annuler la boîte de dialogue n'inscrit
rien.

## Importer ou exporter une seule ressource

Deux autres commandes du menu **Bibliothèque** déplacent un seul fichier de ressource, à la
différence d'un projet entier :

- **Exporter une ressource** exporte l'entrée de catalogue actuellement sélectionnée — ou, si rien
  n'est sélectionné, chaque entrée du catalogue ouvert — sous la forme d'un fichier importable
  unique.
- **Importer une ressource** relit un tel fichier dans la bibliothèque ouverte, en le fusionnant
  dans le catalogue.

Elles sont distinctes des commandes **Exporter un paquet de projet** / **Importer un paquet de
projet**, qui déplacent un projet entier avec tout ce qu'il référence — voir
[Versionnage des ressources et réutilisation entre projets](asset-versioning.md).

## Parcourir le catalogue

Le panneau **Bibliothèque de ressources** liste le catalogue en quatre colonnes — **Nom**,
**Type**, **Étiquettes** et **Statut**. Il montre toujours exactement ce que contient le
catalogue : ajouter, supprimer ou étiqueter une ressource met la liste à jour immédiatement.
Sélectionner une ligne choisit cette ressource, qui est celle que le panneau
**Étiquetage des ressources** modifie ensuite.

- La liste est entièrement pilotée par le catalogue partagé ; le panneau lui-même n'effectue
  aucun filtrage ni aucun tri qui lui soit propre.
- Lorsque le panneau **Recherche de ressources** a une requête active, la liste de la
  bibliothèque n'affiche que les entrées correspondantes (voir ci-dessous) ; effacer la requête
  rétablit la liste complète.

## Étiqueter les ressources

Le panneau **Étiquetage des ressources** modifie les étiquettes de la ressource sélectionnée dans
la bibliothèque. Saisissez une étiquette et ajoutez-la ; sélectionnez une étiquette et retirez-la.
Les étiquettes sont des libellés libres — par exemple `hero`, `enemy` ou `tileset-a` — qui vous
permettent d'organiser les ressources par leur sens.

- **Les modifications d'étiquettes sont annulables.** Ajouter ou retirer une étiquette est une
  seule étape de la pile d'annulation partagée, si bien que **Annuler** restaure exactement
  l'ensemble d'étiquettes précédent et que **Rétablir** réapplique la modification — ce sont les
  mêmes annuler / rétablir que partout ailleurs (voir
  [Premiers pas et espace de travail](app-basics.md)).
- **Ajouter une étiquette déjà présente ne fait rien** (c'est sans effet), et retirer une
  étiquette absente est tout aussi inoffensif.
- **Les étiquettes sont bornées.** Une étiquette a une longueur maximale, et chaque ressource a un
  nombre maximal d'étiquettes. Une étiquette trop longue, ou qui ferait dépasser à la ressource
  sa limite d'étiquettes, est **rejetée avec un message clair** et n'est pas ajoutée — rien n'est
  tronqué en silence.

## Rechercher et filtrer

Le panneau **Recherche de ressources** restreint la liste de la bibliothèque à l'aide de trois
contrôles qui fonctionnent ensemble :

| Contrôle | Correspond à |
| --- | --- |
| **Nom** | Les ressources dont le nom *contient* le texte saisi (correspondance de sous-chaîne). |
| **Étiquettes** | Les ressources portant la ou les étiquettes saisies (séparées par des virgules si elles sont plusieurs). |
| **Type** | Les ressources du type choisi ; une entrée **Tous les types** efface le filtre de type. |

- Les trois filtres se **croisent** — un résultat doit correspondre au nom *et* aux étiquettes *et*
  au type que vous avez définis. Laissez un contrôle vide pour ignorer cette dimension.
- **Les résultats sont stables et déterministes** : le même catalogue et la même requête produisent
  toujours la même liste dans le même ordre.
- **Effacer tous les contrôles rétablit le catalogue complet**, dans son ordre normal.

> **Trouver par le sens, non par le fichier.** Comme les ressources sont étiquetées et
> interrogeables, vous pouvez faire apparaître « tous les sprites `enemy` » ou « les tilesets
> étiquetés `dungeon` » sans fouiller dans des dossiers. Donnez aux ressources un petit vocabulaire
> d'étiquettes cohérent, et les filtres font le reste.

## Comment les ressources sont stockées

Derrière les panneaux, la bibliothèque tient un **catalogue** d'entrées de ressources et un
**magasin adressable par le contenu** pour leurs octets :

- **Stockée une fois, par contenu.** Les octets de chaque ressource sont stockés avec pour clé le
  *contenu* lui-même ; inscrire deux fois le même contenu ne le duplique donc pas — des octets
  identiques ne sont conservés qu'une fois (**déduplication**).
- **Référencée par un identifiant stable, et non par un chemin.** Une ressource est identifiée par
  un identifiant stable qui l'accompagne, si bien que **déplacer ou renommer** le fichier
  sous-jacent ne casse **pas** l'entrée du catalogue.
- **L'œuvre garde son format d'enregistrement habituel.** Le catalogue réutilise le format de
  projet `.pixproj` existant pour les données et ne stocke à côté que des références et des
  métadonnées — il n'existe pas de second format dont votre œuvre devrait se soucier.
- **Le chargement est défensif.** Un catalogue ou ses métadonnées sont traités comme une entrée non
  fiable au chargement : ils sont contrôlés en taille et en forme, n'exécutent jamais rien, et
  chaque chemin référencé est confirmé comme restant à l'intérieur de la bibliothèque — un
  catalogue mal formé ou hors bornes est rejeté avec une erreur claire plutôt que de planter ou de
  corrompre quoi que ce soit.

## Le reste de la bibliothèque de ressources

La bibliothèque de ressources a été livrée par tranches ; le jalon entier est désormais livré. Au-delà
du catalogue, de l'étiquetage et de la recherche / du filtre décrits plus haut :

- **[Dépendances des ressources et détection des ruptures](asset-dependencies.md)** — un graphe
  interrogeable de la façon dont les ressources se référencent les unes les autres
  (`sprite -> animation -> tileset -> tilemap`) et un avertissement passif quand la modification
  d'une ressource en casse une autre qui la référence.
- **[Versionnage des ressources et réutilisation entre projets](asset-versioning.md)** — un
  historique de révisions en ajout seul pour chaque ressource (consulter et restaurer), la
  réutilisation par référence plutôt que par copie d'une ressource partagée entre projets,
  l'exportation / importation des ressources référencées d'un projet sous la forme d'un paquet
  autonome, et un stockage cloud facultatif des blocs de données partagés (non connecté dans cette
  version).
