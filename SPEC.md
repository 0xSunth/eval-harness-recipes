# SPEC — recipe extraction

## 1. Task

**Input.** The free text of a recipe page, as published online.

**Output.** A structured record: ingredients with quantity and unit, number of servings, preparation steps.

**Consumer.** A management platform for independent restaurants. Each ingredient is matched against a supplier catalogue and priced per gram or millilitre; the total is divided by the number of servings to give a cost per cover, which sets the menu price. The record is pre-filled by the system and **corrected by the restaurant manager before it is used**.

**The boundary.** The system transforms form, it never creates content. `25 cl` becomes `250 ml`: same information, different notation. Inferring, computing or completing anything absent from the text is out of scope.

> If it is in the text, extract it. If it is not, leave it empty.

**Why that boundary is a business rule, not a preference.** A human reviews every record. An empty field is visible and costs seconds to fill. An invented value looks correct, passes review unnoticed, and produces a wrong cost per cover, which sets a wrong menu price. Omission is cheap and visible; invention is expensive and invisible. The system therefore always prefers the empty value to the plausible one.

**Out of scope.**

- Scaling quantities to a different number of servings — the platform does that.
- Matching ingredient names to the supplier catalogue — downstream step.
- Any price or cost data — never present in the source text.
- Summing the same ingredient across components. `200 g de farine` for the pastry and `50 g de farine` for the filling stay two records; the platform adds them up. See R-11.
- Re-segmenting instructions. A step is extracted exactly as the page splits it, even when it holds several actions (`Éplucher et hacher les oignons. Éplucher et hacher les gousses d'ail.` is one step, not two).
- Units appearing inside instruction text (`couper en tronçons de 5 cm`). Only units attached to an ingredient line are extracted.

**Source of the case set.** [Marmiton](https://www.marmiton.org/). Chosen because most pages embed a [schema.org/Recipe](https://schema.org/Recipe) JSON-LD block, which gives reference data without hand-annotating hundreds of examples. The JSON-LD is the reference; the visible page text is the input. Pages are collected by hand, one at a time, and stored under `cases/raw/`.

## 2. Data layers

A value has a **source form** and a **canonical form**.

- The source form is many: the same information is written several ways.
- The canonical form is one: it is what the comparator compares, and what the target schema describes.

**The normalizer applies to both sides.** The reference arrives in source form too, the JSON-LD says `PT20M`, so it goes through the same normalizer as the model output. Comparing a normalized output against a raw reference fails every case, for a reason that has nothing to do with the model.

One row per canonical **type**, not per field: two fields sharing a canonical type share one normalization function. `prepTime` and `cookTime` are both durations, so one row and one rule cover both. This table is also the plan for `task/normalize.py`.

| Canonical type | Source forms (observed on the 10 captured cases) | Canonical form | Decided by |
| --- | --- | --- | --- |
| Duration | `PT20M`, `20 min`, `20 mn`, `20 minutes`, `1 h`, `1 h 30` | integer, minutes | R-09 |
| Mass | `500 g`, `1 kg`, `1,5 kg` | decimal, grams | R-08 |
| Volume | `25 cl`, `0,25 l`, `250 ml` | decimal, millilitres | R-08 |
| Non-metric | `1 sachet`, `2 cuillères à soupe` | quantity as given, unit verbatim from a closed list | R-02 |
| Countable | `3 œufs`, `1 citron` | integer, `unit` null | R-10 |
| Name | `les Œufs`, `3 oeufs`, `Cerises dénoyautées`, `Crème fraîche entière` | bare ingredient, singular, lowercase, no preparation and no qualifier | R-01, R-06, R-10 |

A composite source can yield a composite canonical value: `500 g de cerises` is one string that becomes `{name, quantity, unit}`. The normalizer therefore also splits, not only converts.

_Presentation form, what the report prints, only needs a decision where a bare number could be misread. Otherwise the report shows canonical value + unit._

## 3. Target schema

A field exists only if it has a verification route: comparable to the reference, checkable by an invariant, or hand-annotated. A field with no route cannot be measured and does not belong here.

### Recipe

| Field | Type | Required | Verified how |
| --- | --- | --- | --- |
| `servings` | integer \| null | no | reference |
| `prep_time_minutes` | integer \| null | no | reference |
| `cook_time_minutes` | integer \| null | no | reference |
| `ingredients` | list of Ingredient | yes | reference |
| `instructions` | list of Instruction | yes | reference |

### Ingredient

| Field | Type | Required | Verified how |
| --- | --- | --- | --- |
| `name` | string | yes | reference |
| `quantity` | decimal \| null | no | reference |
| `unit` | string \| null | no | reference |
| `unit_is_metric` | boolean | yes | invariant I-02 |
| `preparation` | string \| null | no | hand-annotated |
| `variant` | string \| null | no | reference |
| `alternative` | string \| null | no | hand-annotated |
| `component` | string \| null | no | reference, to confirm — see §7 Q-05 |
| `needs_manager_choice` | boolean | yes | invariant I-03 |

### Instruction

| Field | Type | Required | Verified how |
| --- | --- | --- | --- |
| `position` | integer | yes | derived from the reference array order |
| `text` | string | yes | reference |

`position` is not written anywhere in the JSON-LD: `recipeInstructions` is an ordered list of `HowToStep` objects with no index field. The position is derived from that order, and checked by invariant I-06.

## 4. Normalization rules

**Governing principle.** Where the source text does not decide, the record does not decide either: it flags. `unit_is_metric: false` and `needs_manager_choice: true` are both instances of this. A record that says "a human must look at this line" is correct; a record that guesses is not.

Every rule uses the shape below. Four checks before a rule is finished: the name describes a situation and not a solution; the decision is writable as-is by an annotator, with no interpretation left; the reason traces back to the consumer or to the measurement, never to taste; the consequence says what moves in the numbers.

A rule is needed wherever two careful annotators, reading the same text, could legitimately write different values. Where the text forces one answer, no rule is needed.

**Rule IDs are addresses, not ranks.** They are never renumbered and never reused. A withdrawn rule leaves a marked hole. New rules are appended.

### R-01 — Ingredient name carrying a preparation state

- **Situation** — the source string attaches a past participle describing a preparation to the ingredient name: `cerises dénoyautées`, `oignons émincés`, `beurre fondu`.
- **Decision** — `name` holds the ingredient alone (`cerises`), lowercase. The participle goes to `preparation`, verbatim, lowercase. If there is none, `preparation` is `null`.
- **Reason** — `name` is matched against a supplier catalogue, which lists `cerises` and never `cerises dénoyautées`. A name that carries the preparation never matches and the ingredient gets no price, so the cost per cover is wrong.
- **Consequence** — `name` becomes comparable to the reference, which also writes the bare ingredient. `preparation` has no comparable reference; it is hand-annotated on the case set only and excluded from the headline precision and recall.
- **Boundary with R-06** — both rules detach a word stuck to the name. The test is the price, not the grammar: a preparation state does not change the price per kilo (pitted or not, cherries cost the same), a qualifier does (`épaule` and `tendron` are two catalogue entries). Preparation goes here, qualifier goes to R-06.
- **Status** — settled. 4/10 cases (002, 003, 005, 006).

### R-02 — Quantity expressed in a non-metric unit

- **Situation** — the unit in the source is not a mass or a volume. Two families: packaging (`sachet`, `boîte`, `brique`, `bouquet`) and household measures (`cuillère à soupe`, `cuillère à café`, `verre`, `pincée`).
- **Decision** — write the quantity as given and the unit verbatim, singular, from a closed list. Never convert it to grams or millilitres.
- **Reason** — a tablespoon of sugar weighs about 15 g and one of flour about 10 g: the conversion depends on the ingredient, so any table would be a value the page does not carry. `1 sachet` and `2 cuillères à soupe` are written in the text; extracting them is form, converting them is invention.
- **Consequence** — carries `unit_is_metric: false`, so the manager sees the line and completes the mass. Excluded from the mass and volume conversion metric, counted in `name` precision and recall.
- **Status** — settled. 9/10 cases (001 to 007, 009, 010), the most frequent rule of the set.

### R-03 — Several ingredients on a single source line

- **Situation** — one source line names more than one ingredient, usually with no quantity: `sel, poivre`, `sel et poivre du moulin`.
- **Decision** — emit one record per ingredient, each with `quantity` and `unit` set to `null`. Split on commas and on `et` when what follows is a distinct ingredient.
- **Reason** — each ingredient is priced separately against the supplier catalogue; a single record named `sel, poivre` matches nothing and both disappear from the cost.
- **Consequence** — changes the ingredient count, so it moves `recall` directly: one missed split is one missing ingredient. It also makes the comparator count-sensitive, which is why the comparator matches on sets and not on position.
- **Status** — #unobserved. 0/10 cases. The JSON-LD stores `recipeIngredient` as an array, so the reference has already done the splitting: this rule targets the **visible page text**, not the reference. Kept because other sources do not pre-split, but **excluded from the metric** until a case exercises it. A rule that never fires measures nothing, and counting it as acquired would be a free point. Detection remains unsafe on names containing `et`. See §7, Q-01.

### R-04 — Parenthetical aside carrying no priceable information

- **Situation** — the parenthesis holds an instruction or a second, unquantified use: `(+ un peu pour le moule)`, `(pour le service)`, `(facultatif)`, `(un peu, pour décorer)`. It does **not** apply when the parenthesis narrows the ingredient itself — see R-06.
- **Decision** — the parenthesis and its content are removed before parsing. No second record is emitted from the aside.
- **Reason** — the aside carries no usable quantity, so a second record would be an ingredient with an empty quantity, priced at zero, indistinguishable from a genuine extraction failure.
- **Consequence** — costs `recall` on a real second use of the ingredient, buys `precision` on `name`. Deliberate: a missing line costs the manager seconds, a phantom line at zero cost falsifies the cost per cover silently. **The stripping runs on both sides of the comparison**, model output and reference alike, since the reference carries the parenthesis too.
- **Status** — settled. 3/10 cases (002, 009, 010).

### R-05 — Two ingredients offered as alternatives

- **Situation** — one line offers a choice with `ou`: `1 gousse de vanille ou 1 c. à c. d'extrait`, `beurre ou margarine`.
- **Decision** — keep the first option as the ingredient. The discarded text goes to `alternative`, verbatim. Never emit two records.
- **Reason** — the record feeds a cost per cover. Two records make the dish pay for both, no record makes it pay for neither; both are wrong in a way the manager cannot see. The first option is the author's primary, so it is the defensible choice, and `alternative` keeps the information rather than destroying it.
- **Consequence** — applied **on both sides** of the comparison, since the reference carries the full line too. `alternative` has no comparable reference and stays out of the headline metric.
- **Status** — settled on the decision. 4/10 cases (002, 005, 007, 009). #provisional on the detection only: `ou` also appears inside names, same family of problem as R-03's `et`. See §7, Q-01.

### R-06 — Qualifier narrowing the ingredient itself

- **Situation** — a word attached to the ingredient name specifies a cut, a grade, a fat content or a variety, and therefore changes which catalogue entry is priced. **The punctuation is not the situation.** It appears in two shapes: with parentheses, `veau (épaule ou tendron)`, `farine (T55)`; and with none at all, `crème fraîche entière`, `lait demi-écrémé`.
- **Decision** — `name` stays the bare ingredient. The qualifier goes to `variant`, **verbatim, case preserved**, parentheses removed. When the qualifier itself offers a choice with `ou`, set `needs_manager_choice: true` and do **not** pick one.
- **Why the case is preserved, unlike `name`** — a qualifier is often a standardised designation: `T55`, `AOP`, `IGP`, `demi-sel`. Lowercasing turns `T55` into `t55` and destroys the designation. `name` is lowercased because it is a common noun used as a catalogue key; `variant` is not.
- **Reason** — shoulder and tendron are two catalogue entries at two different prices per kilo, and whole cream is not the same product as light cream. Dropping the qualifier prices the wrong item; picking one arbitrarily prices something the page never committed to. The only honest record says "the page does not decide, a human must".
- **Boundary with R-01** — the test is whether the word changes the price per kilo, not whether it is a participle or an adjective.
- **Consequence** — `variant` is compared to the reference, which carries the string. The comparison is case-sensitive, which costs precision when a page capitalises inconsistently; that cost is accepted and measured rather than hidden behind a lowercasing that would corrupt designations. `needs_manager_choice` is a flag, checkable by invariant I-03, and not a metric. These lines are excluded from any automated cost total. Detecting a qualifier with no punctuation is strictly harder than finding a parenthesis: that difficulty is now inside the rule rather than hidden outside it, and it will show as lower `variant` precision rather than as a silently missing field.
- **Status** — #provisional. The unparenthesised form was observed on a real page (`Crème fraîche entière`, case 005); the parenthesised form fired 0/10. The list of qualifier families is to be closed against 30 pages.

### R-07 — Information absent from the source text

- **Situation** — the page gives no quantity, no unit, or no value for a field: `huile d'olive`, `caramel`, `sel`, a recipe with no stated servings.
- **Decision** — the key exists with the value `null`. Never omit the key, never fill it with a default, an average or a typical value.
- **Reason** — §1: a missing field costs the manager seconds and is visible on screen; an invented one passes review unnoticed and falsifies the cost per cover. Also, an absent key cannot be told apart from a field the extractor forgot, which destroys the error taxonomy.
- **Consequence** — governs R-02, R-03, R-06 and R-10, which all refuse to complete what the page does not say. Fields left `null` because the source was silent are excluded from that field's precision, and counted in its recall only when the reference also has them empty.
- **Status** — settled. 4/10 cases (001, 002, 005, 009).

### R-08 — Mass or volume written in a multiple of the base unit

- **Situation** — the quantity uses a metric unit other than the base one: `1 kg`, `1,5 kg`, `25 cl`, `0,25 l`, `2 dl`. Decimal commas appear too.
- **Decision** — mass is written in grams, volume in millilitres, as a decimal with the comma replaced by a point. `1 kg` becomes `1000`, `25 cl` becomes `250`, `0,25 l` becomes `250`. `unit` holds `"g"` or `"ml"`.
- **Reason** — the supplier catalogue prices per gram and per millilitre, so the cost per cover is computed in those units. Two records holding the same quantity in different units cannot be summed, and cannot be compared to each other by the comparator.
- **Consequence** — this is the one conversion the system is allowed to perform, because the factor is fixed by the unit and not by the ingredient. It runs on both sides of the comparison. A mistake here is invisible by a factor of 1000, which is why the normalizer's unit tests carry one case per accepted source form.
- **Status** — settled. Observed on cases 003 and 004, which carry `cl` and `ml`. The list of accepted source units stays open until 30 pages have been read.

### R-09 — Duration written in a human or in an ISO form

- **Situation** — the same duration appears in two shapes on one page. The JSON-LD reference writes ISO 8601 (`PT20M`, `PT1H30M`); the visible text uses a digit followed by a marker, and the marker varies more than anticipated: `mn` (case 002), `h` (case 004), `minutes` spelled out (case 005), plus `min` and the hour-minute forms `1 h 30` and `1h30`.
- **Decision** — durations are written as an integer number of minutes. The normalizer accepts two input families: ISO 8601, and a digit followed by a marker taken from a **closed list**: `min`, `mn`, `minute`, `minutes`, `h`, `heure`, `heures`, with or without a space, and with an optional trailing minute count after an hour marker. A duration spelled out entirely in words (`une heure`) is **not** parsed and yields `null` under R-07.
- **Reason** — the two sides of the comparison come from two shapes of the same page, so a normalizer that handles only one of them would report failures that are its own. The marker list is closed rather than matched by a loose pattern on any letter, so an unknown marker fails loudly instead of being silently mapped to minutes. Minutes rather than seconds because no source form is finer than the minute; adding precision the source lacks is invention.
- **Consequence** — a source form the normalizer does not recognise falls to `null` and costs `recall` on the duration fields, visibly. It never produces a wrong number. Words are excluded deliberately: parsing them means a lexicon, and a lexicon is a place where a value can be invented.
- **Status** — #provisional. 3/10 cases (002, 004, 005). Three distinct markers in ten pages suggests the list is not closed: re-open it after 30 pages. See §7, Q-03.

### R-10 — Countable ingredient with no unit word

- **Situation** — the line gives a count and an ingredient, with no unit word at all: `3 œufs`, `1 citron`, `4 merguez`. This is **not** R-02: in `2 gousses d'ail` the word `gousses` is present in the text and is a unit, so it goes to R-02's closed list. The discriminator is whether a unit word is written.
- **Decision** — `quantity` holds the count, `unit` is `null`, and `unit_is_metric` is `false`. `name` is the ingredient in the singular (`œuf`, `citron`), so that three eggs and one egg carry the same name.
- **Reason** — the page states a count and no unit, so writing `"pièce"` or `"unité"` would add a word the source does not contain, and writing `60 g` for an egg would be the conversion table R-02 already refuses. The singular is what the catalogue lists, and it keeps `name` comparable across recipes.
- **Consequence** — these lines cannot be priced per gram, so they carry the same flag as R-02 and are excluded from the mass and volume conversion metric. The singularisation is a normalization applied **on both sides**: the reference writes the plural too. It also creates a failure mode of its own, an irregular plural silently mis-singularised, which is why the normalizer keeps an explicit exception list rather than stripping a final `s`.
- **Status** — settled on the decision. 9/10 cases (all but 008). #provisional on the singularisation: the irregular-plural exception list is still empty. See §7, Q-04.

### R-11 — Ingredients grouped by component

- **Situation** — the page groups its ingredients under headings, one per part of the dish: `Pour la pâte`, `Pour la garniture`, `Pour le glaçage`. The same ingredient may appear under more than one heading, with a different quantity each time.
- **Decision** — one record **per source line**, never merged and never summed. `component` holds the heading with the leading `Pour la`, `Pour le`, `Pour les` removed, the rest verbatim and lowercase: `Pour la pâte` becomes `pâte`. A line outside any heading has `component: null`.
- **Why the article is dropped** — it belongs to the layout of the heading, not to the identity of the component. Without this clause `Pour la pâte` and `La pâte`, two writings of the same thing on two pages, would produce two different values and the same component would look like two.
- **Reason** — two arguments, either one sufficient. The measurement first: the reference carries two separate entries for the flour, so a single summed record shows as one produced against two expected, and `recall` is charged for an error the model did not make. Then §1: `200 g` plus `50 g` gives `250 g`, a number written nowhere on the page, which the manager cannot check at a glance. The cost per cover is still computed, by the platform, which is where §1 already puts scaling and totalling.
- **Consequence** — raises the ingredient count on grouped recipes, so an extractor that merges loses `recall` visibly. `component` is comparable to the reference only if the JSON-LD carries the headings, which is not yet established: until then it is hand-annotated and stays out of the headline metric. It also makes duplicate names legitimate, which is why I-09 flags them instead of forbidding them.
- **Status** — #provisional. 1/10 cases (007). See §7, Q-05.

## 5. Invariants

Checks a verifier runs on the produced record. **These are not schema fields** — nothing here is annotated by hand. An invariant that needs no reference also works in production, where no reference exists. Mark that column honestly.

| ID | Invariant | Needs the reference? |
| --- | --- | --- |
| I-01 | Every ingredient named in the steps appears in the ingredient list, as `name` or as `alternative`. | No |
| I-02 | `unit_is_metric` is true if and only if `unit` is `"g"` or `"ml"`. | No |
| I-03 | `needs_manager_choice` is true if and only if `variant` is non-null and contains the token ` ou ` between two spaces. | No |
| I-04 | A non-null `unit` implies a non-null `quantity`. | No |
| I-05 | Every rule ID cited anywhere in this file exists as a heading in §4. | No |
| I-06 | `position` on the instructions runs 1..n with no gap and no repeat. | No |
| I-07 | Every `unit` value belongs to the closed list: `g`, `ml`, or a non-metric unit of R-02. | No |
| I-08 | When `prep_time_minutes`, `cook_time_minutes` and the page's `totalTime` are all present, the first two add up to the third. | No |
| I-09 | Two records sharing the same `name` are flagged, never merged. | No |

I-01 is **#provisional**, and for two reasons found while checking it against the rules. It used to say "and the reverse", which fires on almost every recipe: salt and pepper are listed and never named in the steps. That half is dropped until the false-positive rate is measured. It also used to compare the steps against `name` alone, which made it contradict R-05: the discarded alternative sits in `alternative`, so a step naming it was reported as an incoherence on a record that was correct. An invariant that accuses a rule is the invariant that is wrong.

I-03 used to read "if and only if `variant` offers a choice". "Offers a choice" is not applicable by a machine without a definition, so it was not an invariant, it was an instruction to a human. The token test is mechanical. It misses a qualifier where `ou` is glued to a word, which is the residual risk already recorded as Q-01.

I-05 is a check on the spec, not on a record. It is the invariant that would have caught the dead cross-references of 2026-09-24.

I-07 is the one that catches an invented unit, which is the failure R-02 and R-10 exist to prevent. It is cheap, it needs no reference, and it would fire in production on the first day a page uses a unit nobody anticipated.

I-08 came from reading a real page: `prepTime PT15M`, `cookTime PT45M`, `totalTime PT1H`. The consistency is free to check and catches a duration mis-parsed by a factor of 60.

I-09 exists because R-11 makes a duplicate name legitimate (the same flour in two components) while case 009 shows an illegitimate one (`1 concombre`, then `concombre (un peu, pour décorer)`). The verifier cannot tell the two apart, so it does not try: it flags for the manager. Merging would destroy `un peu, pour décorer` and break the count against the reference.

## 6. Edge cases

Derived from the rules, not invented. Each rule describes a situation; that situation becomes a test case. A rule that yields no case is probably not a real rule. Strings marked **real** were read on a captured page; the others are constructed and are to be replaced as soon as a real one turns up.

| Case | Source | Rule tested | Expected behaviour |
| --- | --- | --- | --- |
| `Crème fraîche entière` | real, case 005 | R-06 | `name: "crème fraîche"`, `variant: "entière"`, `needs_manager_choice: false` |
| `1 h` | real, case 004 | R-09 | `60` |
| `20 mn` | real, case 002 | R-09 | `20` |
| `45 minutes` | real, case 005 | R-09 | `45` |
| `prepTime PT15M` + `cookTime PT45M` + `totalTime PT1H` | real, case 001 | I-08 | consistent, no flag |
| `caramel` | real, case 001 | R-07 | `quantity: null`, `unit: null`, keys present |
| `3 oeufs` written with the digraph, not `œ` | real, case 001 | R-10, R-01 | `name: "œuf"`, `quantity: 3`, `unit: null` |
| `1 concombre` and `concombre (un peu, pour décorer)` | real, case 009 | R-04, R-07, I-09 | two records, aside stripped, duplicate flagged |
| `400 g de lait concentré` and `400 ml de lait écrémé` | real, case 001 | R-08 | `unit: "g"` and `unit: "ml"`, no confusion |
| `500 g de cerises dénoyautées` | constructed | R-01 | `name: "cerises"`, `preparation: "dénoyautées"` |
| `2 cuillères à soupe de sucre` | constructed | R-02 | `quantity: 2`, `unit: "cuillère à soupe"`, `unit_is_metric: false` |
| `sel, poivre` | constructed | R-03 | two records, both with `quantity: null` |
| `1 gousse de vanille ou 1 c. à c. d'extrait` | constructed | R-05 | one record on vanilla, `alternative` holds the rest |
| `800 g de veau (épaule ou tendron)` | constructed | R-06 | `variant: "épaule ou tendron"`, `needs_manager_choice: true` |
| `1,5 kg de pommes de terre` | constructed | R-08 | `quantity: 1500`, `unit: "g"` |
| `une heure de repos` | constructed | R-09 | `null`, not `60` |
| `2 gousses d'ail` | constructed | R-10 against R-02 | R-02 wins: `unit: "gousse"`, a unit word is written |
| `200 g de farine` under `Pour la pâte` and `50 g de farine` under `Pour la garniture` | constructed | R-11, I-09 | two records, `component` set, no sum, duplicate flagged |

**Counter-example check.** For each rule, find one real recipe that the rule would wrongly reject. If you find one, the rule is wrong, not the data.

## 7. Open questions

Decisions I could not settle alone, or that would belong to a domain expert in a real project. Recorded rather than silently resolved.

| ID | Question | Options | Provisional choice | Why unresolved |
| --- | --- | --- | --- | --- |
| Q-01 | `et` and `ou` appear both as separators and inside ingredient names. How is the difference decided? | (a) split always; (b) never split on `et`/`ou`, only on commas; (c) closed list of known compound names | (a), with the failures counted | Needs a count on real pages. A wrong split invents an ingredient; a missed split loses one. The costs are not symmetric and I do not yet know the frequencies. |
| Q-02 | Should a brand name stay in `name`? `4 merguez végétales ACCRO` | (a) keep; (b) drop to a `brand` field; (c) drop entirely | (b) | Depends on whether the catalogue is branded, which is a client question. |
| Q-03 | Are durations spelled out in words frequent enough to parse? | (a) leave `null`; (b) small closed lexicon | (a) | No count yet. Three marker forms in ten pages suggests the written forms are more varied than expected. |
| Q-04 | Does the catalogue sell countables by the piece, so that `3 œufs` can be priced at all? | (a) by the piece, priceable; (b) by weight only, the manager completes the mass | (b) | A client question. The platform's data model decides it, not the recipe page. |
| Q-05 | Does the JSON-LD carry the component headings, or do they exist only in the visible text? | (a) the reference carries them, `component` is comparable; (b) visible text only, `component` is hand-annotated | (b) | Not checked on the captured pages: `recipeIngredient` is a flat array on the ones read so far. Decides whether `component` enters the headline metric. |
| Q-06 | Is `œuf` against `oeuf` the only ligature pair, or is there a wider accent and ligature problem? | (a) normalize ligatures only; (b) full Unicode normalization on both sides | (b) | One occurrence found so far. A sweep on 30 pages will say. |

## 8. Revised decisions

Rules changed after seeing real data. Keeping this visible is the point: it shows the spec was tested, not guessed.

| Date | Rule | Before | After | What triggered the change |
| --- | --- | --- | --- | --- |
| 2026-09-24 | R-02 | packaging units only | packaging and household measures | `2 cuillères à soupe de sucre` |
| 2026-09-24 | R-04 | all parentheses stripped | non-priceable asides only; R-06 handles the rest | `800 g de veau (épaule ou tendron)` |
| 2026-09-24 | R-07 | lost in a renumbering | restored; rule IDs frozen from now on | `huile d'olive` had no governing rule |
| 2026-09-24 | R-08, R-09 | lost in the same renumbering | rewritten and appended | §2 cited R-01 for masses and durations, which R-01 never decided |
| 2026-09-24 | I-02 | false iff `unit` is in R-02's non-metric list | true iff `unit` is `g` or `ml` | R-10 sets `unit: null` with `unit_is_metric: false`; the old wording made that combination illegal |
| 2026-09-25 | R-06 | situation defined by the parenthesis | situation defined by the qualifier, whatever the punctuation | `Crème fraîche entière`: a qualifier with no parenthesis. The rule was keyed on punctuation instead of on the phenomenon, and the parenthesised form never appeared in 10 pages |
| 2026-09-25 | R-09 | markers `min`, `mn`, `h` | closed list extended with `minute`, `minutes`, `heure`, `heures` | `45 minutes` spelled out, case 005 |
| 2026-09-25 | R-03 | settled, counted in the metric | `#unobserved`, excluded from the metric | 0/10 cases: the JSON-LD array pre-splits the lines, so the rule targets the visible text only |
| 2026-09-25 | §3 | `position` verified by the reference | derived from the array order, checked by I-06 | `recipeInstructions` holds `HowToStep` objects with no index field |
| 2026-09-25 | §1 | silent on grouped ingredients | summing across components declared out of scope, R-11 added | recipes split into `Pour la pâte` and `Pour la garniture`, with the same ingredient in both |
| 2026-09-25 | R-06 | `variant` lowercased like `name` | `variant` verbatim, case preserved | lowercasing turns `T55` into `t55` and destroys a standardised designation |
| 2026-09-25 | R-11 | `component` said "article dropped" with no rule | explicit clause: leading `Pour la/le/les` removed, rest verbatim | the instruction was not applicable as written; `Pour la pâte` and `La pâte` would have produced two values for one component |
| 2026-09-25 | I-03 | "if and only if `variant` offers a choice" | token test on ` ou ` between two spaces | "offers a choice" needs human judgement, which disqualifies it as an invariant |
| 2026-09-25 | I-01 | steps against `name`, in both directions | steps against `name` or `alternative`, one direction, #provisional | it contradicted R-05, whose discarded option lives in `alternative`, and the reverse direction fires on every recipe listing salt without naming it in the steps |
| 2026-09-25 | §9 | "ten rules out of eleven fire" | nine confirmed, one at zero, one unknown | the claim went beyond the table printed directly above it |

## 9. Rule coverage on the case set

How often each rule fires on the 10 captured cases. A score is only readable next to this table: without it, a high number may only mean the case set exercises four rules out of eleven.

| Rule | Cases where it fires | Count | Status |
| --- | --- | --- | --- |
| R-01 | 002, 003, 005, 006 | 4/10 | settled |
| R-02 | 001 to 007, 009, 010 | 9/10 | settled |
| R-03 | none | 0/10 | #unobserved, excluded from the metric |
| R-04 | 002, 009, 010 | 3/10 | settled |
| R-05 | 002, 005, 007, 009 | 4/10 | settled |
| R-06 | unparenthesised form only, case 005 | 1/10 | #provisional |
| R-07 | 001, 002, 005, 009 | 4/10 | settled |
| R-08 | 003, 004 | 2/10 | settled |
| R-09 | 002, 004, 005 | 3/10 | #provisional |
| R-10 | all but 008 | 9/10 | settled |
| R-11 | 007 | 1/10 | #provisional |

**Ten of the eleven rules fire at least once on these ten cases. R-03 fires zero times and is excluded from the metric.** An earlier wording of this paragraph claimed ten out of eleven while R-11's count was still unknown: a figure asserted beyond its own data, in the project whose subject is precisely that. R-11 has since been counted on case 007, which makes the claim true. The episode is recorded rather than quietly erased.

Any figure published in `Results` carries this table, its denominator per field, and the exclusions declared in §4.