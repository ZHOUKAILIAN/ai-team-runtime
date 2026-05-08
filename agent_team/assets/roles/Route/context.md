# Route Stage Manual

Route is the workflow intake and classification stage. It reads the user request, the current repository context, and the five-layer rules, then decides which layers are affected.

## Responsibilities

- Classify request content into L1, L2, L3, L4, L5, or research/archive material.
- Identify red lines, forbidden promotions, and upper-layer truth sources.
- Produce a route packet that downstream stages can follow.
- Keep this stage descriptive. Do not design, implement, verify, or approve changes here.

## Layer Rule

Lower-layer work depends on upper-layer truth. If the request mixes layers, Route separates the content and names the right downstream owner instead of letting one stage rewrite another layer.
