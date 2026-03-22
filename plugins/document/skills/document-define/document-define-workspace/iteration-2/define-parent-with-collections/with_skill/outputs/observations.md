# Observations

## Issues Fixed from Iteration 1

### Issue #3: Collections key fields now match child types' actual field names

Fixed. The initiative type uses `title` as its identifier field, not `name`. The epic type also uses `title`. The program's Collections table now correctly uses `title` as the Key for both:

| Collection | Type | Key | Path |
|------------|------|-----|------|
| initiatives | initiative | title | ./initiatives/{title}/index.md |
| epics | epic | title | ./epics/{title}.md |

In iteration 1, the Key column used `name` for both, which does not match any field in the child type definitions. The skill instructions are clear that Key must reference "the field in the child type used as the filename/identifier."

### Issue #1: Dual hosting documented as valid

Fixed. The root-update document now explicitly states that the root-level initiatives row stays. Initiatives can live at `./Initiatives/{title}/index.md` (standalone, root level) AND at `./Programs/{name}/initiatives/{title}/index.md` (under a program). The schema's design principle #6 supports this: "Types can live in multiple places."

Epics also have dual hosting: under initiatives (initiative type's Collections table) and directly under programs (program type's Collections table).

### Issue #10: Registration handles both standalone and parent roles

Fixed. The program type is registered in the root type's Collections table (standalone) AND declares its own Collections table (parent). Step 10 of the define operation handles both. The root-update document now explains these are not mutually exclusive.

### Issue #2: Initiative path is a directory hub

Fixed. The initiative type has its own Collections table (hosts epics at `./epics/{title}.md`). This means initiative instances are directory hubs, not flat files. The program's Collections path now uses `./initiatives/{title}/index.md` instead of `./initiatives/{title}.md`. This matches the root type's existing pattern: `./Initiatives/{title}/index.md`.

## Remaining Issues

### 1. No cascade behavior for lifecycle transitions

When a program moves to `completed`, its child initiatives and epics are not automatically transitioned. The skill has no cascade semantics. Each type manages its own lifecycle independently. This is arguably correct (avoids surprise side effects), but a program marked `completed` with `active` initiatives is semantically inconsistent. Consider adding a validation warning (not enforcement) in a future iteration.

### 2. Epics have three valid locations

With this definition, an epic can live in three places:
- Under an initiative at root level: `./Initiatives/{title}/epics/{title}.md`
- Under an initiative within a program: `./Programs/{name}/initiatives/{title}/epics/{title}.md`
- Directly under a program (no initiative): `./Programs/{name}/epics/{title}.md`

The epic skill's create operation must present all valid locations. The skill instructions say "ask which parent to use," but three levels of nesting may confuse users. Consider whether direct-under-program epics are a needed pattern or an accidental artifact.

### 3. Collection scaffolding for nested hubs

When a program is created, it scaffolds `initiatives/` with an index. When an initiative is then created under that program, it scaffolds its own `epics/` subdirectory. This two-step scaffolding works but means an empty program has two empty indexes (initiatives/index.md and epics/index.md) while an initiative under it would create a third (initiatives/{title}/epics/index.md). The file count grows quickly for sparse programs.

### 4. Root type's existing Collections table uses correct keys

Worth noting: the root type (product-portfolio.md) already uses `title` as the key for initiatives and `title` for decisions. The iteration-1 output showed `name` for those keys, which was stale data. The actual root type definition is correct and consistent.
