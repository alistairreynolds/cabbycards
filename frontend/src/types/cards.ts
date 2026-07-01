/** A card as returned by the search endpoints (Scryfall live + deck-filtered). */
export interface SearchCard {
  scryfall_id: string
  name: string
  data: Record<string, unknown>
}
