# {nom}

{#if titre|auteur|annee|genre|isbn}{#if titre}- **Titre** : {titre}
{/if}{#if auteur}- **Auteur** : {auteur}
{/if}{#if annee}- **Année** : {annee}
{/if}{#if genre}- **Genre** : {genre}
{/if}{#if isbn}- **ISBN** : {isbn}
{/if}
{/if}## Pourquoi le lire
{pourquoi|ou:resume|defaut:- }

{#if idees_cles}## Idées clés
{idees_cles|liste}

{/if}{#if citation_cle}> « {citation_cle} »

{/if}## Source
- {source_url}
{liens|liste}
