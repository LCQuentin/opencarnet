# {nom}

{resume}

{#if brand|model|price|link}{#if brand}- **Brand**: {brand}
{/if}{#if model}- **Model**: {model}
{/if}{#if price}- **Price**: {price} (seen on {price_seen_on})
{/if}{#if link}- **Link**: {link}
{/if}
{/if}{#if pros}## Pros
{pros|liste}

{/if}{#if cons}## Cons
{cons|liste}

{/if}{#if alternatives}## Alternatives
{alternatives|liste}

{/if}{#if illustrations}{illustrations|embed}

{/if}## Source
- {source_url}
{liens|liste}
