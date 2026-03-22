# Observations

## Standalone type resolution works correctly

The skill correctly distinguishes standalone vs hosted types. A standalone type (like team-charter) has no parent type declaring it in a Collections or Facets table. The skill's step 10 says: "If standalone (not hosted by any parent): ask 'Where should these documents live?' ... Add a row to the root type's Collections table." This is clear and unambiguous.

## The type definition correctly omits a Collections section

The schema says Collections is optional and only needed when a type "hosts collections of other document types within its directory." Since team-charter hosts nothing, it has no Collections section. The skill's step 7 asks about this and only writes the section if the answer is yes. This is correct behavior.

## Observation: Relationships section has no "none" convention

The schema shows Relationships with `links-to` and `linked-from` entries but does not specify what to write when a type has no relationships. I wrote "(none)" but the skill does not define a convention for this. The Brand example in the schema has a `linked-from` entry, but there is no example of a type with zero relationships. The skill could either omit the section entirely or define a "(none)" placeholder convention. Since the schema does not list Relationships as optional (it has no "optional" annotation like Collections and Facets do), it is ambiguous whether omitting it is valid.

## Observation: Conversational step 10 conflates two concerns

Step 10 asks "Where should these documents live?" for standalone types. This is a location question that determines the root type's Collections table entry. However, the key field is not explicitly gathered in step 10. It is implied from the Fields section (using the `name` field as the key). The skill should clarify that the key for the Collections table row comes from the type's fields and should ask the user which field to use as the key/identifier if there are multiple candidates.

## Observation: Template creation mode vs conversational mode

The user asked for "template creation mode." The skill's step 6 defines three modes: template, conversational, and both. The schema also lists a fourth mode: "reverse." The skill's conversational flow in step 6 says to ask the user which mode, but when the user has already specified, the skill should accept that directly. This worked fine here since the user was explicit.

## Observation: status field appears in both Fields and Lifecycle

The user described `status` as an optional enum field. The Lifecycle section also references a `status-field`. The skill does not explicitly state how to handle an optional status field in the lifecycle. Looking at the brand example, status is not listed in required fields but does appear in the Lifecycle section. This suggests the pattern is valid, but the skill could be clearer about whether a lifecycle status field must be required or can be optional. If optional and omitted from a document, the lifecycle transitions would not apply to that document, which is a valid interpretation.

## Observation: Path convention for standalone types

The skill asks the user where documents should live but does not provide guidance on path conventions. The existing root type uses PascalCase for directory names (Brands, Products, People) which matches "display name" style. For consistency, a team-charter collection would likely use `./TeamCharters/` but the convention for kebab-case type names to PascalCase directory names is implicit, not documented.

## Gap: No guidance on the `type` field

Every type definition in the schema examples includes `type: string` as a required field with a fixed value. The skill's conversational flow (step 2, Fields) does not mention automatically including `type` as a required field. It suggests `type`, `created`, and `status` as defaults, but does not mandate that `type` is always required. In practice, every document needs a `type` field for identification, so this should be a hard requirement, not a suggestion.
