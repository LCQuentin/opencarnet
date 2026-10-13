# {nom}

{resume}

| Portions | Préparation | Cuisson | Repos | Total |
|---|---|---|---|---|
| {portions|defaut:—} | {temps_preparation|minutes|ou:temps_preparation_texte|defaut:—} | {temps_cuisson|minutes|ou:temps_cuisson_texte|defaut:—} | {temps_repos|minutes|ou:temps_repos_texte|defaut:—} | {temps_total|minutes|defaut:—} |

{#if temperature|difficulte|regime}{#if temperature}- **Température** : {temperature}
{/if}{#if difficulte}- **Difficulté** : {difficulte}
{/if}{#if regime}- **Régime** : {regime}
{/if}
{/if}## Ingrédients
{ingredients|liste|defaut:- }

{#if ustensiles}## Ustensiles
{ustensiles|liste}

{/if}## Étapes
{etapes|numerote|defaut:1. }

{#if astuces}## Astuces
{astuces|liste}

{/if}{#if nutrition}## Valeurs nutritionnelles
{nutrition}

{/if}{#if illustrations}{illustrations|embed}

{/if}## Source
- {source_url}
{liens|liste}
