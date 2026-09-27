# Annotated cases

One file per case, `cases/annotated/NNN.json`, named after the case.

| Key            | Content                                                     |
| -------------- | ----------------------------------------------------------- |
| `case`         | the case id, equal to the file name                         |
| `annotated_at` | date of the annotation                                      |
| `spec_commit`  | the `SPEC.md` commit the annotation follows                 |
| `expected`     | the expected record, validated by `task/schema.py`          |
| `decisions`    | the source lines that needed a rule, one entry per line     |

Each decision holds `line`, the source line as the page writes it, `rules`, the rule IDs applied (SPEC §4), and `note`. `note` is optional: it is written when the cited rule alone does not explain the choice, typically where two annotators could have decided differently.

Annotations are written from `input.txt`, then cross-checked against `page.ld.json`. They are never edited to match a model output.