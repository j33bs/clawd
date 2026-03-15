# UE5 Fantasy Visual Inspirations - 2026-03-13

## Why this note exists

`fantasy_landscape_v2` needs a clear visual target.

Right now the runtime is proving the lane, but the scene can still drift into "engine primitives with mood lighting." That is not enough. The target is a child-delighting 2.5D fantasy tableau with strong silhouette readability, a warm sense of place, and a few animated story beats.

## Reference anchors

### Spiritfarer

Source:
- <https://thunderlotus.itch.io/spiritfarer-art-book>

Useful signal:
- Thunder Lotus explicitly frames the project as a colorful, cozy, hand-drawn work.

What to borrow:
- warmth over spectacle
- readable silhouettes before fine detail
- charm through shape language, not visual noise
- animated life in small beats: smoke, water drift, creature loops, lantern warmth

### Child of Light

Source:
- <https://www.ubisoft.com/en-us/company/about-us/our-brands/child-of-light>

Useful signal:
- Ubisoft describes it as a "playable poem" with a dream-like style where concept art was inserted unedited to resemble an interactive painting.

What to borrow:
- flatter storybook staging
- fewer large forms, each with a clear role
- painterly layer separation: sky, ridges, meadow, props, characters, glow accents
- theatrical composition, with one obvious focal area instead of visual competition everywhere

### Ori and the Blind Forest

Sources:
- <https://www.xbox.com/en-US/games/store/ori-and-the-blind-forest-definitive-edition/9NBLGGH1Z6FB>
- <https://news.xbox.com/en-us/2016/04/27/ori-and-the-blind-forest-definitive-edition-debuts-on-windows-10-and-steam/>

Useful signal:
- Xbox emphasizes hand-painted artwork, meticulous character animation, and a fully orchestrated emotional presentation.

What to borrow:
- deep atmosphere without flattening the frame
- strong foreground/midground/background separation
- careful motion hierarchy: not everything moves, but what moves feels alive
- readable creatures against layered backgrounds

## The actual target for Dali fishtank

This scene should not chase realism.

It should feel like:
- a bedtime-story landscape
- cozy enough for a 9- and 11-year-old to immediately parse
- magical enough that the dragon, cave artifact, ducks, pond, and cabin feel like a little world instead of debug props

## Practical scene rules

1. One hero focal cluster

- The cabin + porch + pond should be the hero.
- The cave artifact is a secondary mystery.
- The dragon is a tertiary event, not the main read of every frame.

2. Silhouette first

- House shape must read clearly in black silhouette.
- Ducks must read as ducks in water and in takeoff.
- The dragon must read as one creature, not a string of tokens.

3. Layer families stay distinct

- sky = broad, calm, low-detail
- ridges = shape rhythm
- meadow = grounding plane
- house/props = story
- characters = emotional anchors
- glow accents = restraint, not flood

4. Motion hierarchy

- constant low motion: clouds, smoke, water shimmer
- medium periodic motion: ducks, fish, rocking chair
- rare event motion: dragon pass + fire breath

5. Night palette discipline

- the scene should be dark enough to feel nocturnal
- only a few things should truly glow:
  - moon rim
  - windows
  - cave artifact
  - fire breath
  - fireflies

6. Delight is in legibility

- children do not need more objects
- they need clearer shapes, stronger color grouping, and a friendlier camera

## Immediate art-direction corrections

1. Stop solving composition with more primitives.
2. Push toward a 2.5D illustrated kit:
   - house body
   - roof halves
   - porch
   - duck poses
   - dragon poses
   - tree canopies
   - cave mouth
   - shoreline/reeds
3. Keep C++ responsible for orchestration and timing, not forever-hand-authoring every visual transform.
4. Use the references above as discipline:
   - Spiritfarer for warmth and shape language
   - Child of Light for painterly staging
   - Ori for atmosphere and motion hierarchy

## Current blocker

The scene code is now more modular, but the runtime capture is still washing the frame out close to white. That means the next useful pass is render/camera/material calibration, not adding more props.
