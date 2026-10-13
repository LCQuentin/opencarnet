# {nom}

{resume}

{#if url|resource_type|pricing|platforms}{#if url}- **Link**: {url}
{/if}{#if resource_type}- **Type**: {resource_type}
{/if}{#if pricing}- **Pricing**: {pricing}{#if price} ({price}){/if}
{/if}{#if platforms}- **Platforms**: {platforms}
{/if}
{/if}{#if features}## Features
{features|liste}

{/if}{#if how_to}## How to use
{how_to|numerote}

{/if}{#if alternatives}## Alternatives
{alternatives|liste}

{/if}## Possible uses
{exploitation|liste|defaut:- }

## Source
- {source_url}
{liens|liste}
