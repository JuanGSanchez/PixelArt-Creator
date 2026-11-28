# Sélection et déplacement/copie flottants

Sélectionner une région vous permet de ne travailler que sur une partie de votre œuvre — et
une **sélection flottante** vous permet de prendre les couleurs d'une sélection active et de
les déplacer — ou de les copier — sous la forme d'un **aperçu en direct non destructif**. Les
pixels *situés sous* la sélection flottante ne sont **pas modifiés** tant que vous ne
validez pas, si bien qu'un déplacement peut toujours être repositionné ou abandonné sans
risque.

C'est le comportement que vous connaissez dans Aseprite, Pro Motion NG, Pixelorama et Krita : soulever, faire glisser, déposer.

> **Calque actif uniquement.** Un déplacement ou une copie flottants agissent sur le **calque
> actif** (voir [le panneau des calques](layers.md)). Sur un document indexé, c'est l'unique
> calque indexé. Les autres calques ne sont pas touchés.

## Faire une sélection

Utilisez les outils de sélection pour définir la région sur laquelle vous voulez travailler :

| Outil | Ce qu'il sélectionne |
| --- | --- |
| **Sélection rectangulaire** | Une région rectangulaire que vous tracez en glissant. |
| **Sélection au lasso** | Une région à main levée que vous dessinez autour. |
| **Baguette magique** | Une zone contiguë de couleur similaire sous le clic. |

**Durée de vie de la sélection.** Passer à l'un des trois outils de sélection ci-dessus
**abandonne** toujours la sélection actuelle et repart de zéro — une nouvelle sélection
n'hérite jamais de la forme de la précédente. Passer à tout autre outil (Crayon, Gomme, Pot
de peinture, …) **conserve** en revanche la sélection active, de sorte que le dessin
contraint par masque continue de fonctionner : vos traits restent limités à la sélection
pendant que vous peignez avec un autre outil.

Tant que l'un des trois outils de sélection ci-dessus est actif, **Shift** et **Alt** ont un
sens différent de celui qu'ils ont partout ailleurs sur le canvas — voir
[Déplacer la vue et construire une sélection](#panning-vs-building-a-selection) ci-dessous :

| Modificateur | Résultat lorsqu'un outil de sélection est actif |
| --- | --- |
| **Shift**+glisser | **Ajoute** à la sélection actuelle. |
| **Alt**+glisser | **Soustrait** de la sélection actuelle. |

### Déplacer la vue et construire une sélection

| Geste | Résultat |
| --- | --- |
| **Shift+left-drag** | Déplace la vue du canvas — **sauf** lorsqu'un outil de sélection est actif : il **ajoute** alors à la sélection, exactement comme le décrit le tableau ci-dessus. |

### Sélectionner tout le canvas, inverser et effacer

| Raccourci | Action |
| --- | --- |
| **Ctrl+A** | Sélectionner tout le canvas. |
| **Ctrl+I** | Inverser la sélection actuelle. |
| **Ctrl+Shift+A** | Désélectionner (effacer la sélection actuelle). |

Effacer le **contenu** de la sélection (plutôt que la sélection elle-même) est une action
distincte, avec ses propres raccourcis, **Shift+Q** et **Delete** — voir le tableau de
[Notions de base de l'application](app-basics.md).

## Soulever et déplacer (glisser)

Le déplacement flottant soulève la sélection déjà active — il ne crée **pas** de nouvelle
forme de sélection, il réutilise le masque que vous avez déjà.

1. Avec l'un des outils de sélection (Sélection rectangulaire, Sélection au lasso ou Baguette
   magique) actif, **appuyez à l'intérieur** de la sélection active. Les pixels couverts par
   la sélection se soulèvent en un aperçu flottant.
2. **Faites glisser.** Les couleurs flottantes suivent le curseur ; la région d'origine
   apparaît **effacée en transparent** (indice 0 en mode indexé) dans l'aperçu en direct.
3. Les pixels sous-jacents ne sont **pas encore modifiés** — seul l'aperçu change.

Appuyer **à l'extérieur** de la sélection active ne soulève **pas** la sélection ; cela
démarre une nouvelle sélection comme d'habitude.

## Copier au lieu de déplacer : maintenir Ctrl

Maintenez **Ctrl** enfoncé pendant le glissement pour passer en mode **COPIE** :

- l'**origine reste intacte** (rien n'est vidé), et
- une **copie** des couleurs flotte jusqu'au curseur.

Un curseur ou un repère visuel propre au mode copie signale que vous copiez. Vous pouvez
basculer entre déplacement et copie **pendant** le glissement en appuyant sur Ctrl ou en le
relâchant.

> **Ctrl est le seul modificateur de copie — pas Alt.** La copie se fait avec **Ctrl
> seul**. **Alt n'est pas un modificateur de copie** : un glissement intérieur avec Alt est le
> geste de **soustraction** de la construction de sélection, et il garde ce sens. Maintenir
> **Ctrl+Alt** pendant un glissement intérieur équivaut à Alt-soustraction, pas à une
> copie — utilisez **Ctrl** seul pour copier.

| Glissement intérieur | Résultat |
| --- | --- |
| *aucun modificateur* | Soulève et **déplace** la sélection (origine vidée à la validation) |
| **Ctrl** | **Copie** la sélection (origine conservée) |
| **Alt** | **Soustrait** de la sélection (geste de construction) |
| **Shift** | **Ajoute** à la sélection (geste de construction) — en dehors d'un outil de sélection actif, **Shift+left-drag** déplace la vue au lieu d'ajouter ; voir [Déplacer la vue et construire une sélection](#panning-vs-building-a-selection) ci-dessus. |

## Valider ou annuler

La sélection flottante est **validée** par l'un des événements suivants :

- le **relâchement** du bouton de la souris,
- l'appui sur **Enter / Return**, ou
- le **changement d'outil** (ou d'onglet de canvas).

À la validation, la modification est appliquée comme **exactement une étape annulable** :

- **Déplacement** — l'origine est écrite en transparent (indice 0 en mode indexé) et les
  couleurs sont estampées à la destination.
- **Copie** — les couleurs sont estampées à la destination et l'origine reste inchangée.

Après une validation, le masque de sélection **suit jusqu'à la destination**.

Appuyez sur **Esc** pour **annuler**. Comme la sélection flottante n'a jamais écrit dans le tampon,
l'annulation restaure **exactement** le canvas d'avant le déplacement et n'enregistre
**aucune** entrée d'annulation ; le masque de sélection revient à sa position d'avant le
soulèvement.

> **Un clic sans glissement ne coûte rien.** Valider avec un décalage nul (un clic dans la
> sélection sans déplacement) n'a aucun effet — cela ne crée aucune étape d'annulation.

Si la destination contient déjà des pixels, une boîte de dialogue **Écraser les pixels
existants ?** demande d'abord confirmation : **Continuer** applique la validation comme
d'habitude, **Annuler** n'applique rien et laisse la sélection flottante active à son décalage actuel.
Cocher **« Ne plus demander pour ce projet »** n'enregistre le masquage de cette demande
qu'une fois que vous acceptez réellement — la cocher puis annuler n'enregistre rien.

## Bords hors du canvas

Vous pouvez faire glisser la sélection flottante **en partie ou entièrement hors du canvas**. À la
validation, les pixels hors du canvas sont **abandonnés** (jamais rebouclés), de sorte que
vous pouvez pousser l'œuvre jusqu'au bord sans erreur. Pour un déplacement, toute l'origine
située dans les limites est quand même vidée, quelle que soit la distance de glissement.

## Annuler, rétablir et rendu

- Un déplacement ou une copie validés comptent pour **une** étape d'annulation : **annuler**
  restaure exactement le tampon d'avant le déplacement ; **rétablir** le réapplique.
- L'aperçu flottant est rendu **au plus proche voisin, anticrénelage désactivé**, à
  n'importe quel zoom, et reste lisible dans les thèmes **clair** et **sombre**.
- L'aperçu de glissement en direct ne met à jour que la région que touche la sélection flottante, de
  sorte qu'il reste dans le budget de 16 ms / 60 images par seconde, même sur un canvas 8K.

## Transformations du document entier

**Image ▸ Mettre à l'échelle…**, les deux rotations d'un quart de tour et les deux actions
de retournement agissent toutes sur le **document entier** — chaque calque et chaque masque,
sur toutes les images d'animation — chaque fois que rien n'est sélectionné. Avec une sélection active,
ces mêmes actions ne transforment toujours que la région du calque actif couverte par la
sélection, exactement comme avant.

| Raccourci | Action |
| --- | --- |
| **Shift+H** | Retourner la sélection (ou le document entier) horizontalement. |
| **Shift+V** | Retourner la sélection (ou le document entier) verticalement. |

RotSprite est la seule exception : il ne transforme jamais que le calque actif, avec ou sans
sélection, car sa rotation ne modifie jamais les dimensions du tampon et n'a jamais eu
besoin d'une portée plus large.

> **Les grandes transformations demandent d'abord confirmation.** Lorsque le résultat
> rééchantillonné et les tampons conservés pour l'annulation dépasseraient ensemble
> 506,25 Mio (l'équivalent de quatre canvas 8K complets de données RGBA), une boîte de
> dialogue **Confirmer la transformation importante** indique la mémoire projetée exacte
> avant que quoi que ce soit ne s'exécute. **Annuler** est le bouton par défaut, si bien
> qu'appuyer sur Return ne lance **pas** la transformation — vous devez cliquer
> délibérément sur **Continuer**. Refuser laisse le document entièrement intact et n'empile
> rien sur la pile d'annulation. En dessous de ce seuil, aucune boîte de dialogue
> n'apparaît.

Une fois qu'une transformation du document entier est en cours, une boîte de dialogue de
progression **Transformation du document** la suit tampon par tampon et peut être annulée à
tout moment — le bouton Annuler, Escape ou la commande de fermeture de la fenêtre
fonctionnent tous. L'annulation est atomique : le document est laissé exactement tel qu'il
était et rien n'atteint la pile d'annulation, quel que soit le nombre de tampons déjà
rééchantillonnés.

## Ce qui n'est pas couvert

- **Faire pivoter ou mettre à l'échelle** la sélection *pendant qu'elle flotte* — validez
  d'abord le déplacement, puis utilisez les outils de transformation.
- Une variante **déplacer tous les calques** — la sélection flottante n'agit que sur le calque actif.
- Le glissement d'une sélection flottante **entre documents**, ou son enregistrement dans un `.pixproj` — une sélection flottante est un état d'édition transitoire, toujours validée ou annulée au préalable.
