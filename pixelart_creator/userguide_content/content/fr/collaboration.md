# Projets partagés, commentaires, présence et temps réel

Dans cette version, la **couche de collaboration** fonctionne à l'intérieur d'une seule fenêtre de
l'application en cours d'exécution, entièrement en mémoire (voir la note ci-dessous). Dans cette
fenêtre, vous pouvez **partager un projet** avec un ensemble nommé de membres (chacun avec un rôle),
laisser et résoudre des **commentaires**, voir **qui d'autre est présent** et créer des **branches**
de l'œuvre comme avec du code source. **La co-édition en temps réel et les curseurs en direct ne
peuvent pas se connecter dans cette version** : **Démarrer le mode temps réel…** ne rejoint rien, de
sorte que les sections sur le temps réel ci-dessous décrivent le fonctionnement d'une session une
fois qu'une connexion existe. La couche est conçue pour que plusieurs personnes travaillent autour
d'un même projet cloud et suit la conception indépendante du fournisseur de la
[couche cloud](cloud-and-collaboration.md), mais, dans cette version, les panneaux n'enregistrent ni
n'ouvrent aucun `.pixproj` ; ils gèrent uniquement la liste des membres, les commentaires et la
présence.

> **À quoi cette version se connecte.** Les panneaux **Projets partagés**, **Commentaires** et
> **Présence** utilisent un adaptateur intégré qui garde tout en mémoire à l'intérieur de la seule
> fenêtre de l'application qui l'a créé. Chaque fenêtre a le sien : une deuxième fenêtre de
> l'application sur le même ordinateur ne peut donc pas voir les projets, les membres, les
> commentaires ni la présence de la première, et la copie d'une autre personne non plus. Rien n'est
> envoyé sur un réseau ni écrit sur le disque, et tout disparaît à la fermeture de l'application.
> **Démarrer le mode temps réel…** ne peut rien rejoindre dans cette version (voir *Co-édition en
> temps réel* ci-dessous). Les branches sont une fonction locale, limitée à la session.

Tout ce qui figure dans ce guide se pilote depuis le **menu Cloud**, qui comporte les panneaux
ancrables de collaboration et les commandes de temps réel sous l'entrée de l'historique des
versions :

- **Cloud ▸ Projets partagés** — partager le projet actuel et gérer ses membres.
- **Cloud ▸ Commentaires** — ajouter, organiser en fil et résoudre des commentaires.
- **Cloud ▸ Présence** — voir qui est présent et se signaler.
- **Cloud ▸ Démarrer le mode temps réel… / Arrêter le mode temps réel** — rejoindre ou quitter une
  session de co-édition en direct (connexion impossible dans cette version).
- **Cloud ▸ Afficher les curseurs en direct** — afficher ou masquer, sur votre canvas, les curseurs
  en direct des autres éditeurs (il n'y en a aucun à afficher tant qu'une session en temps réel ne
  peut pas se connecter).
- **Cloud ▸ Branches** — ouvrir le panneau des branches (créer, basculer, fusionner).

Chaque entrée de panneau affiche ou masque le panneau correspondant, de sorte que vous pouvez les
disposer à côté des panneaux des calques, de la ligne temporelle et des autres panneaux de flux de
travail.

> **Un seul port indépendant du fournisseur — pas d'enfermement propriétaire.** Tout comme pour les
> enregistrements cloud d'un seul utilisateur, la collaboration ne dialogue jamais directement avec
> un fournisseur précis. Le partage, la gestion des membres, les commentaires et la présence passent
> tous par la **même interface indépendante du fournisseur** (la famille du *port cloud*), de sorte
> que l'application se comporte de façon identique quel que soit le fournisseur sur lequel elle
> s'appuie. Dans cette version, cette interface est assurée par l'adaptateur intégré en mémoire
> décrit plus haut.

## Partager un projet et gérer la liste des membres

Le partage d'un projet se fait depuis le panneau **Projets partagés**. Ouvrez-le avec **Cloud ▸
Projets partagés**.

### Créer (partager) un projet

1. Dans le champ **Nom du projet partagé**, saisissez le nom sous lequel votre projet partagé sera enregistré (par exemple `team-sprite`). Réutilisez ce nom plus tard pour continuer à travailler
   sur le même projet partagé.
2. Constituez la **liste à partager** avec la ligne d'ajout de membre :
    - Saisissez un **identifiant de membre** (l'identifiant du collaborateur) dans le champ
      *Identifiant du membre à inviter*.
    - Choisissez un **rôle** dans le sélecteur de rôle — **Propriétaire**, **Éditeur** ou
      **Lecteur**.
    - Cliquez sur **Ajouter un membre**. Le membre apparaît, avec son rôle, dans la liste modifiable
      *Liste à partager*.
3. Répétez l'étape 2 pour chaque collaborateur. Pour retirer quelqu'un avant le partage,
   sélectionnez sa ligne et cliquez sur **Supprimer**.
4. Lorsque la liste est prête, cliquez sur **Partager / Mettre à jour**. Le projet est partagé avec
   exactement cette liste, et les membres enregistrés apparaissent dans la liste en lecture seule
   *Membres actuels* ci-dessous.

> **Rôles.** Un rôle est un marqueur d'autorisation indépendant du fournisseur, attaché à chaque
> membre : **Propriétaire** — contrôle total du projet partagé ; **Éditeur** — peut modifier l'œuvre
> et commenter ; **Lecteur** — peut voir et commenter. Les rôles sont stockés avec chaque membre et affichés à la fois dans la liste modifiable et dans la liste des membres actuels.

> **La limite de membres.** Un projet partagé peut compter **32** membres au plus. Le panneau refuse
> d'ajouter un membre au-delà de cette limite avec un message clair, et la couche de stockage impose
> la même limite comme seconde ligne de défense. Les identifiants de membre en double sont aussi
> refusés.

### Mettre à jour la liste des membres

Pour changer qui fait partie d'un projet partagé, ajustez la liste modifiable (ajoutez ou retirez des
membres) et cliquez de nouveau sur **Partager / Mettre à jour**. Repartager **remplace** la liste par
le brouillon actuel — il n'existe pas d'étape distincte « ajouter un seul membre », veillez donc à
ce que le brouillon énumère toutes les personnes qui doivent avoir accès avant de le confirmer.

### Ouvrir un projet partagé

Saisissez le nom d'un projet partagé existant et partagez-le (ou repartagez-le avec la même liste de
membres) pour en faire le **projet partagé actif**. Les panneaux Commentaires et Présence agissent
toujours sur le projet partagé actif ; l'ouvrir ici relie donc les trois panneaux au même projet en
une seule fois.

## Ajouter et consulter des commentaires

Les commentaires se trouvent sur le projet partagé actif. Ouvrez le fil avec **Cloud ▸
Commentaires**.

### Lire le fil

La vue des commentaires est une **arborescence en fil de discussion** à trois colonnes :

- **Auteur** — l'identifiant du membre qui a écrit le commentaire.
- **Commentaire** — le texte du commentaire.
- **Statut** — **Ouvert** ou **Résolu**.

Les réponses sont imbriquées sous le commentaire auquel elles répondent, de sorte qu'une discussion
se lit comme un fil en retrait.

### Ajouter un commentaire

1. Saisissez **votre identifiant de membre** dans le champ *Votre identifiant de membre* (il est
   enregistré comme auteur du commentaire).
2. Saisissez votre commentaire dans la zone de texte en bas. Un **compteur d'octets** en direct
   indique quelle part du budget par commentaire vous avez utilisée (par exemple
   `18 / 4096 bytes`).
3. *(Facultatif)* Pour répondre à un commentaire existant, sélectionnez-le dans le fil et activez
   **Répondre à la sélection** — votre nouveau commentaire sera placé sous celui-ci.
4. Cliquez sur **Ajouter un commentaire**. Le commentaire apparaît dans le fil (imbriqué sous son
   parent s'il s'agissait d'une réponse) avec le statut **Ouvert**.

### Résoudre un commentaire

Sélectionnez un commentaire dans le fil et cliquez sur **Résoudre**. Son statut devient **Résolu**.
Résoudre est une marque à sens unique indiquant qu'un commentaire a été traité ; le commentaire reste
dans le fil pour mémoire.

> **Limites des commentaires.** Deux limites s'appliquent, chacune imposée à l'entrée du panneau avec un retour et revérifiée par la couche de stockage : **Taille du commentaire** — un
> commentaire peut faire au plus **4096 octets** (mesurés sur la **longueur en octets UTF-8**, de
> sorte qu'un texte accentué ou non latin compte son coût réel en octets) ; et **Nombre de
> commentaires** — un projet partagé peut contenir au plus **1024** commentaires.

> **Les commentaires sont validés, jamais exécutés.** Le texte d'un commentaire est traité comme une
> **entrée non fiable** : il est contrôlé en schéma et en taille avant d'être stocké et n'est
> **jamais** évalué ni exécuté comme du code. Des données mal formées ou trop volumineuses sont
> rejetées avec une erreur claire, jamais par un plantage.

## Voir qui est présent

Le panneau **Présence** affiche une liste en direct des personnes *actuellement présentes* dans le
projet partagé actif. Ouvrez-le avec **Cloud ▸ Présence**.

1. Saisissez **votre identifiant de membre** dans le champ de présence.
2. Cliquez sur **Rejoindre** pour vous signaler comme présent. Votre identifiant apparaît dans la
   liste des membres présents.
3. Cliquez sur **Quitter** pour effacer votre présence lorsque vous vous absentez.

> **La présence est éphémère.** La présence n'est **jamais enregistrée dans le fichier du projet** ni
> dans son état de collaboration — c'est un signal en direct, en mémoire, indiquant qui est là à
> l'instant. Fermer un projet partagé ou le quitter efface votre présence.

> **Liste de présence et curseurs en direct.** Le panneau Présence affiche la **liste de présence** —
> la liste des personnes présentes. Dessiner les **curseurs et sélections en direct** des autres
> collaborateurs sur votre canvas est une fonction distincte — voir *Co-édition en temps réel*
> ci-dessous.

## Comment les modifications concurrentes convergent

Lorsque plusieurs membres modifient un projet partagé, leurs changements sont conciliés par un
**modèle de convergence hybride déterministe**, de sorte que tout le monde se retrouve avec le
**même** projet, quel que soit l'ordre d'arrivée des modifications :

- Les **métadonnées structurées** — l'arbre des calques, les attributs des calques (nom, opacité,
  visibilité, verrouillage) et l'ordre des calques pour chaque image d'animation — convergent grâce
  à un **CRDT de séquence / d'arbre**.
- Les **pixels matriciels** convergent par **dernier écrivain gagnant par tuile** : le canvas est
  découpé en tuiles de 64 pixels, et les modifications concurrentes de tuiles *différentes*
  survivent toutes, tandis que les modifications concurrentes de la *même* tuile se résolvent par un
  départage déterministe fondé sur l'horloge logique et l'identifiant du site.

Le résultat est **déterministe** : pour un même ensemble de modifications, chaque participant converge
vers un projet identique à l'octet près — la fusion ne lit ni l'horloge de la machine, ni le hasard, ni les paramètres régionaux. Il s'agit du modèle de conciliation **par lots** ; appliquer les modifications
**en direct**, au fur et à mesure, est la voie temps réel décrite ensuite.

## Co-édition en temps réel

La co-édition en temps réel applique les modifications de chaque participant sur le canvas de
**chaque** pair au fur et à mesure qu'elles se produisent, en convergeant avec le même modèle
déterministe que la fusion par lots ci-dessus. Les modifications transitent par un **serveur de
synchronisation en temps réel** dédié (voir la note à l'intention de l'opérateur à la fin).

> **Connexion impossible dans cette version.** L'application de bureau n'a aucune connexion temps réel
> configurée : **Cloud ▸ Démarrer le mode temps réel…** (après la saisie d'un identifiant de membre)
> ne rejoint donc aucune session. La barre d'état affiche un message se terminant par
> « no real-time transport configured », et il n'en résulte ni pairs, ni curseurs en direct, ni
> rejeu pour les retardataires. Les étapes ci-dessous décrivent le fonctionnement d'une session une
> fois qu'une connexion existe.

### Démarrer ou rejoindre une session

1. Ouvrez le document que vous voulez co-éditer (un projet partagé ou n'importe quel onglet ouvert).
2. Choisissez **Cloud ▸ Démarrer le mode temps réel…**.
3. Saisissez **votre identifiant de membre** lorsqu'il vous est demandé — c'est ainsi que les pairs
   vous voient (et il étiquette votre curseur en direct). L'application rejoint le relais temps réel
   du document.
4. Une fois connecté, la surimpression **Afficher les curseurs en direct** est activée
   automatiquement.

Tous ceux qui démarrent le temps réel sur le **même document** rejoignent la même session. Si un
projet partagé est ouvert, la session est associée à ce projet partagé afin que toute l'équipe
converge sur un seul document ; sinon, elle est associée à votre document local.

Pour quitter, choisissez **Cloud ▸ Arrêter le mode temps réel**. Vous pouvez vous reconnecter à tout
moment ; quitter efface les curseurs en direct.

> **Les retardataires rattrapent automatiquement leur retard.** Le serveur de synchronisation
> **conserve durablement** le flux de modifications de chaque document, de sorte qu'un collaborateur
> qui rejoint la session après le début des modifications **rejoue les modifications accumulées** et
> arrive au même document convergé que tous les autres.

> **Le temps réel reste réactif.** Les modifications entrantes sont reçues sur une tâche
> d'arrière-plan et appliquées au document actif sur le fil d'exécution de l'interface, en ne redessinant
> **que les tuiles modifiées** (un redessin par rectangles modifiés). Une seule modification
> entrante coûte la taille de cette modification, pas celle du canvas entier, de sorte que la
> co-édition reste fluide même à la taille de canvas 8K.

> **Les données entrantes sont traitées comme non fiables, par construction.** Chaque modification entrante et chaque donnée de curseur est
> **validée en schéma et en taille** avant d'être appliquée et n'est **jamais** exécutée comme du
> code. Un message mal formé ou trop volumineux est rejeté avec un avis dans la barre d'état, jamais
> par un plantage.

### Curseurs et sélection en direct

Tant que le temps réel est connecté, **Cloud ▸ Afficher les curseurs en direct** affiche ou masque
une surimpression qui dessine sur votre canvas les curseurs et les sélections des autres éditeurs,
chacun étiqueté avec l'identifiant de membre du pair.

- Les curseurs sont **éphémères** — ce sont uniquement un signal en direct, et ils ne sont **jamais**
  écrits dans le `.pixproj` ni dans l'état enregistré du projet.
- Masquez la surimpression à tout moment pour désencombrer la vue ; votre propre édition n'est pas
  affectée.

## Branches de l'œuvre

Les branches vous permettent de bifurquer le projet actuel en une ligne de modifications
indépendante, d'y travailler sans perturber la branche principale, puis de la **fusionner** de
nouveau **sans aucune résolution manuelle de conflit** — le même modèle CRDT / dernier écrivain
gagnant, qui sert à la convergence, fusionne automatiquement les deux lignes. Ouvrez le panneau avec
**Cloud ▸ Branches**.

### Créer une branche

1. Avec un projet ouvert, cliquez sur **Nouvelle branche** dans le panneau Branches.
2. Dans l'invite **Nom de la branche**, saisissez un nom (par exemple `experiment`). La branche est créée à partir du
   document actuel et apparaît dans la liste des branches ; la **branche principale** est toujours
   présente.

### Changer de branche

Sélectionnez une branche dans la liste et cliquez sur **Basculer**. Le document de la branche
sélectionnée est chargé dans l'onglet actif : vous modifiez donc la copie indépendante de cette
branche. Basculer vers la **branche principale** ramène au tronc.

### Vérifier avant de fusionner

Sélectionnez une branche secondaire et cliquez sur **Ouvrir les différences** — une commande
distincte de **Fusionner**, activée dans les mêmes conditions. Elle ouvre une boîte de dialogue de
différences **non modale, en lecture seule**, qui calcule une seule fois, à son ouverture, la
divergence entre la branche et la branche principale, et liste les **Régions concernées** — chaque
zone modifiée, signalée à une granularité fixe d'une tuile de pixels, de sorte que même une
modification d'un seul pixel apparaît comme une tuile entière — ainsi qu'un avertissement de
supervision lorsqu'il y en a un. La boîte de dialogue n'effectue aucune fusion elle-même ; vous y
choisissez **Passer à la fusion** (qui exécute la même fusion que celle décrite ci-dessous) ou
**Fermer** pour revenir en arrière sans fusionner.

### Fusionner une branche

Sélectionnez une branche secondaire et cliquez sur **Fusionner**. Ses modifications sont fusionnées
dans la **branche principale** sans conflit, le document fusionné est chargé dans l'onglet actif, et
le panneau affiche une ligne de **résultat de la fusion** résumant ce qui s'est passé (par exemple *Branche « experiment » (12 modifications) fusionnée dans la branche principale — sans conflit.*)

> **Les fusions ne vous demandent jamais de résoudre un conflit.** Comme le modèle sous-jacent est
> commutatif et déterministe, une fusion réussit toujours et produit toujours le même résultat, quel
> que soit l'ordre dans lequel les modifications ont été faites — il n'y a aucune étape de
> résolution manuelle de conflit. Les opérations sur les branches (création, changement, fusion) relèvent de l'état de la session et **ne constituent pas** une étape de la pile d'annulation.
> **Ouvrir les différences** est facultatif — vous pouvez fusionner directement sans examiner
> d'abord les différences.

<!-- split-with: docs/site/pages/en/usage/hosting.md (that page extracts and expands this section's deployment detail; this section stays the bundle's single mention) -->

## Note à l'intention de l'opérateur : exécuter le serveur de synchronisation

La co-édition en temps réel nécessite un **serveur de synchronisation** — un petit service distinct
qui relaie et conserve durablement les modifications entre collaborateurs. Il ne fait **pas** partie
du noyau à trois couches de l'application de bureau ; il vit dans son propre paquet de premier niveau
`sync_backend/` et ne dialogue avec les clients que par le transport temps réel.

- Le serveur n'importe **aucun** code d'interface, de données ou Qt, et il ne reçoit ni ne stocke
  **jamais** les jetons de votre fournisseur cloud — ceux-ci restent dans le trousseau de clés du
  client de bureau.
- Pour le développement local et la suite de tests automatisés, le serveur est lancé **dans le même
  processus, sur un port de bouclage éphémère**, si bien que toute la boucle client ↔ serveur
  s'exécute sur `127.0.0.1`, sans réseau externe ni compte.
- Exécuter le serveur comme un service autonome, accessible par le réseau, pour une équipe répartie
  est une **question de déploiement** (hôte, port et gestion des processus), distincte de
  l'application de bureau.
- Dans cette version, l'application de bureau n'a aucune connexion configurée vers un serveur de
  synchronisation ; un serveur en cours d'exécution ne peut donc pas encore être rejoint depuis
  l'application.

Le [guide cloud](cloud-and-collaboration.md) explique que les véritables fournisseurs cloud ne
peuvent pas être sélectionnés depuis le menu Cloud dans cette version.
