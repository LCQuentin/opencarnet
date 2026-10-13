# {nom}

{#if titre|type_oeuvre|realisation|annee|genre|plateforme}{#if titre}- **Titre** : {titre}
{/if}{#if type_oeuvre}- **Type** : {type_oeuvre}
{/if}{#if realisation}- **Réalisation** : {realisation}
{/if}{#if annee}- **Année** : {annee}
{/if}{#if genre}- **Genre** : {genre}
{/if}{#if plateforme}- **Où le voir** : {plateforme}
{/if}
{/if}## Pitch
{pitch|ou:resume|defaut:- }

{#if pourquoi}## Pourquoi le voir
{pourquoi}

{/if}## Source
- {source_url}
{liens|liste}
