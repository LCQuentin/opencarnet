[English](README.md) · **Français**

# OpenCarnet

> Transforme les reels et posts Instagram que vous enregistrez en un carnet de notes propre et rangé, au lieu d'une longue liste de liens que vous ne rouvrez jamais.

Vous enregistrez des reels. Ils s'entassent. Ce que vous vouliez retenir se perd : un outil, une astuce, une adresse, un livre, un prompt. Tout finit dans une grille de vignettes qu'on ne parcourt plus. OpenCarnet récupère cette matière et la range pour vous, dans le carnet que vous utilisez déjà (Obsidian, Notion, un simple dossier de notes).

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

## Pour commencer

```bash
# 0. récupérer OpenCarnet
git clone https://github.com/LCQuentin/opencarnet
cd opencarnet

# 1. installer les 3 outils gratuits
brew install yt-dlp ffmpeg
python3 -m pip install --user faster-whisper "av==13.1.0"
python3 -m pip install --user instaloader

# 2. récupérer la liste de vos enregistrements
python3 scripts/parse_meta_export.py "~/Downloads/instagram-export/" --out items.csv
```

Ensuite, pour chaque contenu : OpenCarnet le télécharge, le transcrit, l'assemble, puis l'assistant IA le transforme en fiche. Le détail des commandes est plus bas, dans « Pour aller plus loin ».

## Où vont vos notes (les réglages)

OpenCarnet ne décide pas à votre place où ranger vos notes. Vous le lui dites, dans **un petit fichier de réglages** que vous écrivez une fois.

Vous y précisez par exemple :
- le dossier où vont les fiches (Obsidian, Notion, un dossier…),
- comment nommer les fiches,
- quels mots-clés ajouter,
- où mettre de côté les fiches douteuses.

Un réglage prêt à l'emploi est fourni (`config.example.json`). Vous le copiez et vous l'adaptez. C'est ce qui rend OpenCarnet utilisable avec **n'importe quel carnet**, sans rien réécrire.

## Comment ça se compare

La plupart des outils du secteur sont des applications fermées (Resurfy, SocialMarks, Recall, Fabric…) qui rangent vos enregistrements **dans leur application**, avec un abonnement. D'autres sont ouverts mais ne savent ranger qu'à **un seul endroit** (un carnet précis, une base précise).

OpenCarnet fait autrement :
- **il range où vous voulez** (Obsidian, Notion, un dossier, une base),
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
- [ ] **YouTube** : vos « J'aime » et vos playlists.

## Licence

MIT, voir `LICENSE`.
