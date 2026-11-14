# Le panneau des calques

Le **panneau des calques** liste les calques et les groupes du document actif pour l'image d'animation en cours, et expose toutes les commandes propres à chaque calque. C'est la surface
principale de l'édition non destructive.

## Lire la liste

- Les calques sont affichés **de haut en bas selon l'ordre z** : la ligne **en haut de la
  liste est le haut de la pile** (dessinée en dernier, au premier plan).
- Une seule ligne est le **calque actif** — c'est la cible des outils de peinture.
- Les **groupes** apparaissent sous forme de nœuds dépliables / repliables contenant leurs
  enfants.

## Commandes de chaque calque

Chaque ligne de calque expose :

| Commande | Fonction |
| --- | --- |
| **Curseur d'opacité** | Règle l'opacité du calque de **0 à 100 %**. S'applique à tous les modes de fusion, pas seulement à Normal. |
| **Commutateur de visibilité** | Affiche ou cache le calque. Un calque caché ne contribue en rien à la composition. |
| **Commutateur de verrouillage** | Protège le calque contre la modification de ses **pixels**. Sur un calque verrouillé, peindre, remplir et effacer n'ont aucun effet ; son opacité, sa visibilité, son mode de fusion et son ordre peuvent toujours changer. |
| **Liste déroulante des modes de fusion** | Choisit l'un des douze [modes de fusion](blend-modes.md). |

> **Le verrouillage ne protège que les pixels.** Vous pouvez toujours mettre le focus sur un
> calque verrouillé, changer son opacité, le cacher ou l'afficher et le réorganiser. Le
> verrouillage empêche seulement de peindre dans ses pixels.

## Gérer les calques

- **Ajouter un calque** — insère un nouveau calque vide au-dessus du calque actif.
- **Supprimer le calque** — supprime le calque actif. Supprimer le **dernier** calque d'une image d'animation est refusé.
- **Dupliquer le calque** — insère une copie pixel pour pixel, avec les attributs copiés,
  au-dessus de la source.
- **Glisser pour réorganiser** — faites glisser une ligne vers une nouvelle position pour
  changer l'ordre z ; le canvas se recompose dans le nouvel ordre. Glisser un calque dans un
  groupe ou hors d'un groupe change son parent.

## Groupes

- **Groupe** enveloppe les calques de premier niveau sélectionnés dans un nouveau nœud de
  groupe.
- **Dégrouper** dissout un groupe en faisant remonter ses enfants dans le parent, à la
  position du groupe.

Un groupe **compose d'abord ses enfants**, puis fusionne ce résultat unique aplati avec la
pile en utilisant l'opacité et le mode de fusion **propres au groupe**. Un groupe aux
attributs par défaut (Normal, 100 %) se compose de manière identique à ses enfants non
groupés. Cacher un groupe cache toute son arborescence. L'imbrication des groupes est bornée.

## Masques

Associez un **masque** à un calque pour moduler son alpha de façon non destructive :

1. Choisissez **Ajouter un masque** pour le calque sélectionné.
2. Activez **Modifier le masque** pour faire du masque la cible de la peinture — peindre
   modifie alors le tampon du masque, et non les pixels du calque.
3. Là où le masque vaut 0, le calque est caché ; là où il est au maximum, le calque est
   entièrement visible ; les valeurs intermédiaires sont proportionnelles.

Un masque entièrement au maximum équivaut à l'absence de masque, et modifier un masque
n'altère jamais les pixels propres du calque. Associer ou supprimer un masque est annulable.

## Calques de référence

Activez **Référence** pour marquer un calque comme calque de **référence**, que vous suivez pour dessiner sur un autre calque : il reste visible dans la composition mais **refuse la
peinture** (les outils de peinture n'ont aucun effet dessus), comme un verrouillage
permanent déclaré à dessein. Ce marquage est réversible.

## Calques intelligents

Utilisez **Calque intelligent** pour créer, à partir d'un calque source sélectionné, un
**calque intelligent**, instance non destructive qui **reflète les pixels de la source** (en
lecture seule) tout en possédant sa propre opacité, sa propre visibilité et son propre mode
de fusion. Modifier la source met à jour toutes les instances intelligentes à la
recomposition suivante ; un calque intelligent n'a pas de pixels modifiables de manière
indépendante.

## Tout compte pour une seule étape d'annulation

Chaque opération de calque proposée par le panneau — définir l'opacité, la visibilité, le
verrouillage ou le mode de fusion, ajouter, supprimer, dupliquer ou réorganiser, grouper ou
dégrouper, associer ou supprimer un masque, définir un calque de référence ou intelligent —
est enregistrée comme **exactement une** commande d'annulation. Annuler restaure l'état exact
antérieur de l'arborescence des calques.

## Mode de couleur et documents indexés

La pile de calques et les modes de fusion s'appliquent aux documents **RGBA**. Les documents
**indexés** n'ont qu'un seul calque par conception — le compositeur ne gère que le RGBA.

- Convertir un document **RGBA à plusieurs calques** en document indexé
  (**Palette ▸ Convertir en indexé**) **aplatit la composition en un seul calque indexé**
  (par image d'animation). Cette conversion est annulable : annuler restaure exactement l'arborescence
  RGBA complète à plusieurs calques — groupes, masques, opacité, modes de fusion, références
  et liens intelligents.
- Reconvertir en RGBA transforme l'unique calque indexé en un seul calque RGBA.

Le mode de couleur du document est l'unique source de vérité, de sorte que ce que le canvas
affiche, ce qui est enregistré dans `.pixproj` et l'indicateur de mode concordent toujours.

## Sujets connexes

- Comprenez comment la pile est composée dans [Modes de fusion](blend-modes.md).
- Chaque image d'animation a sa propre pile de calques — voir la
  [ligne temporelle d'animation](animation-timeline.md).
