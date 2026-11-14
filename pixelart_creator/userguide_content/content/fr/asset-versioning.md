# Versionnage des ressources et réutilisation entre projets

La bibliothèque de ressources conserve pour chaque ressource un **historique de versions en ajout
seul**, vous permet de **réutiliser une même ressource partagée dans plusieurs projets sans
dupliquer ses octets**, d'**exporter et d'importer** les ressources qu'un projet référence sous la
forme d'un paquet autonome, et de travailler **entièrement hors ligne** ; un magasin de blocs de
données adossé au cloud existe dans la couche de stockage, mais cette version ne le connecte pas
(voir *Stockage cloud facultatif*). Ces fonctions sont accessibles depuis le menu **Bibliothèque**,
à côté des panneaux de la [bibliothèque de ressources](asset-library.md) et des
[dépendances](asset-dependencies.md) sur lesquels elles s'appuient.

> **Référence, pas copie.** Tout ce qui suit repose sur une idée que la bibliothèque applique déjà :
> les octets d'une ressource sont stockés **une seule fois**, avec pour clé leur contenu, dans un
> magasin adressable par le contenu, et un projet ne conserve qu'une **référence** (un identifiant
> stable et le hachage de contenu qu'il attend). Le versionnage, la réutilisation et l'exportation
> déplacent des références et vérifient le contenu — ils ne font jamais de seconde copie de votre
> œuvre.

## Historique des versions

Chaque fois que vous consignez un nouvel état d'une ressource, la bibliothèque ajoute une
**révision** à l'historique de cette ressource :

- **En ajout seul et immuable.** Une révision n'est jamais modifiée ni supprimée sur place.
  Consigner un nouvel état ajoute une nouvelle révision en tête ; les révisions antérieures restent
  exactement telles qu'elles étaient, de sorte que l'historique est un enregistrement fidèle de
  l'évolution de la ressource.
- **Adressée par le contenu.** Chaque révision est identifiée par le **hachage de contenu** de ses
  octets et reliée à la révision qu'elle suit, de sorte que l'historique forme une chaîne adressée
  par le contenu. Deux révisions aux octets identiques partagent un seul bloc de données stocké
  (déduplication).
- **Consigner deux fois le même contenu ne fait rien.** Si vous consignez un contenu dont le
  hachage correspond à la révision de tête actuelle, c'est **sans effet** — aucune nouvelle
  révision et aucun nouveau bloc de données ne sont ajoutés.
- **Borné.** Une ressource conserve au plus un nombre maximal fixe de révisions ; le dépasser est
  signalé par une erreur claire plutôt que d'écarter silencieusement l'historique.

### Parcourir et restaurer des révisions

Le panneau **Versions des ressources** liste dans l'ordre les révisions de la ressource
sélectionnée. Sélectionnez-en une pour l'**examiner**, ou **restaurez** une révision antérieure
pour la rendre de nouveau actuelle.

> **Restaurer ajoute une nouvelle révision — l'historique n'est jamais réécrit.** Restaurer une
> révision antérieure ne supprime **pas** les révisions qui l'ont suivie. À la place, le navigateur
> de versions consigne de nouveau les octets de la révision choisie (vérifiés par leur hachage de
> contenu) comme une **nouvelle révision de tête**. L'historique ne fait que s'allonger : vous
> pouvez donc toujours refaire marche arrière.

Lors d'une restauration, le navigateur de versions vérifie aussi les octets de la révision par
rapport au hachage attendu par son entrée ; un bloc de données qui ne correspond plus à son
hachage consigné est **rejeté avec une erreur claire** (protection contre la falsification et la
corruption) au lieu d'être chargé.

## Réutilisation entre projets (référencer, ne pas copier)

Le panneau **Réutilisation de ressources** vous permet de **référencer une ressource partagée
existante dans un autre projet**. Comme la bibliothèque référence les ressources au lieu de les
copier, la réutilisation ne coûte rien en stockage :

- **Référencer ne copie aucun octet.** Ajouter une ressource partagée à un projet consigne la
  référence ; les octets partagés continuent de n'exister qu'**une seule fois** dans le magasin
  adressable par le contenu. Le nombre de blocs de données stockés est **inchangé** par la
  référence.
- **Les ressources partagées sont signalées.** Lorsque plus d'un projet référence la même
  ressource, le panneau l'affiche comme **Partagé**, ce qui vous permet de voir quelles ressources
  sont utilisées à plusieurs endroits.
- **La présence est vérifiée, jamais écrite.** Avant de référencer une ressource partagée, le
  panneau confirme que les octets partagés sont bien présents ; s'ils manquent, il signale une
  erreur claire au lieu de créer une référence pendante. Il ne fait que lire — il n'écrit jamais de
  nouvelle copie.

> **Pourquoi c'est sans danger.** La réutilisation et le [graphe des dépendances](asset-dependencies.md)
> fonctionnent ensemble : une ressource réutilisée est une référence comme une autre, de sorte que
> l'indicateur de rupture passif signalera une réutilisation dont la cible disparaît ou change par
> la suite.

## Quand une ressource partagée change

Quand vous ouvrez un projet qui référence une ressource de la bibliothèque qui a changé depuis la création de la référence, l'invite **Ressource de la bibliothèque mise à jour** s'affiche, une fois par ressource modifiée :

- **Récupérer la modification** résout désormais la référence vers le contenu actuel de la
  ressource dans la bibliothèque ; la référence du projet passe à la dernière révision de la
  bibliothèque.
- **Conserver la version référencée** continue de résoudre exactement le contenu que le projet
  référence déjà — rien ne change dans la référence.

Annuler ou fermer l'invite a le même effet que **Conserver la version référencée**. Cocher **Ne plus
demander** en choisissant l'une ou l'autre option mémorise ce choix pour les prochaines
modifications de cette ressource, dans ce projet ; vous pouvez rétablir l'invite plus tard depuis
**Édition ▸ Confirmations du projet ▸ Lorsqu'une ressource de bibliothèque référencée change**. Le
choix est enregistré dès que vous le faites, que vous cochiez la case ou non — vous n'avez pas
besoin d'enregistrer le projet pour qu'il soit retenu. Si vous laissez **Ne plus demander** décoché,
votre réponse s'applique tout de même à cette modification ; la modification suivante, différente,
de cette ressource posera de nouveau la question.

## Exporter et importer les ressources d'un projet

**Exporter un paquet de projet** regroupe exactement les ressources qu'un projet référence dans un
**paquet autonome et portable**, de sorte que le projet s'ouvre complet sur une autre machine ;
**Importer un paquet de projet** réintègre un tel paquet. Les deux commandes sont accessibles depuis
le menu **Bibliothèque**.

- **Exactement les ressources référencées — ni plus, ni moins.** L'exportation résout l'ensemble de
  références du projet et regroupe précisément les blocs de données de ces ressources, chacun
  stocké une fois par contenu, ainsi qu'un index de catalogue et des fichiers annexes par
  ressource.
- **Réutilise le format de projet fourni.** Le paquet s'appuie sur le catalogue et sur le mécanisme
  de projet existants — il n'y a aucun nouveau format à apprendre.
- **L'importation est défensive.** Un paquet est traité comme une **entrée non fiable** : il est
  analysé sans rien exécuter, contrôlé en taille et en forme, et **chaque chemin est confirmé comme
  restant à l'intérieur du paquet** (protection contre la traversée de chemin). Chaque bloc de
  données est **vérifié par son hachage de contenu** à mesure qu'il est lu, de sorte qu'un paquet
  altéré ou corrompu est rejeté avec une erreur claire.

## Stockage cloud facultatif

La bibliothèque stocke chaque bloc de données **localement** et fonctionne **entièrement hors
ligne**. La couche de stockage contient aussi un magasin de blocs de données facultatif adossé au
cloud, mais **cette version ne le connecte pas** : la bibliothèque est toujours locale, et ni
**Cloud ▸ Se connecter…** (qui connecte l'adaptateur intégré, en mémoire, décrit dans
[Cloud : enregistrement, versions et enregistrement automatique](cloud-and-collaboration.md)) ni
aucun véritable fournisseur ne l'active. Une fois connecté, ce stockage adossé au cloud est conçu
pour fonctionner sans rien changer à votre façon d'utiliser la bibliothèque :

- **Local d'abord.** Dans cette version, la bibliothèque est purement locale ; le stockage adossé au
  cloud ne serait engagé que **lorsqu'un fournisseur est connecté**.
- **La même interface de stockage.** Le stockage adossé au cloud n'est qu'un autre moteur de blocs
  de données derrière la même interface que celle du magasin local, de sorte que le catalogue, les
  révisions et la réutilisation se comportent de la même façon, que le stockage soit local ou
  partagé.
- **Les données du cloud sont vérifiées et mises en cache.** Un bloc de données récupéré depuis le
  cloud est **vérifié par son hachage de contenu** avant d'être utilisé, puis mis en cache
  localement afin que les lectures suivantes restent hors ligne.
- **Aucun détail de fournisseur ne fuit.** Aucun nom de fournisseur, aucun identifiant et aucun type
  de SDK n'apparaît dans la bibliothèque — le stockage adossé au cloud ne dépend que de la même
  interface cloud indépendante du fournisseur que celle utilisée par le reste de l'application.

## Accessibilité, thèmes et langue

Chaque contrôle du navigateur de versions et du panneau de réutilisation porte un nom accessible et
s'utilise au clavier, tous les libellés peuvent être entièrement traduits, et les deux panneaux
s'affichent correctement dans les thèmes clair et sombre.
