# {nom}

{resume}

{#if marque|modele|prix|lien}{#if marque}- **Marque** : {marque}
{/if}{#if modele}- **Modèle** : {modele}
{/if}{#if prix}- **Prix** : {prix} (constaté le {prix_constate_le})
{/if}{#if lien}- **Lien** : {lien}
{/if}
{/if}{#if points_forts}## Points forts
{points_forts|liste}

{/if}{#if points_faibles}## Points faibles
{points_faibles|liste}

{/if}{#if alternatives}## Alternatives
{alternatives|liste}

{/if}{#if illustrations}{illustrations|embed}

{/if}## Source
- {source_url}
{liens|liste}
