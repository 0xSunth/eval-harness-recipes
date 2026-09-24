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

**Source of the case set.** 
[Marmiton](https://www.marmiton.org/). Chosen because most pages embed a [schema.org/Recipe](https://schema.org/Recipe) JSON-LD block, which gives reference data without hand-annotating hundreds of examples. The JSON-LD is the reference; the visible page text is the input. Pages are collected by hand, one at a time, and stored locally under `cases/`.

## 2. Data layers

A value has a **source form** and a **canonical form**.

- The source form is many: the same information is written several ways.
- The canonical form is one: it is what the comparator compares, and what the target schema describes.

**The normalizer applies to both sides.** The reference arrives in source form too, the JSON-LD says `PT20M`, so it goes through the same normalizer as the model output. Comparing a normalized output against a raw reference fails every case, for a reason that has nothing to do with the model.

One row per canonical **type**, not per field: two fields sharing a canonical type share one normalization function. `prepTime` and `cookTime` are both durations, so one row and one rule cover both. This table is also the plan for `task/normalize.py`.


| Canonical type | Source forms (confirm against real pages) | Canonical form                                      | Decided by |
| -------------- | ----------------------------------------- | --------------------------------------------------- | ---------- |
| Duration       | `PT20M`, `20 min`, `1 h 30`               | integer, minutes                                    | R-09       |
| Mass           | `500 g`, `1 kg`, `1,5 kg`                 | decimal, grams                                      | R-08       |
| Volume         | `25 cl`, `0,25 l`, `250 ml`               | decimal, millilitres                                | R-08       |
| Non-metric     | `1 sachet`, `2 cuillères à soupe`         | quantity as given, unit verbatim from a closed list | R-02       |
| Countable      | `3 œufs`, `1 citron`                      | integer, `unit` null                                | R-10       |
| Name           | `les Œufs`, `Cerises dénoyautées`         | bare ingredient, lowercase, no preparation          | R-01       |


A composite source can yield a composite canonical value: `500 g de cerises` is one string that becomes `{name, quantity, unit}`. The normalizer therefore also splits, not only converts.

*Presentation form, what the report prints, only needs a decision where a bare number could be misread. Otherwise the report shows canonical value + unit.*

## 3. Target schema

A field exists only if it has a verification route: comparable to the reference, checkable by an invariant, or hand-annotated. A field with no route cannot be measured and does not belong here.

### Recipe


| Field               | Type                | Required | Verified how |
| ------------------- | ------------------- | -------- | ------------ |
| `servings`          | integer | null      | no       | reference    |
| `prep_time_minutes` | integer | null      | no       | reference    |
| `cook_time_minutes` | integer | null      | no       | reference    |
| `ingredients`       | list of Ingredient  | yes      | reference    |
| `instructions`      | list of Instruction | yes      | reference    |




### Ingredient


| Field                  | Type           | Required | Verified how   |
| ---------------------- | -------------- | -------- | -------------- |
| `name`                 | string         | yes      | reference      |
| `quantity`             | decimal | null | no       | reference      |
| `unit`                 | string | null  | no       | reference      |
| `unit_is_metric`       | boolean        | yes      | invariant I-02 |
| `preparation`          | string | null  | no       | hand-annotated |
| `variant`              | string | null  | no       | reference      |
| `alternative`          | string | null  | no       | hand-annotated |
| `needs_manager_choice` | boolean        | yes      | invariant I-03 |




### Instruction


| Field      | Type    | Required | Verified how |
| ---------- | ------- | -------- | ------------ |
| `position` | integer | yes      | reference    |
| `text`     | string  | yes      | reference    |




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
- **Status** — #provisional — not yet confirmed against real pages.



### R-02 — Quantity expressed in a non-metric unit

- **Situation** — the unit in the source is not a mass or a volume. Two families: packaging (`sachet`, `boîte`, `brique`, `bouquet`) and household measures (`cuillère à soupe`, `cuillère à café`, `verre`, `pincée`).
- **Decision** — write the quantity as given and the unit verbatim, singular, from a closed list. Never convert it to grams or millilitres.
- **Reason** — a tablespoon of sugar weighs about 15 g and one of flour about 10 g: the conversion depends on the ingredient, so any table would be a value the page does not carry. `1 sachet` and `2 cuillères à soupe` are written in the text; extracting them is form, converting them is invention.
- **Consequence** — carries `unit_is_metric: false`, so the manager sees the line and completes the mass. Excluded from the mass and volume conversion metric, counted in `name` precision and recall.
- **Status** — settled.



### R-03 — Several ingredients on a single source line

- **Situation** — one source line names more than one ingredient, usually with no quantity: `sel, poivre`, `sel et poivre du moulin`.
- **Decision** — emit one record per ingredient, each with `quantity` and `unit` set to `null`. Split on commas and on `et` when what follows is a distinct ingredient.
- **Reason** — each ingredient is priced separately against the supplier catalogue; a single record named `sel, poivre` matches nothing and both disappear from the cost.
- **Consequence** — changes the ingredient count, so it moves `recall` directly: one missed split is one missing ingredient. It also makes the comparator count-sensitive, which is why the comparator matches on sets and not on position.
- **Status** — #provisional — the split on `et` is unsafe on names that contain it (`sel et poivre` vs `sucre et cannelle mélangés`). See 7, Q-01.



### R-04 — Parenthetical aside carrying no priceable information

- **Situation** — the parenthesis holds an instruction or a second, unquantified use: `(+ un peu pour le moule)`, `(pour le service)`, `(facultatif)`. It does **not** apply when the parenthesis narrows the ingredient itself (`(épaule ou tendron)`, `(demi-écrémé)`) — see R-06.
- **Decision** — the parenthesis and its content are removed before parsing. No second record is emitted.
- **Reason** — the aside carries no usable quantity, so a second record would be an ingredient with an empty quantity, priced at zero, indistinguishable from a genuine extraction failure.
- **Consequence** — costs `recall` on a real second use of the ingredient, buys `precision` on `name`. Deliberate: a missing line costs the manager seconds, a phantom line at zero cost falsifies the cost per cover silently. **The stripping runs on both sides of the comparison**, model output and reference alike, since the reference carries the parenthesis too.
- **Status** — settled.



### R-05 — Two ingredients offered as alternatives

- **Situation** — one line offers a choice with `ou`: `1 gousse de vanille ou 1 c. à c. d'extrait`, `beurre ou margarine`.
- **Decision** — keep the first option as the ingredient. The discarded text goes to `alternative`, verbatim. Never emit two records.
- **Reason** — the record feeds a cost per cover. Two records make the dish pay for both, no record makes it pay for neither; both are wrong in a way the manager cannot see. The first option is the author's primary, so it is the defensible choice, and `alternative` keeps the information rather than destroying it.
- **Consequence** — applied **on both sides** of the comparison, since the reference carries the full line too. `alternative` has no comparable reference and stays out of the headline metric.
- **Status** — #provisional — `ou` also appears inside names. Same family of problem as R-03's `et`. See 7, Q-01.



### R-06 — Parenthesis narrowing the ingredient itself

- **Situation** — the parenthesis specifies a cut, a grade or a variety that changes the catalogue entry: `veau (épaule ou tendron)`, `lait (demi-écrémé)`, `farine (T55)`.
- **Decision** — `name` stays the bare ingredient. The content goes to `variant`, verbatim. When the variant itself offers a choice with `ou`, set `needs_manager_choice: true` and do **not** pick one.
- **Reason** — shoulder and tendron are two catalogue entries at two different prices per kilo. Dropping the variant prices the wrong meat; picking one arbitrarily prices a cut the page never committed to. The only honest record says "the page does not decide, a human must".
- **Consequence** — `variant` is compared to the reference, which carries the string. `needs_manager_choice` is a flag, checkable by invariant I-03, and not a metric. These lines are excluded from any automated cost total.
- **Status** — settled.



### R-07 — Information absent from the source text

- **Situation** — the page gives no quantity, no unit, or no value for a field: `huile d'olive`, `sel`, a recipe with no stated servings.
- **Decision** — the key exists with the value `null`. Never omit the key, never fill it with a default, an average or a typical value.
- **Reason** — 1: a missing field costs the manager seconds and is visible on screen; an invented one passes review unnoticed and falsifies the cost per cover. Also, an absent key cannot be told apart from a field the extractor forgot, which destroys the error taxonomy.
- **Consequence** — governs R-02, R-03 and R-06, which all refuse to complete what the page does not say. Fields left `null` because the source was silent are excluded from that field's precision, and counted in its recall only when the reference also has them empty.
- **Status** — settled.



### R-08 — Mass or volume written in a multiple of the base unit

- **Situation** — the quantity uses a metric unit other than the base one: `1 kg`, `1,5 kg`, `25 cl`, `0,25 l`, `2 dl`. Decimal commas appear too.
- **Decision** — mass is written in grams, volume in millilitres, as a decimal with the comma replaced by a point. `1 kg` becomes `1000`, `25 cl` becomes `250`, `0,25 l` becomes `250`. `unit` holds `"g"` or `"ml"`.
- **Reason** — the supplier catalogue prices per gram and per millilitre, so the cost per cover is computed in those units. Two records holding the same quantity in different units cannot be summed, and cannot be compared to each other by the comparator.
- **Consequence** — this is the one conversion the system is allowed to perform, because the factor is fixed by the unit and not by the ingredient. It runs on both sides of the comparison. A mistake here is invisible by a factor of 1000, which is why the normalizer's unit tests carry one case per accepted source form.
- **Status** — #provisional — the list of accepted source units is to be closed against real pages.



### R-09 — Duration written in a human or in an ISO form

- **Situation** — the same duration appears in two shapes on one page. The JSON-LD reference writes ISO 8601 (`PT20M`, `PT1H30M`); the visible text writes `20 min`, `1 h 30`, `1h30`, `une heure`.
- **Decision** — durations are written as an integer number of minutes. The normalizer accepts both families as input: ISO 8601, and digits followed by a unit marker (`min`, `mn`, `h`). A duration spelled out in words (`une heure`) is **not** parsed and yields `null` under R-07.
- **Reason** — the two sides of the comparison come from two different shapes of the same page, so a normalizer that handles only one of them would report failures that are its own. Minutes rather than seconds because no source form is finer than the minute; adding precision the source lacks is invention.
- **Consequence** — a source form the normalizer does not recognise falls to `null` and costs `recall` on the duration fields, visibly. It never produces a wrong number. Words are excluded deliberately: parsing them means a lexicon, and a lexicon is a place where a value can be invented.
- **Status** — #provisional — `une heure` may be frequent enough to deserve its own rule rather than a `null`. Count it on 30 pages before deciding. See 7, Q-03.



### R-10 — Countable ingredient with no unit word

- **Situation** — the line gives a count and an ingredient, with no unit word at all: `3 œufs`, `1 citron`, `4 merguez`. This is **not** R-02: in `2 gousses d'ail` the word `gousses` is present in the text and is a unit, so it goes to R-02's closed list. The discriminator is whether a unit word is written.
- **Decision** — `quantity` holds the count, `unit` is `null`, and `unit_is_metric` is `false`. `name` is the ingredient in the singular (`œuf`, `citron`), so that three eggs and one egg carry the same name.
- **Reason** — the page states a count and no unit, so writing `"pièce"` or `"unité"` would add a word the source does not contain, and writing `60 g` for an egg would be the conversion table R-02 already refuses. The singular is what the catalogue lists, and it keeps `name` comparable across recipes.
- **Consequence** — these lines cannot be priced per gram, so they carry the same flag as R-02 and are excluded from the mass and volume conversion metric. The singularisation is a normalization applied **on both sides**: the reference writes the plural too. It also creates a failure mode of its own, an irregular plural silently mis-singularised, which is why the normalizer keeps an explicit exception list rather than stripping a final `s`.
- **Status** — #provisional — the exception list is empty until real pages fill it. Whether the catalogue sells eggs by the piece is a client question; see 7, Q-04.



## 5. Invariants

Checks a verifier runs on the produced record. **These are not schema fields** — nothing here is annotated by hand. An invariant that needs no reference also works in production, where no reference exists. Mark that column honestly.


| ID   | Invariant                                                                               | Needs the reference? |
| ---- | --------------------------------------------------------------------------------------- | -------------------- |
| I-01 | Every ingredient named in the steps appears in the ingredient list, and the reverse.    | No                   |
| I-02 | `unit_is_metric` is true if and only if `unit` is `"g"` or `"ml"`.                      | No                   |
| I-03 | `needs_manager_choice` is true if and only if `variant` offers a choice.                | No                   |
| I-04 | A non-null `unit` implies a non-null `quantity`.                                        | No                   |
| I-05 | Every rule ID cited anywhere in this file exists as a heading in 4.                     | No                   |
| I-06 | `position` on the instructions runs 1..n with no gap and no repeat.                     | No                   |
| I-07 | Every `unit` value belongs to the closed list: `g`, `ml`, or a non-metric unit of R-02. | No                   |


I-05 is a check on the spec, not on a record. It is the invariant that would have caught the dead cross-references of 2026-09-24.

I-07 is the one that catches an invented unit, which is the failure R-02 and R-10 exist to prevent. It is cheap, it needs no reference, and it would fire in production on the first day a page uses a unit nobody anticipated.

## 6. Edge cases

Derived from the rules, not invented. Each rule describes a situation; that situation becomes a test case. A rule that yields no case is probably not a real rule.


| Case                                         | Rule tested | Expected behaviour                                                 |
| -------------------------------------------- | ----------- | ------------------------------------------------------------------ |
| `500 g de cerises dénoyautées`               | R-01        | `name: "cerises"`, `preparation: "dénoyautées"`                    |
| `2 cuillères à soupe de sucre`               | R-02        | `quantity: 2`, `unit: "cuillère à soupe"`, `unit_is_metric: false` |
| `sel, poivre`                                | R-03        | two records, both with `quantity: null`                            |
| `50 g de beurre (+ un peu pour le moule)`    | R-04        | one record, `quantity: 50`, aside dropped on both sides            |
| `1 gousse de vanille ou 1 c. à c. d'extrait` | R-05        | one record on vanilla, `alternative` holds the rest                |
| `800 g de veau (épaule ou tendron)`          | R-06        | `variant: "épaule ou tendron"`, `needs_manager_choice: true`       |
| `huile d'olive`                              | R-07        | `quantity: null`, `unit: null`, keys present                       |
| `1,5 kg de pommes de terre`                  | R-08        | `quantity: 1500`, `unit: "g"`                                      |
| `PT1H30M` and `1 h 30` on the same page      | R-09        | both normalize to `90`                                             |
| `une heure de repos`                         | R-09        | `null`, not `60`                                                   |
| `3 œufs`                                     | R-10        | `quantity: 3`, `unit: null`, `name: "œuf"`                         |
| `2 gousses d'ail`                            | R-10 / R-02 | R-02 wins: `unit: "gousse"`, a unit word is written                |


**Counter-example check.** For each rule, find one real recipe that the rule would wrongly reject. If you find one, the rule is wrong, not the data.

## 7. Open questions

Decisions I could not settle alone, or that would belong to a domain expert in a real project. Recorded rather than silently resolved.


| ID   | Question                                                                                            | Options                                                                                                 | Provisional choice             | Why unresolved                                                                                                                                                 |
| ---- | --------------------------------------------------------------------------------------------------- | ------------------------------------------------------------------------------------------------------- | ------------------------------ | -------------------------------------------------------------------------------------------------------------------------------------------------------------- |
| Q-01 | `et` and `ou` appear both as separators and inside ingredient names. How is the difference decided? | (a) split always; (b) never split on `et`/`ou`, only on commas; (c) closed list of known compound names | (a), with the failures counted | Needs a count on real pages. A wrong split invents an ingredient; a missed split loses one. The costs are not symmetric and I do not yet know the frequencies. |
| Q-02 | Should a brand name stay in `name`? `4 merguez végétales ACCRO`                                     | (a) keep; (b) drop to a `brand` field; (c) drop entirely                                                | (b)                            | Depends on whether the catalogue is branded, which is a client question.                                                                                       |
| Q-03 | Are durations spelled out in words frequent enough to parse?                                        | (a) leave `null`; (b) small closed lexicon                                                              | (a)                            | No count yet.                                                                                                                                                  |
| Q-04 | Does the catalogue sell countables by the piece, so that `3 œufs` can be priced at all?             | (a) by the piece, priceable; (b) by weight only, the manager completes the mass                         | (b)                            | A client question. The platform's data model decides it, not the recipe page.                                                                                  |




## 8. Revised decisions

Rules changed after seeing real data. Keeping this visible is the point: it shows the spec was tested, not guessed.


| Date       | Rule       | Before                                        | After                                            | What triggered the change                                                                          |
| ---------- | ---------- | --------------------------------------------- | ------------------------------------------------ | -------------------------------------------------------------------------------------------------- |
| 2026-09-24 | R-02       | packaging units only                          | packaging and household measures                 | `2 cuillères à soupe de sucre`                                                                     |
| 2026-09-24 | R-04       | all parentheses stripped                      | non-priceable asides only; R-06 handles the rest | `800 g de veau (épaule ou tendron)`                                                                |
| 2026-09-24 | R-07       | lost in a renumbering                         | restored; rule IDs frozen from now on            | `huile d'olive` had no governing rule                                                              |
| 2026-09-24 | R-08, R-09 | lost in the same renumbering                  | rewritten and appended                           | 2 cited R-01 for masses and durations, which R-01 never decided                                    |
| 2026-09-24 | I-02       | false iff `unit` is in R-02's non-metric list | true iff `unit` is `g` or `ml`                   | R-10 sets `unit: null` with `unit_is_metric: false`; the old wording made that combination illegal |


