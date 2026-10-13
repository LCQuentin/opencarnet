[English](README.md) · **Français**

# OpenCarnet

> Transforme les reels et posts Instagram que vous enregistrez en un carnet de notes propre et rangé, au lieu d'une longue liste de liens que vous ne rouvrez jamais.

Vous enregistrez des reels. Ils s'entassent. Ce que vous vouliez retenir se perd : un outil, une astuce, une adresse, un livre, un prompt. Tout finit dans une grille de vignettes qu'on ne parcourt plus. OpenCarnet récupère cette matière et la range pour vous, dans le carnet que vous utilisez déjà (Obsidian, Notion, un simple dossier de notes).

> **Note de l'auteur.** Je n'ai pas testé cet outil sous cette forme packagée : c'est un dérivé de ma façon de faire, mise en boîte et simplifiée. Ce n'est pas parfait, et c'est améliorable. Des aspérités peuvent subsister. Je suis ouvert à toutes vos suggestions d'amélioration.

## Pourquoi ça marche

Un reel, ça n'est pas du texte. L'information utile est éparpillée à trois endroits :

- ce qui est raconté à l'oral,
- ce qui est écrit à l'écran (texte, interface, code),
- la légende.

OpenCarnet réunit ces trois morceaux, en fait une fiche lisible, et la range. On ne classe jamais sur la seule légende : sans le son et l'image, on passe à côté de l'essentiel.

## Comment ça se passe

Trois étapes, une seule commande par étape :

1. **Récupérer la liste** de vos enregistrements (depuis l'export officiel de vos données Instagram ou X, ou une simple liste de liens).
2. **Lire chaque contenu** : OpenCarnet télécharge la vidéo, transcrit ce qui est dit, et lit le texte à l'écran.
3. **Ranger** : votre assistant IA en tire une fiche courte (de quoi il s'agit, les détails utiles, le lien vers l'original), puis OpenCarnet la range à sa place, sans doublon.

## Ce qu'il vous faut

- Un ordinateur Mac ou Linux.
- Un assistant IA que vous utilisez déjà (Claude Code, Cursor, ChatGPT avec des extensions, etc.).
- Trois outils gratuits, à installer en une commande chacun (indiqué plus bas).

Pas besoin de savoir programmer. Vous copiez des commandes dans un terminal, c'est tout.

## Vous n'y connaissez rien ? Passez par votre IA

OpenCarnet contient un mode d'emploi écrit pour les assistants IA (`SKILL.md`). Vous pouvez donc simplement **donner le lien du dépôt à votre IA** (Claude, ChatGPT, Cursor…), et lui demander de vous expliquer ou de le faire pour vous.

Exemples de messages à lui envoyer :
- « Voici un projet GitHub : [lien]. Explique-moi ce qu'il fait et comment l'utiliser. »
- « Installe et configure ce projet pour moi, étape par étape. »
- « Voici mes exports Instagram et X. Mets en place ce projet et range mes enregistrements dans mon carnet Obsidian. »

En clair : si vous savez copier un lien, vous savez utiliser OpenCarnet.

## Récupérer vos données Instagram

C'est l'étape 1, et la seule vraiment manuelle. Vous demandez à Instagram une copie de vos données, puis vous récupérez le fichier.

Commencez par là : Instagram met parfois quelques heures (parfois un jour ou deux) à préparer le fichier.

1. Dans l'application Instagram : **Paramètres**, puis **Centre de comptes** (tout en haut).
2. **Vos informations et autorisations** → **Exporter vos informations**.
3. **Créer une exportation**, choisissez votre profil, puis **Exporter vers un appareil**.
4. Dans le choix du contenu, sélectionnez **« Certaines de vos informations »** et cochez seulement **Enregistrements** (Saved) et, si vous le souhaitez, **J'aime** (Likes). Inutile d'exporter le reste.
5. **Format** : JSON. **Période** : tout l'historique.
6. Lancez l'exportation. Instagram vous envoie un lien par e-mail quand c'est prêt.

Important : le lien de téléchargement **expire en quelques jours**. Téléchargez le fichier et rangez-le dans vos Documents.

Vous obtiendrez un dossier contenant `saved_posts.json` (vos enregistrements) et, si vous l'avez coché, `liked_posts.json` (vos « J'aime »). C'est ce dossier que vous donnerez à OpenCarnet.

> Si vous ne voulez traiter que vos enregistrements, cochez uniquement **Enregistrements** : c'est le fichier `saved_posts.json` qui compte.

### Et vos données X / Twitter

Même principe pour X (Twitter) : vous téléchargez l'archive de vos données, et OpenCarnet en tire vos « J'aime » et vos signets.

1. Sur x.com : menu **Plus**, puis **Paramètres et confidentialité** → **Votre compte** → **Télécharger une archive de vos données**.
2. Confirmez, puis demandez l'archive. X vous prévient quand elle est prête (souvent sous 24 h).
3. Téléchargez le fichier `.zip`. Il contient un dossier `data/` avec vos « J'aime » (`like.js`) et, si vous les utilisez, vos signets.

Puis :

```bash
python3 scripts/parse_x_export.py "~/Downloads/twitter-archive.zip" --out items-x.csv
```

Sur X, la plupart des posts sont du texte : le contenu est déjà dans l'export. Vous pouvez donc souvent sauter le téléchargement et la transcription, et passer directement à l'analyse.

### TikTok, LinkedIn, YouTube (support en cours)

Ces trois sources arrivent (voir la feuille de route). Vous pouvez déjà préparer vos exports dès maintenant.

**TikTok**
1. Profil → menu ☰ → **Paramètres et confidentialité**.
2. **Compte** → **Télécharger vos données**.
3. Choisissez « All data » (ou au minimum **Activity**), format **JSON**.
4. Demandez, puis téléchargez sous ~4 jours. Vous obtiendrez vos favoris et vos « J'aime » (date + lien).

**LinkedIn** (sur ordinateur uniquement)
1. Icône **Moi** → **Paramètres et confidentialité**.
2. **Confidentialité des données** → **Télécharger vos données**.
3. Cochez **Saved Items** → **Demander l'archive**.
4. Téléchargez le fichier (lien valable 72 h). Vous obtiendrez `Saved Items.csv` (lien + date).

**YouTube**
1. Allez sur `takeout.google.com`.
2. Décochez tout, puis cochez **YouTube and YouTube Music**.
3. Cochez au minimum **playlists** (contient vos vidéos aimées) et **history**.
4. Créez l'export. Google vous envoie un lien par e-mail. Vous obtiendrez surtout des identifiants de vidéos (et des dates), pas les vidéos.

## Pour commencer

```bash
# 0. récupérer OpenCarnet
git clone https://github.com/LCQuentin/opencarnet
cd opencarnet

# 1. installer les 3 outils gratuits
brew install yt-dlp ffmpeg
python3 -m pip install --user faster-whisper "av==13.1.0"
python3 -m pip install --user instaloader

# 2. le configurer — quelques questions (votre outil de notes, où ranger, la langue)
python3 scripts/compile.py --init

# 3. récupérer la liste de vos enregistrements
python3 scripts/parse_meta_export.py "~/Downloads/instagram-export/" --out items.csv
```

Ensuite, pour chaque contenu : OpenCarnet le télécharge, le transcrit, l'assemble, puis l'assistant IA le transforme en fiche. Le détail des commandes est plus bas, dans « Pour aller plus loin ».

## Où vont vos notes (les réglages)

OpenCarnet ne décide pas à votre place où ranger vos notes. Vous le lui dites, dans **un petit fichier de réglages** que vous écrivez une fois.

Vous y précisez par exemple :
- le dossier où vont les fiches (Obsidian, Logseq, n'importe quel dossier Markdown…),
- comment nommer les fiches,
- quels mots-clés ajouter,
- où mettre de côté les fiches douteuses.

`--init` écrit ce fichier de réglages pour vous à partir d'un **preset** (dossier Markdown, Obsidian ou Logseq), et copie les modèles de fiches pour que vous puissiez les modifier. Vous préférez le faire à la main ? Un exemple neutre est fourni (`config.example.json`) — copiez-le et adaptez-le. Dans tous les cas, OpenCarnet marche avec **n'importe quel carnet**, sans rien réécrire.

Vous préférez un tableau (une base Notion, Airtable, Google Sheets) à des fiches séparées ? Réglez `output` sur `csv` ou `jsonl` dans le même fichier : vos enregistrements arrivent dans un fichier unique, prêt à importer.

### Des fiches mises en forme selon leur contenu

Une recette ne ressemble pas à un outil, et un restaurant ne ressemble pas à un livre. OpenCarnet donne à chacun sa mise en forme :
- **recette** : portions, temps de préparation / cuisson / total, ingrédients avec quantités, ustensiles, étapes numérotées ;
- **lieu** : adresse, **lien Google Maps** prêt à cliquer, **coordonnées GPS** en option (pour voir vos lieux sur une carte) ;
- **ressource web** : le lien de l'outil lui-même, son modèle de prix, ses plateformes, ce qu'il permet ;
- **livre**, **film / série**, **produit** (avec la date à laquelle le prix a été relevé).

Les temps et les portions sont de vrais nombres : vous pouvez filtrer (« recettes de moins de 30 minutes »). Les mises en forme sont de simples modèles Markdown, à copier et modifier. Ce que l'IA pourrait inventer (coordonnées, liens de carte, totaux) est calculé, jamais deviné.

## Comment ça se compare

La plupart des outils du secteur sont des applications fermées (Resurfy, SocialMarks, Recall, Fabric…) qui rangent vos enregistrements **dans leur application**, avec un abonnement. D'autres sont ouverts mais ne savent ranger qu'à **un seul endroit** (un carnet précis, une base précise).

OpenCarnet fait autrement :
- **il range où vous voulez** (Obsidian, Logseq, n'importe quel dossier Markdown),
- **il tourne avec votre assistant IA**, pas avec une IA payante à part,
- **il ne vous enferme pas** : pas de compte, pas d'abonnement,
- **tout reste chez vous**.

## Ce qu'OpenCarnet ne fait pas

- Les posts **privés ou supprimés** ne peuvent pas être récupérés. Ils sont simplement ignorés.
- Si un contenu est illisible (audio de mauvaise qualité), la fiche est **mise de côté** plutôt qu'inventée. On ne devine pas.
- OpenCarnet ne recopie pas un contenu payant : il garde un lien et une courte citation.

## Pour aller plus loin

Les détails techniques (les commandes complètes, le schéma des fiches, les réglages avancés) sont ici :

- `reference/extraction-schema.md` : ce que contient chaque fiche.
- `reference/configuration.md` : tous les réglages possibles.
- `scripts/` : les outils, un par étape.

## Feuille de route

- [x] **X / Twitter** : vos « J'aime » et vos signets, mêmes fiches que pour Instagram.
- [ ] **TikTok** : vos vidéos favorites.
- [ ] **LinkedIn** : vos éléments enregistrés.
- [ ] **YouTube** : vos « J'aime » et vos playlists.

## Licence

MIT, voir `LICENSE`.
