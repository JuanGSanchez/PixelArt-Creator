# Tilesets, tilemaps et tuilage automatique

Le **système de tilemap** transforme une image source en un **tileset** réutilisable et vous
permet de peindre de grands niveaux avec ces tuiles sur une **carte infinie à plusieurs
calques** : découpez une image en tuiles indexées, tamponnez / effacez / remplissez des
cellules, laissez le **tuilage automatique** résoudre les bordures à votre place, retournez et
pivotez les tuiles au moment de les placer, et **exportez / importez** toute la carte en JSON
compatible Tiled. Chaque modification de la carte constitue une seule étape d'annulation.

> **Tuiles logiques et tuiles affichées.** Le tuilage automatique sépare la tuile que vous
> *placez* (la tuile **logique**) de la tuile qui est *affichée* (la tuile **d'affichage**).
> Vous peignez une seule tuile « mur » et la carte choisit la variante de bord ou de coin
> appropriée à partir de ses voisines ; le placement logique est ce qui est stocké et ce qui
> fait l'aller-retour, de sorte que le résultat est **déterministe et réversible**. Désactiver
> le tuilage automatique affiche directement la tuile logique.

## Tilesets

Un **tileset** est une image source découpée en une grille de tuiles de taille égale. Ouvrez
le panneau **Éditeur de tileset** (menu Tilemap) et ajoutez un tileset avec
**Tilemap ▸ Nouveau tileset à partir d'une image…** ; l'outil de découpe lit l'image avec votre
**taille de tuile**, une **Marge** extérieure facultative et un **Espacement** facultatif
entre les tuiles, et indexe les tuiles obtenues de gauche à droite et de haut en bas, à
partir de `0`.

- Chaque tuile est une région de la mémoire tampon source, de sorte qu'un tileset est **adossé à une
  seule image** plutôt qu'à de nombreuses copies.
- **Modifier une tuile source se répercute** sur chaque instance placée de cette tuile dans
  tous les calques — repeignez la tuile une fois et tout le niveau est mis à jour.
- Le panneau présente les tuiles découpées sous la forme d'une grille de sélection ; la tuile
  sélectionnée est celle que peint l'outil tampon.

> **Marge et espacement.** `margin` est la bordure ignorée autour de toute l'image ;
> `spacing` est l'écart ignoré **entre** les tuiles. Les feuilles de sprites exportées avec une
> gouttière de 1 px nécessitent généralement `spacing = 1` (et `margin = 1` si la gouttière
> entoure aussi les bords) pour que l'outil de découpe tombe exactement sur chaque tuile.

## Peindre une tilemap

Le **canvas de tilemap** peint des cellules sur une grille, à raison d'une tuile par
cellule. Choisissez une tuile dans le panneau Éditeur de tileset, puis utilisez les outils de
carte :

| Outil | Effet |
| --- | --- |
| **Outil tampon** | Place la tuile sélectionnée dans la cellule située sous le curseur (faites glisser pour peindre une série de cellules). |
| **Gomme à tuiles** | Remet la cellule à l'état vide. |
| **Remplissage rectangulaire** | Remplit avec la tuile sélectionnée un rectangle que vous tracez en faisant glisser. |

Chaque tampon / effacement / remplissage rectangulaire constitue **exactement une étape
d'annulation**, et l'annulation restaure exactement les cellules précédentes. Peindre à
proximité de tuiles existantes recalcule le voisinage de **tuilage automatique** afin que les
bordures restent correctes pendant que vous dessinez.

### Retourner et pivoter

Avant de tamponner, vous pouvez transformer la tuile : **Retourner le tampon horizontalement**
et **Retourner le tampon verticalement** la reflètent, et **Pivoter le tampon de 90° (sens
horaire)** la fait passer par les quatre orientations à angle droit. La transformation est
stockée pour chaque cellule placée sous la forme d'un indicateur compact sur la tuile, de
sorte que retourner ou pivoter une tuile ne coûte **aucune entrée de tileset supplémentaire**
et fait l'aller-retour sans perte. Les transformations se composent dans un ordre fixe
(diagonale, puis horizontale, puis verticale) afin qu'une combinaison donnée soit toujours
rendue à l'identique.

## Tuilage automatique

Le **tuilage automatique** résout la tuile *affichée* de chaque cellule à partir de ses
**huit voisines** (le schéma Blob-47 : un masque de bits sur 8 voisines avec un filtrage bord-implique-coin, ce qui donne 47 tuiles distinctes). Peignez une seule tuile de
« terrain » et la carte remplit automatiquement les bords droits ainsi que les coins
intérieurs et extérieurs appropriés.

- **Activez ou désactivez** le tuilage automatique avec la case **Tuilage automatique
  (Blob-47)** du panneau Calques de tilemap. Lorsqu'il est **activé**, peindre, effacer ou
  remplir un rectangle recalcule aussi les cellules concernées **et leurs voisines** afin que
  la bordure reste toujours cohérente — le tout dans la même étape d'annulation.
- La résolution est une **fonction pure et déterministe** du placement logique et des
  voisines : une même carte produit donc toujours les mêmes tuiles affichées.
- **Désactiver** le tuilage automatique affiche directement la tuile logique que vous avez
  placée, sans résolution des bordures.

## Calques et cartes infinies

Une tilemap est **à plusieurs calques** — empilez un calque d'arrière-plan, un calque de
terrain et un calque de détails, chacun peint indépendamment — avec le même modèle de calques
que le reste de l'éditeur (ajouter / supprimer / réorganiser / afficher-cacher). Le panneau
**Calques de tilemap** gère la pile ; les calques visibles sont composés ensemble pour
l'affichage.

La carte elle-même est **infinie** : les cellules sont stockées dans une **grille clairsemée
de blocs de 16×16**, de sorte que seules les régions que vous peignez réellement consomment de
la mémoire. Vous pouvez tamponner loin de l'origine (dans n'importe quelle direction) sans
dimensionner la carte à l'avance, et les régions vides ne coûtent rien. Chaque cellule est un
identifiant de tuile (GID) sur 32 bits qui porte l'indice de la tuile ainsi que ses
indicateurs de retournement et de rotation.

> **Rendu des grandes cartes.** Chaque bloc visible est rendu une fois puis mis en cache ; le
> déplacement de la vue réutilise les blocs en cache au lieu de les repeindre, de sorte que le
> défilement d'une grande carte reste fluide. Le **premier** rendu d'une région tout juste
> devenue visible est précalculé en arrière-plan (hors du fil d'exécution de l'interface) afin que la
> fenêtre reste réactive pendant ce calcul.

## Exportation / importation JSON Tiled

La carte s'exporte en **JSON compatible Tiled** et se réimporte **sans perte** — un
aller-retour conserve les calques, chaque cellule et ses indicateurs de retournement et de
rotation, ainsi que tous les champs que l'éditeur n'utilise pas lui-même (les champs inconnus
sont transmis tels quels).

- **Exporter** (**Tilemap ▸ Exporter en JSON Tiled…**) écrit une carte Tiled valide dont les
  données de calque sont en **CSV**.
- **Importer** (**Tilemap ▸ Importer du JSON Tiled…**) lit les cartes Tiled écrites en CSV ou
  avec des données de calque en base64 non compressées, gzip ou zlib, et accepte une
  référence de tileset **`.tsj` externe**.
- L'importation est un **chargement défensif et validé** : une carte mal formée, un calque
  compressé en **zstd** non pris en charge ou une référence de tileset externe **`.tsx`** sont
  rejetés avec une erreur claire plutôt qu'un plantage ou une corruption silencieuse.

> **Fidélité de l'aller-retour.** Comme les champs inconnus survivent à l'aller-retour et que
> les indicateurs de retournement et de rotation sont conservés bit à bit, vous pouvez
> déplacer une carte entre PixelArt Creator et Tiled sans perdre les données ajoutées par
> l'autre outil.

## Persistance

Les tilesets et les tilemaps font l'aller-retour dans un fichier `.pixproj`. Enregistrer puis
rouvrir un projet restaure à l'identique chaque tileset (sa source et sa configuration de
découpage) et chaque tilemap (ses calques, ses cellules et les indicateurs de retournement et
de rotation de chaque cellule). Les projets enregistrés par des versions antérieures (avant
l'existence des tilemaps) s'ouvrent toujours — ils se chargent simplement sans tileset ni
tilemap.

## Annuler, rétablir et ce qui n'est *pas* annulable

- **Annulable (une étape par action) :** tamponner / effacer une cellule, remplir une zone
  rectangulaire (y compris le recalcul des voisines du tuilage automatique), et ajouter /
  supprimer / réorganiser / afficher-cacher un calque de tilemap.
- **Non annulable (état de la vue) :** sélectionner une tuile dans le panneau Éditeur de
  tileset, activer ou désactiver le tuilage automatique, choisir un retournement ou une
  rotation pour le prochain tampon, et déplacer la vue sur la carte.

## Ce qui n'est pas couvert

- Les données de calque Tiled **compressées en zstd** et les tilesets **`.tsx` externes** à
  l'importation — rejetés par conception (l'importation accepte le CSV et le base64 (non
  compressé, gzip ou zlib) ainsi que les `.tsj` externes) ; utilisez l'un des encodages pris
  en charge.
- Les jeux de tuiles **Wang d'angle / de bord** au-delà du schéma Blob-47 sur 8 voisines — le
  moteur de tuilage automatique est conçu pour être étendu à ces jeux dans une phase
  ultérieure.
- Les **tuiles animées** et les **calques d'objets** — phase ultérieure ; cette version couvre
  les calques de tuiles.
