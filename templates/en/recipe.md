# {nom}

{resume}

| Servings | Prep | Cook | Rest | Total |
|---|---|---|---|---|
| {servings|defaut:—} | {prep_time|minutes|ou:prep_time_texte|defaut:—} | {cook_time|minutes|ou:cook_time_texte|defaut:—} | {rest_time|minutes|ou:rest_time_texte|defaut:—} | {total_time|minutes|defaut:—} |

{#if temperature|difficulty|diet}{#if temperature}- **Temperature**: {temperature}
{/if}{#if difficulty}- **Difficulty**: {difficulty}
{/if}{#if diet}- **Diet**: {diet}
{/if}
{/if}## Ingredients
{ingredients|liste|defaut:- }

{#if tools}## Tools
{tools|liste}

{/if}## Steps
{steps|numerote|defaut:1. }

{#if tips}## Tips
{tips|liste}

{/if}{#if nutrition}## Nutrition
{nutrition}

{/if}{#if illustrations}{illustrations|embed}

{/if}## Source
- {source_url}
{liens|liste}
