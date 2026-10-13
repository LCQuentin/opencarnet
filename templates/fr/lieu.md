# {nom}

{resume}

{#if categorie_lieu|adresse|ville|google_maps|coordonnees|budget|site}{#if categorie_lieu}- **Type** : {categorie_lieu}
{/if}{#if adresse}- **Adresse** : {adresse}
{/if}{#if ville}- **Ville** : {ville}{#if pays}, {pays}{/if}
{/if}{#if google_maps}- **Carte** : [Ouvrir dans Google Maps]({google_maps})
{/if}{#if coordonnees}- **GPS** : {coordonnees}{#if precision_gps} (précision : {precision_gps}){/if}
{/if}{#if budget}- **Budget** : {budget}
{/if}{#if site}- **Site / compte** : {site}
{/if}
{/if}{#if description}## À propos
{description}

{/if}{#if a_essayer}## À essayer
{a_essayer|liste}

{/if}{#if infos_pratiques}## Infos pratiques
{infos_pratiques|liste}

{/if}## Exploitation possible
{exploitation|liste|defaut:- }

{#if illustrations}{illustrations|embed}

{/if}## Source
- {source_url}
{liens|liste}
