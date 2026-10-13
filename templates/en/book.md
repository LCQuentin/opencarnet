# {nom}

{#if title|author|year|genre|isbn}{#if title}- **Title**: {title}
{/if}{#if author}- **Author**: {author}
{/if}{#if year}- **Year**: {year}
{/if}{#if genre}- **Genre**: {genre}
{/if}{#if isbn}- **ISBN**: {isbn}
{/if}
{/if}## Why read it
{why|ou:resume|defaut:- }

{#if key_ideas}## Key ideas
{key_ideas|liste}

{/if}{#if citation_cle}> "{citation_cle}"

{/if}## Source
- {source_url}
{liens|liste}
