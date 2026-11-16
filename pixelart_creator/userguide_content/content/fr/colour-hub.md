<!-- surface-only: bundle — contenu d'orientation dans l'application ; sans page de site, par conception -->
# Le centre de couleurs du clic droit

Le **centre de couleurs** est un menu contextuel que vous invoquez **là où vous travaillez** :
faites un **clic droit** sur le canvas et il s'ouvre au niveau du curseur. Il vous offre deux
moyens rapides de choisir une couleur — une liste de **Favoris** soigneusement composée et une
**roue chromatique** complète avec des **harmonies de la théorie des couleurs** en direct — et
il applique immédiatement votre choix.

## Ouvrir le centre

Faites un clic droit n'importe où sur le [canvas](canvas-and-view.md). Le centre de couleurs
apparaît ancré au niveau du curseur, si bien que vous n'avez jamais à vous rendre jusqu'à un
panneau éloigné pour changer de couleur. Choisissez une couleur : elle devient aussitôt la
**couleur active** et la pastille active se met à jour en conséquence. **Un nouveau clic
droit alors que le centre est ouvert le ferme** sans rien choisir, ce qui vous permet de
faire marche arrière et de continuer à peindre exactement là où vous en étiez.

## Favoris

Les **Favoris** forment votre liste personnelle et persistante de couleurs de prédilection.

- **Ajouter aux favoris** conserve la couleur actuelle dans les Favoris pour qu'elle soit à
  un clic de distance la prochaine fois.
- **Supprimer** retire une couleur dont vous n'avez plus besoin.
- **Monter** / **Descendre** réorganisent les favoris afin que les couleurs que vous utilisez
  le plus se trouvent en tête.

Votre liste de Favoris **persiste** d'une session à l'autre, de sorte que votre palette de
travail est toujours là quand vous rouvrez l'application. Un clic sur un favori l'applique
immédiatement.

Il existe aussi un geste qui atteint les Favoris sans même ouvrir le centre :

| Geste | Résultat |
| --- | --- |
| **Middle-click** | Sélectionne la première entrée des Favoris et en fait la couleur active, sur-le-champ, que le centre soit ouvert ou non. |

## La roue chromatique

La **roue chromatique** est une roue RGB façon Canva qui permet de choisir n'importe quelle
couleur par sa teinte et sa saturation, avec un contrôle de valeur (luminosité). Pendant que
vous vous déplacez sur la roue, la couleur active se met à jour en direct.

## Harmonies de la théorie des couleurs en direct

Pendant que vous choisissez sur la roue, le centre affiche des **pastilles d'harmonie**
dérivées de votre couleur actuelle selon la théorie des couleurs classique, afin que vous
puissiez construire une palette cohérente sans tâtonner :

| Harmonie | Relation avec votre couleur |
| --- | --- |
| **Complémentaire** | La teinte opposée (+180°) — contraste maximal. |
| **Analogue** | Les teintes voisines (±30°) — des combinaisons calmes et cohérentes. |
| **Triadique** | Deux teintes situées à 120° (±120°) — équilibré et vibrant. |
| **Tétradique** | Trois teintes espacées régulièrement de 90° — quatre couleurs, fort contraste. |
| **Complémentaire divisée** | Les deux teintes de part et d'autre du complément (±150°). |
| **Tons foncés** et **Tons clairs** | Les **tons foncés** sont des paliers plus sombres de votre couleur ; les **tons clairs** sont des paliers plus clairs. Le panneau **Rampes de tons** (ouvrez-le depuis le menu **Palette**) présente des rampes entières de tons foncés, de tons clairs et de tons grisés pour votre couleur active, chacune avec un bouton **Ajouter à la palette**. |

La roue elle-même et les pastilles d'harmonie — les petits cercles disposés autour — se
comportent différemment, et il vaut la peine de ne pas les confondre :

- **La zone de la roue n'est pas une pastille.** La faire glisser définit la couleur du
  cercle d'harmonie actuellement sélectionné ; elle n'a pas de double-clic qui lui soit propre.
- **Un simple clic sur un cercle d'harmonie peint aussitôt avec la couleur de ce cercle**, et
  laisse intacte la couleur propre du cercle — rien ne change pour la roue ou le cercle,
  seul votre canvas change.
- **Double-cliquez sur un cercle pour adopter sa couleur à la place** — elle devient votre
  couleur active sans rien peindre. L'activation au clavier fait de même : placez le focus sur
  un cercle avec Tab, puis appuyez sur **Space** ou **Enter** pour l'adopter.

Un simple clic sert donc à peindre à la volée avec une couleur d'harmonie sans perturber
votre couleur active, et un double-clic (ou Space / Enter sur un cercle qui a le focus) sert
à vous engager sur cette couleur comme couleur active. Les harmonies se recalculent en
direct pendant que vous vous déplacez sur la roue.

## Appliquer et enregistrer

- **Choisir** — la couleur choisie devient active immédiatement et la pastille active la
  reflète, si bien que votre prochain trait l'utilise.
- **Ajouter aux favoris** — conservez une couleur que vous aimez pour plus tard.

## Palettes et documents indexés

Le centre de couleurs fonctionne de concert avec la **palette** de votre document. Sur un
document **indexé**, la palette est l'ensemble fixe de couleurs que l'œuvre utilise ; vous
pouvez charger des palettes en déposant un fichier `.gpl`, `.hex` ou `.pal` sur la fenêtre
(voir [Importation par glisser-déposer](drag-drop-import.md)). Remplacer la palette
compte pour une seule étape annulable.

## Sujets connexes

- Peignez avec la couleur choisie sur [le canvas](canvas-and-view.md).
- Passez du mode de couleur RGBA au mode indexé, et inversement, depuis le menu **Palette**
  (**Convertir en indexé** / **Convertir en RGBA**) ; voir [Le panneau des calques](layers.md)
  pour ce que la conversion fait aux calques.
