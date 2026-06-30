# ALI-12 — Deck building: commander, colour-identity & format-legality filtering

**Status:** Design approved (2026-06-30)
**Linear:** ALI-12
**Branch:** `madcabbage/ali-12-deck-building-commander-colour-identity-format-legality`
**Delivery:** one PR, split into ordered commits (no DB migration).

## Goal

The primary use case. Create decks, set a commander, add cards filtered by
**colour identity** and **format legality**, and **build decks from cards you
already own** — with the seamless storage⇄deck movement that is CabbyCards'
ALI-18 differentiator.

## Decisions (resolved in brainstorm)

1. **Full vertical slice** — backend API + Scryfall filtering + Vue deck-builder
   UI, in one PR (ordered commits).
2. **Auto-allocate owned copies on add** — adding `quantity` of a card always
   sets/increments its `deck_entry` (the intent); if the user owns matching
   copies in storage, **up to `quantity`** of them are also pulled into the deck
   location (capped at what's available). Not owned → entry-only; the shortfall
   feeds the ALI-14 wantlist.
3. **Scryfall live search with native filter syntax** for the card picker
   (`id<=<identity>`, `legal:<format>`); returned cards are cached into the local
   `cards` table as they are seen.
4. **Filter + validate, don't hard-block** — the picker is filtered by the
   commander's identity + format by default (with a "show all" escape hatch);
   cards still get added freely; the deck surfaces a validation summary of any
   violations. No API-level rejection of "illegal" adds.
5. **Printing-exact + finish/condition-exact allocation** — auto-allocation
   matches the exact `(card_id, foil, condition)` holding stack the user
   selected and `move_holding`s it from storage. Ownership *counts*
   (owned-elsewhere, missing) remain oracle-level for the wantlist; the physical
   move is printing-exact. This mirrors how adding to a collection should work
   (choose exact printing + finish + condition — see ALI-22).
6. **Shared `PrintingSelector` component**, used in the deck builder only for
   now. ALI-22 later reuses the same component in collection-add (no rework).

## Data model

**No migration.** ALI-18 already provides everything:

- `decks` (`location_id` PK, `format`, `commander_card_id`)
- `deck_entries` (`deck_id`, `card_id`, `board`, `desired_quantity`; unique on
  `(deck_id, card_id, board)`)
- `holdings` (`location_id`, `card_id`, `quantity`, `foil`, `condition`; unique
  on `(location_id, card_id, foil, condition)`)
- `locations` (`user_id`, `name`, `kind`)
- card attributes for filtering/validation (`color_identity`, `legalities`,
  `type_line`) live in `cards.data` (JSONB).

### Ownership matching is oracle-level; entries & holdings are per-printing

A `deck_entry` names a specific printing (`cards.id`), and an auto-allocated
holding is a specific physical printing. But "do I own this card?" matches at
`oracle_id` (ALI-13/ALI-18): any printing of *Sol Ring* fulfils a desired *Sol
Ring*. So the deck read-model's ownership math groups holdings by the entry
card's `oracle_id`:

- `allocated_qty` = Σ holdings **at the deck location** sharing the entry's
  `oracle_id`
- `owned_elsewhere_qty` = Σ holdings **at other locations** with that `oracle_id`
- `missing_qty` = `max(0, desired_qty − allocated_qty − owned_elsewhere_qty)`
  → feeds the ALI-14 wantlist

The **physical** auto-allocation path is printing-exact (matches the exact
stack); only the **counts** above are oracle-level.

## Backend — service layer

New module **`app/services/deck_builder.py`** (keeps the growing `inventory.py`
to primitive CRUD; this module orchestrates on top of those primitives:
`set_deck_entry`, `move_holding`, `ensure_default_location`).

- `add_card_to_deck(session, *, deck, card_id, board, quantity, foil, condition,
  auto_allocate=True)` — single transaction: upsert/increment the `deck_entry`;
  if `auto_allocate`, `move_holding` up to `quantity` copies of the matching
  `(card_id, foil, condition)` stack from storage into the deck location (capped
  at the available quantity). Entry-only when not owned.
- `remove_card_from_deck(session, *, deck, card_id, board, quantity)` —
  decrement/delete the entry; de-allocate by moving any deck-located copies back
  to the default "Unsorted" storage (cards are never lost — ALI-18).
- `set_commander(session, *, deck, commander_card_id)` — store it; validation
  flags an illegal commander rather than rejecting.
- `delete_deck(session, *, deck)` — relocate all deck-located holdings to
  "Unsorted", then delete the deck + location (entries cascade).
- `build_deck_view(session, *, deck)` — the computed read model: deck meta +
  per-card rows (`deck_entry` joined with oracle-level allocation/ownership) +
  validation summary. One aggregation; no client-side math.

**Validation** is a pure function `deck_violations(deck_cards,
commander_identity, format)` returning violation codes (no DB, trivially
unit-testable):

- per card: `off_colour_identity` (card's `color_identity` ⊄ commander's),
  `not_format_legal` (`legalities[format]` ∉ {`legal`, `restricted`})
- deck-level (Commander/Brawl): `singleton_violation` (>1 of a non-basic),
  `wrong_size` (≠ 100 incl. commander), `no_commander`

## Backend — API

New router **`app/api/routes/decks.py`** (`prefix="/decks"`), plus two
card-catalogue endpoints. All deck endpoints authorise via a new
`get_owned_deck` helper (mirrors `get_owned_location` → 404 if not the user's).

Deck lifecycle:
- `POST /decks` — `{name, format, commander_scryfall_id?}` → cache commander,
  create deck, return deck view.
- `GET /decks` — list (summary: name, format, commander, distinct-card count,
  owned %).
- `GET /decks/{id}` — full deck view.
- `PATCH /decks/{id}` — edit `name` / `format` / `commander`.
- `DELETE /decks/{id}` — relocate holdings to "Unsorted", then delete.

Deck contents:
- `POST /decks/{id}/cards` — `{scryfall_id, board, quantity, foil, condition,
  auto_allocate=true}` → `add_card_to_deck`, returns the updated deck-card row.
- `PATCH /decks/{id}/cards` — change `desired_quantity` / move board.
- `DELETE /decks/{id}/cards/{card_id}?board=…` → `remove_card_from_deck`.

Card catalogue (feeds the picker):
- `GET /cards/search?q=…&deck_id=…` — Scryfall-live search with the deck's
  identity/format filters appended; caches results.
- `GET /cards/{scryfall_id}/printings` — all printings of a card (set, collector
  №, available finishes, image) for the `PrintingSelector`.

Schemas in **`app/schemas/deck.py`**: `DeckCreate`, `DeckUpdate`, `DeckSummary`,
`DeckView`, `DeckCardOut` (`{card, board, desired_qty, allocated_qty,
owned_elsewhere_qty, missing_qty, violations}`), `AddDeckCardRequest`,
`UpdateDeckCardRequest`.

## Backend — Scryfall filtering

Extend `app/services/scryfall.py` with `search_cards(query, *, identity=None,
format=None)`:

- Builds Scryfall's `q`: user terms + `id<=<identity>` (e.g. `id<=wub`;
  colourless commander → `id:c`) + `legal:<format>`. No commander set → format
  filter only.
- Hits `/cards/search`, **first page only for v1** (full pagination is ALI-10 —
  leave a `# See ALI-10` note, don't build it here).
- Upserts every returned card into the local `cards` table via the existing
  ingest path, so later picks/adds resolve by `scryfall_id` with no extra fetch.
- Reuses the service's existing politeness (UA header, ~100ms spacing).

Colour identity is derived as `"".join(commander.data["color_identity"]).lower()`.
`deck_violations` independently re-checks identity locally (defence in depth, and
it covers cards added via "show all").

## Frontend

Routing: add `/decks` (list) and `/decks/:id` (builder), both `requiresAuth`;
header gains Collection ⇄ Decks nav.

Store `stores/decks.ts` (mirrors `collection.ts`): state `{ decks, current }`;
actions `fetchDecks`, `createDeck`, `fetchDeck`, `addCard`, `updateCard`,
`removeCard`, `setCommander`, `deleteDeck` — all via `lib/api.ts`.

Views:
- `DecksView.vue` — deck grid + "New deck" (name, format, commander search).
  Per-deck: commander art, format, card count, owned %.
- `DeckBuilderView.vue` — Archidekt-style stacked layout: commander header strip,
  board tabs (Main / Side / Maybe / Command), cards grouped into type columns
  (Creatures, Instants, Sorceries, Artifacts, Enchantments, Planeswalkers, Lands)
  as stacked thumbnails with a quantity badge; right-hand filtered add panel; a
  validation summary panel.

Components:
- `PrintingSelector.vue` — shared picker: set/printing dropdown (from
  `/cards/{id}/printings`), finish (from the printing's `finishes`), condition
  (`CardCondition`). Emits `{scryfall_id, foil, condition}`.
- Extend `AddCardSearch.vue` to take deck context → filtered results → on pick,
  open `PrintingSelector` → confirm adds via the store.
- Reuse `CardView.vue` for thumbnails. Each card row shows desired / allocated /
  owned-elsewhere / missing with a colour cue (green = fully in deck, amber =
  owned but not allocated, red = missing → wantlist).

## Error handling

- Not-owned deck/holding → 404 (existing pattern). `InsufficientQuantity` → 400
  (existing). Scryfall failures → 404/502 as in `cards.py`.
- "Add a card you don't own" is not an error — entry-only, no move, surfaces as
  `missing_qty`.
- Commander/format changes that orphan cards are allowed; they appear in the
  validation summary (the no-hard-block decision).

## Testing

Per the "every function has a test" + `See:` docstring convention.

- Hermetic pytest for every `deck_builder` function — auto-allocate
  owned/not-owned/partial paths, remove/de-allocate, `delete_deck` relocation,
  `build_deck_view` aggregation, `set_commander`.
- `deck_violations` pure-function tests — one per violation code.
- `scryfall.search_cards` query-building tests via the injectable
  `httpx.MockTransport`.
- `test_decks_api.py` — every endpoint, ownership 404s, validation payloads
  (follows `test_collection_api.py`).
- Opt-in DB integration test (`CABBYCARDS_DB_TESTS`) for the read-model
  aggregation.
- Vitest specs for `stores/decks.ts` and `PrintingSelector.vue` (follows
  `collection.spec.ts` / `AddCardSearch.spec.ts`).

## Commit sequence (one PR)

1. `deck_builder` service + `deck_violations` + tests
2. `decks` API router + schemas + `get_owned_deck` + tests
3. Scryfall `search_cards` filtering + `/cards/search` + `/cards/{id}/printings`
   + tests
4. `stores/decks.ts` + routing + nav + store tests
5. `DecksView` + `DeckBuilderView`
6. Shared `PrintingSelector` + `AddCardSearch` deck integration + specs

## Out of scope (explicit)

- Scryfall search **pagination** / rate-limit backoff hardening → ALI-10.
- Owned-only **filter toggle** in the picker → ALI-13 (the read model already
  exposes ownership; the toggle is a separate slice).
- Wantlist **export** → ALI-14 (this slice produces `missing_qty`, the input).
- Retrofitting `PrintingSelector` into collection-add → ALI-22.
- Mana-curve / price / advanced deck stats.
