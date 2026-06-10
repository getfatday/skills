# People Links Audit: Functional Areas

## Summary

All 36 `engineering_leader` fields across Functional Area index files use plain text names. None are linked to People files. The portfolio's CLAUDE.md convention states: "Cross-references in frontmatter use markdown link syntax." However, only 1 of the 35 unique people referenced has a People file today (Ed Hodges, referenced in `Experience Platform/index.md`). The remaining names have no People files to link to.

Additionally, `Experience Platform/index.md` has `lead: Ed Hodges` as a plain text name instead of a person slug, which is inconsistent with how `lead` is used elsewhere (e.g., `lead: ianderson` in the Design System team).

## Existing People Files

| File | Name |
|------|------|
| `People/cbates.md` | Cameron Bates |
| `People/dstrugnell.md` | David Strugnell |
| `People/ianderson.md` | Ian Anderson |
| `People/joschmidt.md` | Jordan Schmidt |
| `People/jotanner.md` | Joonas Tanner |
| `People/lmeadow.md` | Lucy Meadow |

None of these people appear as `engineering_leader` values. The only person with both a People file and a reference in Functional Areas is **Ian Anderson** (`People/ianderson.md`), but that person appears as `lead: ianderson` on Design System, not as an `engineering_leader`.

## All Unlinked engineering_leader References

| Functional Area | engineering_leader value | People file exists? |
|----------------|------------------------|-------------------|
| Acquisition Landing | Camila Kill | No |
| Agentic Servicing | Ryan Hillman | No |
| AI + Analytics Platform | Sabeena Shafaq | No |
| Air Supply | (not set) | N/A |
| Booking Platform | (not set) | N/A |
| BTT Ops | (not set) | N/A |
| Checkout | Namita Raigandhi | No |
| Cloud, Observability & Reliability Platform | GAP | N/A (vacancy marker) |
| Content | Bogdan Vulcan | No |
| Corporate Systems and Infrastructure | Chris Burgess | No |
| Cyber Security | Ambrish Srivastava | No |
| Data Platform | Shao Xie | No |
| Developer Experience | Donata Wonsowicz | No |
| Edge + API Platform | Mohammed Abdulghani | No |
| EG Advertising | Pooja Seth | No |
| Enterprise & Cross Domain Data Products | Alice Zhang | No |
| Experience Platform | Ed Hodges | No |
| Fraud and Risk | Amitabh Ghosh | No |
| Global Governance, Risk, Compliance & Privacy Operations | Neena Ballard (Interim) | No |
| Growth & Comms | Sruthi Samraj | No |
| H4P / Hcom KTLO | Cristiano Bellofiore | No |
| Homepage Ecosystem | Sruthi  Samraj | No |
| Identity | Bhakti Sanap | No |
| InsurTech | Rajat Arora | No |
| Lodging Connectivity | Dhiraj Kumar | No |
| Marketplace Trust | Bogdan Vulcan | No |
| ML - Booking and Post Booking | Hilary Lurie-Malina | No |
| ML - Emerging BU | Roopesh Ranjan | No |
| ML - Shopping and Membership | Zoe Yang | No |
| ML - Yield and Marketplace | Kun Zan | No |
| Multi-Product Shopping | Andrea Pund | No |
| Partnerships | Rajat Arora | No |
| Payments | Ian Butcher | No |
| Post Booking | Ryan Hillman | No |
| Pricing | Bogdan Vulcan | No |
| Product Experience & Offers | Ryan Desjardins | No |
| Search and Recs | Jordan Houari | No |
| Supply Partner Experience | Emil Riccardi | No |
| Universal Messaging Platform | Ramnath Shanbhogue | No |

## Additional Issues Found

### 1. Double space typo in Homepage Ecosystem

**File:** `Functional Areas/Homepage Ecosystem/index.md`

```yaml
# Before
engineering_leader: Sruthi  Samraj

# After
engineering_leader: Sruthi Samraj
```

### 2. lead field uses plain text name instead of person slug

**File:** `Functional Areas/Experience Platform/index.md`

The `lead` field should be a person slug (like `ianderson`) per usage elsewhere, but it contains a full name:

```yaml
# Before
lead: Ed Hodges

# After (if People file existed)
lead: ehodges
```

## Recommended Fixes

### Phase 1: Fix data quality issues (no People files needed)

1. Fix the double-space typo in `Homepage Ecosystem/index.md`.

### Phase 2: Create People files for engineering leaders, then link

To properly link `engineering_leader` fields, People files would need to be created first. There are **28 unique people** referenced (excluding "GAP" which is a vacancy marker):

| Name | Appears in N areas | Suggested userid |
|------|-------------------|-----------------|
| Bogdan Vulcan | 3 | bvulcan |
| Rajat Arora | 2 | rarora |
| Ryan Hillman | 2 | rhillman |
| Sruthi Samraj | 2 | ssamraj |
| Alice Zhang | 1 | azhang |
| Ambrish Srivastava | 1 | asrivastava |
| Amitabh Ghosh | 1 | aghosh |
| Andrea Pund | 1 | apund |
| Bhakti Sanap | 1 | bsanap |
| Camila Kill | 1 | ckill |
| Chris Burgess | 1 | cburgess |
| Cristiano Bellofiore | 1 | cbellofiore |
| Dhiraj Kumar | 1 | dkumar |
| Donata Wonsowicz | 1 | dwonsowicz |
| Ed Hodges | 1 | ehodges |
| Emil Riccardi | 1 | ericcardi |
| Hilary Lurie-Malina | 1 | hlurie-malina |
| Ian Butcher | 1 | ibutcher |
| Jordan Houari | 1 | jhouari |
| Kun Zan | 1 | kzan |
| Mohammed Abdulghani | 1 | mabdulghani |
| Namita Raigandhi | 1 | nraigandhi |
| Neena Ballard | 1 | nballard |
| Pooja Seth | 1 | pseth |
| Ramnath Shanbhogue | 1 | rshanbhogue |
| Roopesh Ranjan | 1 | rranjan |
| Ryan Desjardins | 1 | rdesjardins |
| Sabeena Shafaq | 1 | sshafaq |
| Shao Xie | 1 | sxie |
| Zoe Yang | 1 | zyang |

Once People files exist, the `engineering_leader` field could be converted from plain text to a markdown link. Example for Experience Platform:

```yaml
# Before
engineering_leader: Ed Hodges

# After
engineering_leader: "[Ed Hodges](../../People/ehodges.md)"
```

### Phase 3: Fix the lead field on Experience Platform

Once `People/ehodges.md` exists:

```yaml
# Before
lead: Ed Hodges

# After
lead: ehodges
```

## Scope Assessment

- **Immediate fixes (no blockers):** 1 typo fix (Homepage Ecosystem double space)
- **Blocked on People file creation:** 28 new People files needed before engineering_leader fields can be linked
- **Total files that would change:** Up to 36 Functional Area index files + 1 lead field fix
- **Type definition note:** The `functional-area` type defines `engineering_leader` as `string`, not `link`. If linking is desired, the type definition at `.config/documents/types/functional-area.md` should also be updated to `engineering_leader: link` to match the convention.
