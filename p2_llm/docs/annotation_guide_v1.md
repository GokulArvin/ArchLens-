# Annotation guide v1: semantic labels (P2) (S2 D8)

One JSON file per diagram, `annotation.json`, in the format below. Validate it with `annotation.validate_annotation`, or run `cli audit` on the whole set.

```json
{"diagram_id": "S01_shop", "image": "diagram.png", "annotator": "P2",
 "components": [{"id": "c1", "name": "Order Service", "type": "service", "bbox": [x1, y1, x2, y2]}],
 "relationships": [{"source": "c1", "target": "c2", "type": "depends_on"}]}
```

## Components
1. **One box per architectural element.** Draw the bbox tight around the shape and include any label written *inside* it. Labels *outside* an icon don't go in the bbox; they're still the name.
2. **name:** the text exactly as written. Fix only obvious rendering typos. Don't expand abbreviations: "Pmt Svc" stays "Pmt Svc", because normalisation is the code's job.
3. **type:** pick one of `service, database, queue, external_system, user, gateway, frontend, cache, storage, module, interface, component, unknown`.
   - Shape wins over text: a cylinder is a `database` even if it's labelled "Orders".
   - `external_system`: anything outside the system boundary or owned by a third party (Stripe, SendGrid).
   - `component`: a generic box whose role you can't tell (e.g. "Order Controller" in a layered diagram).
   - `unknown`: unreadable. Set `name` to `"?"`.
4. **Don't annotate** legends, titles, notes or boundary frames, unless the boundary is itself a named module (then type it `module` and add `contains` edges).

## Relationships
1. Annotate only what's drawn. **Direction follows the arrowhead.**
2. type: `depends_on` (default), `calls`, `publishes_to` (dashed or async arrow into a queue), `reads_from` (consumer), `writes_to`, `contains` (nesting), `implements`.
3. A double-headed or undirected line gets two records, each with `"uncertain": true`. A line you can't trace gets no record; mention it in `notes`.

## Quality control
- About 20% of diagrams are annotated by a **second member**. Run `annotation.agreement(a, b)` and record the `type_kappa`, `relation_f1` and `disagreements` in the sprint notes.
- Settle disagreements by discussion, then update this guide (bump to v1.1) if a rule was unclear.
- **Never annotate or look at `held_out_test` diagrams while tuning prompts.** `config/split.json` is write-once.
