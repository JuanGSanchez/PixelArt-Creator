<!-- site-counterpart: docs/site/pages/en/usage/ai-assistant.md (derived FROM this bundle file, reverse direction) -->
# L'assistant IA : piloter l'éditeur par la conversation

L'**assistant IA** vous permet de piloter l'éditeur en **langage courant**. Vous écrivez ce que
vous voulez dans un panneau de discussion, et l'assistant l'exécute en lançant les **propres**
opérations de l'application — les mêmes commandes d'[automatisation](automation-and-scripting.md)
que vous pouvez capturer, scripter et traiter par lot à la main. Il est **indépendant du
modèle** : vous le pointez vers le fournisseur d'IA de votre choix et vous fournissez votre propre
clé. Il est aussi **facultatif** — l'application est pleinement utilisable sans jamais le
configurer.

> **L'assistant agit par la couche d'automatisation sûre — rien de nouveau n'est exposé.**
> Chaque action de l'assistant est une opération ordinaire de l'éditeur, figurant sur la liste
> d'autorisation, envoyée par la **même couche de commandes de confiance, sans `eval`**, que
> celle des macros et des scripts. Il ne peut ni exécuter du code arbitraire, ni dépasser cette
> couche de commandes, ni inventer de nouveaux pouvoirs — un message de discussion est une
> **donnée**, jamais une autorisation de faire ce que l'éditeur ne pourrait pas déjà faire en
> toute sécurité.

## Ouvrir l'assistant

Ouvrez le panneau de discussion depuis **Aide ▸ Assistant IA**. Il apparaît sous la forme d'un
**panneau ancrable** que vous pouvez placer à côté du canvas, pour voir l'assistant travailler
pendant que votre œuvre reste visible. Le panneau affiche la conversation en cours — vos
messages, les réponses de l'assistant et les modifications qu'il apporte au document.

Avant que l'assistant puisse parler à un fournisseur, vous devez d'abord **en configurer un**
(ci-dessous). D'ici là, il indique clairement **qu'aucun fournisseur n'est configuré**, au lieu d'échouer —
configurer un fournisseur est une étape à faire une seule fois.

## Configurer un fournisseur et une clé

Ouvrez la boîte de dialogue de configuration du fournisseur avec le bouton **Configurer…** du
panneau Assistant IA. L'assistant étant **indépendant du modèle**, vous choisissez le service et
le modèle qui vous conviennent et vous saisissez :

| Champ | Que saisir |
| --- | --- |
| **Fournisseur** | Soit un service **Compatible OpenAI**, soit **Anthropic (Claude)**. L'option compatible OpenAI couvre un large éventail de points de terminaison (OpenAI lui-même, le point de terminaison compatible OpenAI de Gemini, et des environnements locaux tels qu'Ollama ou llama.cpp) ; l'option Anthropic dialogue nativement avec Claude. |
| **URL du point de terminaison** | Le point de terminaison d'API du service. Pointez-le vers un fournisseur hébergé ou vers un serveur de modèle local sur votre propre machine. |
| **Modèle** | Le nom du modèle à utiliser, tel que votre fournisseur le désigne. |
| **Clé d'API** | Votre clé pour le fournisseur. Une clé doit être enregistrée même pour un serveur de modèle local : l'assistant ne considère un fournisseur comme configuré que lorsqu'un point de terminaison et une clé non vide sont tous deux enregistrés, et il envoie ce que vous saisissez sans le vérifier. Si votre serveur local ne vérifie pas les clés, saisissez n'importe quel texte non vide qu'il accepte. |

Cliquez sur **Enregistrer** pour stocker les paramètres du fournisseur.

> **Votre clé est stockée de façon sécurisée — jamais dans votre projet.** La clé d'API que vous
> saisissez est remise au **magasin sécurisé d'identifiants du système d'exploitation (le
> trousseau de clés du système)**. Elle n'est **jamais écrite dans votre fichier de projet
> `.pixproj`, jamais journalisée, et ne voyage jamais avec un projet partagé ou exporté**.
> Partager un projet ne partage donc jamais votre clé. L'accès réel à la clé repose sur un extra
> facultatif (`pip install ".[assistant_live]"`) ; voir le README.

> **Identifiants facultatifs.** L'assistant est entièrement facultatif : vous ne l'activez que si
> vous le décidez. Si vous ne configurez jamais de fournisseur, rien ne change dans le reste de
> l'éditeur — vous n'utilisez simplement pas l'assistant. Il n'y a aucune connexion obligatoire, et
> aucune clé n'est requise pour utiliser PixelArt Creator.

## Discuter pour piloter le flux de travail

Une fois les paramètres d'un fournisseur enregistrés (un point de terminaison et une clé d'API
conservée dans votre trousseau de clés), saisissez une demande en langage naturel — par exemple,
demander à l'assistant de recolorer une région ou de générer du contenu procédural — et envoyez-la.
L'assistant interprète votre demande, décide quelles opérations de l'éditeur permettent de
l'accomplir, puis les exécute, en indiquant dans la conversation ce qu'il a fait. Comme il pilote
les opérations **réelles** de l'éditeur, les résultats sont exactement ceux que vous obtiendriez en
effectuant ces étapes vous-même.

Un aller-retour avec le modèle s'exécute sur une **tâche d'arrière-plan**, si bien que la fenêtre
reste réactive pendant que l'assistant réfléchit.

## Sécurité à deux niveaux — les actions réversibles s'appliquent seules, les actions destructrices demandent d'abord

L'assistant range chaque action qu'il veut entreprendre dans l'un de deux niveaux, et le niveau
détermine si elle nécessite votre confirmation. Cette barrière réside dans le code même de
l'application : ce n'est **pas** quelque chose que décide le modèle d'IA, et aucune formulation
dans un message de discussion ne peut convaincre l'éditeur d'y renoncer.

- **Les actions réversibles s'appliquent immédiatement.** Une action qui va sur la
  [pile d'annulation](app-basics.md) normale comme une étape unique, proprement annulable (comme
  une recoloration par lot ou un remplissage procédural), est **appliquée sans demander**. Vous la
  voyez se produire dans le document, et vous pouvez l'**annuler** comme n'importe quelle autre
  modification.
- **Les actions destructrices demandent d'abord.** Tout ce qui ne figure pas sur la liste des
  actions réversibles est traité comme **destructeur par défaut**, et l'assistant **se met en
  pause pour vous demander**, en nommant l'action exacte. Elle ne s'exécute **que** si vous
  confirmez, et elle est abandonnée dans le cas contraire — une action destructrice n'est jamais
  appliquée en silence.

> **Sûr par défaut.** La barrière est réglée par défaut sur *demander* pour tout ce dont elle n'est
> pas certaine qu'il soit proprement réversible. Ainsi, une action nouvelle ou inhabituelle
> ne peut jamais passer et s'exécuter toute seule simplement parce que personne ne l'a classée — le
> niveau réversible est un petit ensemble explicite, et tout le reste mérite une invite de
> confirmation.

## Ce que l'assistant ne fera pas

- **Il ne peut pas exécuter de code arbitraire.** L'assistant ne pilote que les opérations de
  l'éditeur figurant sur la liste d'autorisation, via la couche de commandes de confiance ; il n'y
  a ni `eval` ni `exec` sur ce chemin, exactement comme pour les
  [macros et les scripts](automation-and-scripting.md).
- **Il ne peut pas contourner la barrière de confirmation.** Aucune instruction — y compris une
  instruction qui arrive à l'intérieur d'un résultat d'outil — ne peut faire sauter sa
  confirmation à une action destructrice, et aucune opération non autorisée ne peut être exécutée
  simplement parce que la conversation le demande.
- **Il ne divulgue jamais votre clé.** Vos identifiants restent dans le trousseau de clés du système
  et ne servent qu'à dialoguer avec le fournisseur que vous avez configuré.

## Accessibilité, thèmes et langue

Chaque contrôle du panneau de l'assistant et de la boîte de dialogue du fournisseur porte un nom accessible et s'utilise au clavier, tous les libellés peuvent être entièrement traduits et se retraduisent en direct quand vous changez de langue, et les deux surfaces s'affichent
correctement dans les thèmes clair et sombre.

## Sujets connexes

- L'assistant pilote les mêmes opérations que le reste du
  [système d'automatisation](automation-and-scripting.md) — macros, scripts, recoloration par lot
  et génération procédurale.
- La configuration d'un fournisseur suit le même principe que celle des véritables fournisseurs de la couche de [stockage cloud](cloud-and-collaboration.md) (non sélectionnables depuis le menu Cloud dans cette version) : des identifiants facultatifs, conservés dans le trousseau de clés.
