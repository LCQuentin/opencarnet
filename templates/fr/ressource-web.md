# {nom}

{resume}

{#if url|categorie_ressource|modele_prix|plateformes}{#if url}- **Lien** : {url}
{/if}{#if categorie_ressource}- **Type** : {categorie_ressource}
{/if}{#if modele_prix}- **Modèle** : {modele_prix}{#if prix} ({prix}){/if}
{/if}{#if plateformes}- **Plateformes** : {plateformes}
{/if}
{/if}{#if fonctionnalites}## Fonctionnalités
{fonctionnalites|liste}

{/if}{#if utilisation}## Utilisation
{utilisation|numerote}

{/if}{#if alternatives}## Alternatives
{alternatives|liste}

{/if}## Exploitation possible
{exploitation|liste|defaut:- }

## Source
- {source_url}
{liens|liste}
