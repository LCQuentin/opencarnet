# {nom}

{#if title|work_type|director|year|genre|platform}{#if title}- **Title**: {title}
{/if}{#if work_type}- **Type**: {work_type}
{/if}{#if director}- **Director**: {director}
{/if}{#if year}- **Year**: {year}
{/if}{#if genre}- **Genre**: {genre}
{/if}{#if platform}- **Where to watch**: {platform}
{/if}
{/if}## Pitch
{pitch|ou:resume|defaut:- }

{#if why}## Why watch it
{why}

{/if}## Source
- {source_url}
{liens|liste}
