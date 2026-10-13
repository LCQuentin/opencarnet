# {nom}

{resume}

{#if place_type|address|city|google_maps|location|budget|website}{#if place_type}- **Type**: {place_type}
{/if}{#if address}- **Address**: {address}
{/if}{#if city}- **City**: {city}{#if country}, {country}{/if}
{/if}{#if google_maps}- **Map**: [Open in Google Maps]({google_maps})
{/if}{#if location}- **GPS**: {location}{#if gps_precision} (precision: {gps_precision}){/if}
{/if}{#if budget}- **Budget**: {budget}
{/if}{#if website}- **Website / account**: {website}
{/if}
{/if}{#if description}## About
{description}

{/if}{#if to_try}## To try
{to_try|liste}

{/if}{#if practical_info}## Practical info
{practical_info|liste}

{/if}## Possible uses
{exploitation|liste|defaut:- }

{#if illustrations}{illustrations|embed}

{/if}## Source
- {source_url}
{liens|liste}
