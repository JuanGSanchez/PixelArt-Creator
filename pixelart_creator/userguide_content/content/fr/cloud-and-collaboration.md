# Cloud : enregistrement, versions et enregistrement automatique

Dans cette version, la **couche cloud** s'appuie sur un adaptateur intégré, en mémoire : l'historique
des versions et la copie enregistrée automatiquement ne durent donc que jusqu'à la fermeture de
l'application, et ne vous protègent ni d'un plantage ni d'une coupure de courant. Enregistrez une
copie locale du projet pour tout ce que vous voulez conserver. Dans cette limite, la couche cloud
vous permet de vous **connecter**, d'**enregistrer** le projet actuel, de l'**ouvrir** de nouveau,
de parcourir un **historique des versions** et de **restaurer** un enregistrement antérieur, et de
conserver une **copie de travail enregistrée automatiquement** pendant que vous travaillez.

Tout ce qui figure dans ce guide se pilote depuis le **menu Cloud** de la barre de menus.

> **Un seul port indépendant du fournisseur — pas d'enfermement propriétaire.** L'application ne
> dialogue jamais directement avec un fournisseur précis. Tout le travail cloud passe par **une seule
> interface indépendante du fournisseur** (le *port cloud*) : se connecter, enregistrer, ouvrir,
> lister les versions, restaurer, ainsi que l'emplacement d'enregistrement automatique et de
> récupération. L'application se comporte **de façon identique** quel que soit le fournisseur sur
> lequel elle s'appuie, de sorte que vous n'êtes pas enfermé chez un fournisseur, et qu'un nouveau
> fournisseur n'est qu'un nouvel adaptateur derrière le même port.

Ce qui fonctionne dans cette version : le port indépendant du fournisseur, un adaptateur intégré
entièrement testé, l'aller-retour cloud d'un fichier `.pixproj`, l'historique des versions avec
restauration, et l'enregistrement automatique ; les **projets partagés, commentaires et présence**,
qui s'exécutent sur un adaptateur en mémoire à l'intérieur d'une seule fenêtre de l'application (une
autre fenêtre ou la copie d'une autre personne ne peut pas les voir) ; et les **branches de
l'œuvre** locales. Ce qui ne fonctionne pas encore : les **véritables fournisseurs Google Drive /
OneDrive / Dropbox** sont implémentés dans la couche de stockage mais ne peuvent pas être
sélectionnés depuis le menu Cloud, et la **co-édition en temps réel avec curseurs en direct** ne peut
pas se connecter. Toutes ces fonctions de collaboration sont décrites dans
[Projets partagés, commentaires, présence et temps réel](collaboration.md).

## Connexion à un fournisseur cloud

Les actions cloud sont désactivées jusqu'à ce que vous vous connectiez.

1. Ouvrez le menu **Cloud**.
2. Choisissez **Se connecter…**. Cela connecte l'adaptateur intégré par le port cloud et active le
   reste du menu Cloud (**Enregistrer dans le cloud…**, **Ouvrir depuis le cloud…**,
   **Historique des versions…** et **Se déconnecter**).
3. Pour vous déconnecter, choisissez **Cloud ▸ Se déconnecter**. Cela libère la connexion et
   désactive de nouveau les actions cloud jusqu'à ce que vous vous reconnectiez.

> **Vos identifiants ne quittent jamais la couche de stockage.** Lorsqu'un adaptateur de véritable
> fournisseur est utilisé, le flux de connexion (OAuth) s'exécute **entièrement à l'intérieur de la
> couche de stockage** — l'application ne fait que lancer, pour vous, votre navigateur système. Les
> jetons ne sont **jamais** montrés à l'interface, **jamais** écrits dans un `.pixproj` et **jamais**
> écrits dans les journaux. L'interface ne voit jamais qu'un simple état *connecté / non connecté*.

> **L'adaptateur intégré.** La connexion de cette version est un adaptateur intégré, en mémoire,
> déterministe, qui n'a besoin ni de réseau ni de compte — il rend tout le flux d'enregistrement et
> de versions utilisable au sein d'une session. Comme il vit en mémoire, tout ce qu'il contient
> disparaît à la fermeture de l'application. Les véritables fournisseurs en ligne sont décrits dans
> *Connexion à un véritable fournisseur cloud* ci-dessous, mais ils ne peuvent pas être choisis
> depuis le menu Cloud dans cette version.

## Connexion à un véritable fournisseur cloud

La couche de stockage contient de **véritables** fournisseurs Google Drive, OneDrive et Dropbox, placés
derrière le **même** port cloud que l'adaptateur intégré. Lorsqu'un tel fournisseur est utilisé, les
étapes de ce guide (enregistrer, ouvrir, historique des versions) fonctionnent de la même façon,
par-dessus votre stockage en ligne. Cette version n'a aucune commande du menu Cloud qui en
sélectionne un : **Se connecter…** connecte l'adaptateur intégré.

> **Fonctionnalité conditionnée par des identifiants.** Les véritables fournisseurs sont
> **conditionnés par des identifiants** : chacun nécessiterait un **identifiant client** OAuth pour le
> service choisi et un accès réseau opérationnel, ils ne sont donc pas activés par défaut, et cette
> version n'a aucune commande du menu Cloud qui en active un. L'adaptateur intégré décrit plus haut
> n'a besoin de rien de tout cela.

### Comment fonctionne la connexion

1. Utiliser un fournisseur de la couche de stockage lance sa procédure de connexion. **Cloud ▸ Se
   connecter…** ne le fait pas dans cette version : il connecte l'adaptateur intégré.
2. La connexion ouvre votre **navigateur système** sur la page de connexion / de consentement du
   fournisseur. PixelArt Creator utilise le flux de bureau standard **OAuth Authorization Code +
   PKCE avec redirection vers l'adresse de bouclage** — il n'y a **aucune vue web intégrée** et
   **aucun secret client** stocké dans l'application.
3. Approuvez l'accès dans le navigateur. Le navigateur redirige vers l'application, qui termine la
   connexion. Les actions d'enregistrement, d'ouverture et de version du menu Cloud s'activent alors,
   comme pour l'adaptateur intégré.
4. Pour vous déconnecter, choisissez **Cloud ▸ Se déconnecter**.

> **Vos identifiants ne quittent jamais la couche de stockage.** Toute la connexion s'exécute
> **entièrement à l'intérieur de la couche de stockage**. Votre **jeton d'actualisation est stocké
> dans le trousseau de clés du système d'exploitation** (une entrée par fournisseur) ; le jeton
> d'accès, de courte durée, n'est conservé qu'en mémoire et actualisé automatiquement. Les jetons
> ne sont **jamais** montrés à l'interface, écrits dans un `.pixproj` ou écrits dans les journaux.

> **Même comportement, quel que soit le fournisseur.** Comme chaque fournisseur se trouve derrière
> le même port cloud, enregistrer et parcourir les versions fonctionnent de la même manière, que ce
> soit l'adaptateur intégré ou Drive / OneDrive / Dropbox qui les assure. C'est la conception sans
> enfermement propriétaire ; choisir un fournisseur depuis le menu Cloud n'est pas disponible dans
> cette version.

## Enregistrer un projet dans le cloud

1. Avec un projet ouvert et un fournisseur connecté, choisissez **Cloud ▸ Enregistrer dans le
   cloud…**.
2. Lorsque l'invite **Nom du projet cloud** s'affiche, saisissez un nom. C'est la clé sous laquelle votre
   projet est stocké ; réutilisez le même nom pour continuer à ajouter des versions au même projet.
3. L'application sérialise le projet en un `.pixproj` et le stocke comme une **nouvelle version**.
   Quand l'opération est terminée, la barre d'état affiche *« Enregistré dans le cloud. »*

Chaque enregistrement est transporté sous la forme d'un `.pixproj` entier — le **même** format
d'enregistrement validé et versionné que celui des fichiers locaux. La couche cloud n'ajoute aucun
format qui lui soit propre ; elle se contente de transporter le `.pixproj` comme *unité de
synchronisation* atomique.

> **L'enregistrement ne fige jamais l'application.** La sérialisation et l'envoi s'exécutent **hors
> du fil d'exécution de l'interface**, de sorte que la fenêtre reste réactive même pour un grand projet
> (jusqu'à 8K) — vous pouvez continuer à travailler pendant qu'un enregistrement se termine.

> **Chaque enregistrement est une nouvelle version.** Enregistrer n'écrase **pas** l'enregistrement
> cloud précédent — cela ajoute une nouvelle entrée à l'historique des versions. L'historique est
> plafonné aux **100** versions les plus récentes par projet.

## Ouvrir un projet depuis le cloud

1. Choisissez **Cloud ▸ Ouvrir depuis le cloud…**.
2. Dans l'invite **Nom du projet cloud**, saisissez le nom du projet à ouvrir.
3. L'application récupère la dernière version du projet et l'ouvre dans un **nouvel onglet**.

L'ouverture ne remplace **pas** et ne perturbe pas ce sur quoi vous travaillez actuellement — le
projet cloud arrive dans son propre onglet.

> **Les fichiers du cloud sont traités comme non fiables.** Un `.pixproj` récupéré depuis le cloud
> est validé de façon défensive exactement comme un fichier local : chaque champ est contrôlé en type
> et en bornes, la taille des données est plafonnée, et un fichier mal formé, trop volumineux ou de
> version inconnue est rejeté avec une **erreur claire** — jamais par un plantage et **jamais** en
> exécutant du code issu du fichier. Si un projet récupéré ne peut pas être validé, une boîte de
> dialogue d'avertissement s'affiche et votre travail en cours reste intact.

## Parcourir l'historique des versions et restaurer une version

Chaque enregistrement crée une nouvelle version, ordonnée, et vous pouvez revenir à n'importe
laquelle. L'historique des versions ne dure que pour la session en cours : l'adaptateur intégré le
conserve en mémoire et il repart vide au prochain lancement de l'application. Enregistrez une copie
locale du projet pour tout ce que vous voulez conserver.

1. Choisissez **Cloud ▸ Historique des versions…** (si vous n'avez pas ouvert ni enregistré de
   projet cloud pendant cette session, le nom du projet cloud vous sera d'abord demandé).
2. La boîte de dialogue **Historique des versions du cloud** liste toutes les versions stockées, de
   la plus ancienne à la plus récente, avec ces colonnes :
    - **Version** — le numéro d'ordre / l'identifiant de la version.
    - **Marqueur** — le marqueur d'ordre de la version.
    - **Taille (octets)** — la taille du `.pixproj` stocké.
    - **Épinglée** — indique si la version est épinglée (conservée) — *Oui* / *Non*.
    - **Parent** — la version que cet enregistrement suivait.
3. Sélectionnez une version pour voir ses détails dans la zone d'aperçu sous la liste.
4. Cliquez sur **Restaurer** (ou double-cliquez sur la ligne, ou appuyez sur **Enter**) pour
   ramener cette version.

> **Restaurer est sans danger — cela ouvre un nouvel onglet.** Restaurer une version antérieure la
> récupère et la valide, puis l'ouvre dans un **nouvel onglet**. Cela n'écrase **pas** votre travail
> en cours ni votre dernier enregistrement cloud — c'est à vous de décider ce que vous faites de la
> copie restaurée.

La liste des versions est récupérée hors du fil d'exécution de l'interface avant l'ouverture de la boîte de
dialogue ; parcourir l'historique ne fige donc jamais l'application.

## Enregistrement automatique et emplacement de récupération

Pendant que vous travaillez sur un projet connecté, l'application **enregistre automatiquement**
votre copie de travail, en arrière-plan, dans un **emplacement de récupération** dédié. Dans cette
version, l'emplacement n'est conservé qu'en mémoire : il protège votre travail au sein de la
session, pas d'un plantage.

- L'enregistrement automatique s'exécute à une cadence fixe (par défaut **toutes les 2 minutes**) et
  **seulement lorsque le document a des modifications non enregistrées** — un document propre n'est
  jamais enregistré automatiquement.
- L'emplacement de récupération est **séparé de votre historique des versions**.
  L'enregistrement automatique ne crée jamais de version visible et **n'écrase jamais votre dernier
  enregistrement manuel dans le cloud**.
- L'enregistrement automatique s'exécute hors du fil d'exécution de l'interface ; il n'interrompt donc
  jamais votre dessin.

### L'invite de récupération au redémarrage

La récupération au redémarrage n'est pas disponible dans cette version. L'adaptateur intégré ne
conserve pas l'emplacement de récupération d'un redémarrage à l'autre, et l'invite **Récupérer le
travail non enregistré** n'est vérifiée qu'une seule fois, au démarrage de l'application, avant que
vous puissiez vous connecter. Après un plantage ou une coupure de courant, aucune invite n'apparaît
au prochain démarrage de l'application. Tant qu'un fournisseur persistant ne peut pas être
sélectionné, fiez-vous à l'enregistrement d'une copie locale du projet.

L'invite elle-même propose deux choix (vous ne la verrez pas dans cette version) :

- **Récupérer** — va chercher la copie enregistrée automatiquement, la valide et l'ouvre dans un
  **nouvel onglet**. Votre dernier enregistrement manuel n'est pas affecté.
- **Abandonner** — ferme l'invite et laisse tout en l'état.

> **La récupération est elle aussi décodée de façon défensive.** La copie récupérée passe par la
> même validation d'entrée non fiable que tout fichier du cloud : un emplacement de récupération mal
> formé est donc rejeté avec une erreur claire au lieu d'être ouvert.

> **L'enregistrement automatique a besoin d'une connexion.** L'enregistrement automatique passe par
> le port cloud ; il ne s'exécute donc que lorsque vous êtes **connecté**. Il protège votre travail
> au sein de la session, pas d'un plantage.

## Le reste du jalon cloud et collaboration

Cette page couvre le travail cloud à un seul utilisateur — enregistrement, versions, enregistrement
automatique — ainsi que les fournisseurs de la couche de stockage. Les fonctions de collaboration
(sur leur propre adaptateur en mémoire, par fenêtre de l'application, dans cette version ; la
co-édition en temps réel et les curseurs en direct ne peuvent pas se connecter) — **projets partagés et gestion des membres**, **commentaires**, **présence**, **convergence déterministe**, **co-édition en temps
réel et curseurs en direct** et **branches de l'œuvre** — sont toutes décrites dans
[Projets partagés, commentaires, présence et temps réel](collaboration.md).
