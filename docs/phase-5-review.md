# Phase 5 review

The owner approved phase 4 and requested three follow-up changes before release
preparation. This phase completes those changes and prepares version 0.1.0.

## Names and credits

The MIT copyright holder and README credits now use **Beak Tech Community
Interest Company**.

Species matching accepts unique whole-word endings of common names among
species present in the retained input. Swallow, Wren and Robin all follow this
rule; the hard-coded Robin alias has been removed. A short match prints the
chosen common and scientific names to standard error. Multiple matches produce
an error listing all candidates. Exact scientific/common names take precedence;
recorded common names take priority over bundled names. Case-insensitive
matching and close-match suggestions remain.

New synthetic tests cover unique and ambiguous matches, multiple-word endings,
case and surrounding whitespace, exact-name precedence, recorded-name priority,
whole-word boundaries, repeated records and CLI notices/errors.

## README charts

The two README images were regenerated through the package from
`scripts/data/seasonal-2026.json` in the website checkout. No detection exports
or databases were read. The README credits
[What autumn sounds like in the Lakes](https://beaktech.org/blog/listening-to-autumn).

`examples/regenerate_article.py` reproduces the images from that external file
and an optional logo. It uses the Keswick house martin quarter-hour counts and
the three stations' house martin daily counts, covering 111 days from 20 June
to 8 October 2026. Unknown values remain unknown; the package computes the
seven-day averages. Keswick's quarter-hour totals equal its daily counts on
every day. The source JSON and its metadata are not copied into this repository.

Comparison against the website's published PNGs at the same resolution:

| Chart | Comparison |
| --- | --- |
| Keswick heatmap, 2400 × 1680 | Pixel-for-pixel identical: zero changed pixels. |
| Daily counts, 2160 × 2016 | 5,723 of 4,354,560 pixels differ (0.13143%). All differences lie in the Haverthwaite grey gap for 15 July, reflecting the previously approved centring correction. |

Both regenerated images were visually inspected. The website checkout was not
modified. `examples/generate.py` remains unchanged and synthetic; its CSV, SVG
and PNG outputs stay under ignored `.local/`.

## Release preparation and validation

- Package version: **0.1.0**. `CHANGELOG.md` describes the first release and
  explicitly marks it prepared, not published.
- GitHub Actions runs pytest and the synthetic example generator on Python 3.10
  and the latest stable Python 3. The `3.x` matrix entry and `check-latest: true`
  follow [setup-python's documented version selection](https://github.com/actions/setup-python/blob/main/docs/advanced-usage.md#using-the-python-version-input).
  The workflow has read-only repository permissions and no publishing steps.
- **194 tests pass on Python 3.10.21 and Python 3.15.0.** Both environments also
  render the synthetic examples successfully. Python 3.10 uses Matplotlib
  3.10.9 and NumPy 2.2.6; Python 3.15 uses Matplotlib 3.11.2 and NumPy 2.5.4.
- Source distribution and wheel build locally. The source manifest includes
  documentation, examples, the changelog and all test support files; ignored
  local data and environments are excluded. The wheel contains the English
  lookup, its CC BY 4.0 notice and the updated MIT licence.

Hosted CI has not run: the repository has not been published or pushed. Local
checks pass; the owner will publish when ready. No blocking questions remain.
