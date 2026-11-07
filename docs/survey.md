# Survey: visual forms of research maps

Researched 2026-11-07. Starting point: the GTU Research Map
(<https://tanitim.gtu.edu.tr/arastirma-haritasi/?lang=en>).

## 1. Reference: how the GTU map works

A teardown of the published page, which is one self-contained 16 MB HTML file.

| Aspect | GTU choice |
|---|---|
| Scope | 799 academic staff in 8 units, 693 placed on the map |
| Source | YÖK Akademik public profiles + YÖKSİS CVs (Turkish national systems) |
| Records used | Titles only: articles, conference papers, books, projects, courses, supervised theses (no abstracts) |
| Text model | `intfloat/multilingual-e5-base`, so Turkish and English titles share one space |
| Person vector | 5 weighted parts: publication topics 45, venues 15, courses 15, theses 15, projects 10. Recency weights: last 10 years 1.0, 2006–2015 0.6, older 0.35. PCA to 96 dims, then the TR–EN language direction is removed |
| Layout | t-SNE (cosine) to 2-D |
| Areas | k-means, 12 clusters on the 96-d vectors (not on the 2-D map), named from each cluster's distinctive terms |
| Rendering | D3 v7 (zoom, scales), all data inlined as JSON |
| Search | Offline copy: a word-vector lexicon inlined in the page. Live site: bge-m3 on the university's own server, ranked by each person's best-matching records, with real titles shown as evidence |
| Views | Scatter map (names appear on zoom, hollow circles for people with fewer than 6 records); legend highlight; person card with ORCID/YÖK links and 10 nearest researchers plus shared terms; unit × area count matrix; method notes; TR/EN toggle; KPI header |

What makes it good: one question per view ("who works near whom", "which
unit sits in which area"), evidence on every claim (real titles), a plain
method section, and no server needed for the offline copy.

## 2. Other families of research maps

| # | Family | Examples | What a point or shape is | Borrow | Watch out |
|---|---|---|---|---|---|
| 1 | Semantic map of people | GTU; [PeopleMap](https://arxiv.org/abs/2006.06105) (Georgia Tech, MIT-licensed, [code](https://github.com/poloclub/people-map)); [REMatch](https://smsf.cs.arizona.edu/~kobourov/rematch.pdf) (Arizona, expert matching for research offices) | A researcher; nearness = similar topics | The core view. REMatch's "paste a call for proposals, get matching people with an explanation" is a strong research-office feature | Axes mean nothing; users need labels and a method note |
| 2 | Document landscape with zoom-level labels | [Cartolabe](https://arxiv.org/pdf/2003.00975) (Inria, HAL: 700k papers, 170k authors, UMAP); [DataMapPlot](https://datamapplot.readthedocs.io/en/latest/interactive_intro.html) (deck.gl, layered labels); [Apple Embedding Atlas](https://apple.github.io/embedding-atlas/overview.html) (WebGPU, cross-filter, MIT) | A paper (and authors as a second layer) | Density shading; labels that get finer as you zoom; cross-filter charts beside the map | Needs WebGL past ~50k points |
| 3 | Search-driven topic bubbles | [Open Knowledge Maps](https://openknowledgemaps.org/faq) | A sub-topic bubble built from the top 100 results of one query | "Map this topic at our university" on demand | Built per query, not a standing map |
| 4 | Bibliometric networks | [VOSviewer](https://www.vosviewer.com/features/examples) (co-authorship, term co-occurrence; overlay colour by year or citations; embeddable online version) | A term, author, or institution; links = co-occurrence | Overlay colouring by year to show what is new; Leiden-style clustering | Hairballs past a few hundred nodes |
| 5 | Within-institution collaboration networks | [Northeastern "Inside the Institution"](https://www.networkscienceinstitute.org/news/a-netsi-co-op-student-maps-the-hidden-architecture-of-academic-collaboration-at-northeastern-university) (2,737 faculty; collaboration map, research-units view, bridging-scholars view; only 7.1% have a cross-college tie); [Northwestern CRS](https://www.northwestern.edu/crs/news/2021/visualizing-crs-faculty-collaboration.html); [UCSF departments](https://biomed20.ucsf.edu/2013/11/22/ucsf-collaborations-visualized); [Harvard Catalyst Profiles](https://connects.catalyst.harvard.edu/Profiles/display/person/43793/network/coauthors/radial) (radial and cluster co-author views per person) | A person or department; links = co-authored papers | "Bridging scholars" ranking; per-person radial view | Shows who already works together, not who could |
| 6 | Expertise fingerprints | Elsevier Pure ([Maastricht](https://library.maastrichtuniversity.nl/?p=4225760), [WashU](https://becker.wustl.edu/resources/research-profiles/)) | A weighted concept list per person or unit, plus "similar profiles" | Concept chips on the person card; unit-level fingerprints | Proprietary thesaurus; licence cost |
| 7 | Fixed base map of science with overlays | [UCSD Map of Science](https://cns.iu.edu/2012-UCSDMap.html) (Börner et al.); SciVal Spotlight circle map | A discipline on a fixed global layout; an institution is an overlay | Put every university on the same base so maps can be compared | Coarse; discipline-level only |
| 8 | Hierarchical portfolio charts | Sunburst/treemap ([Kucher & Kerren](https://scitepress.org/publishedPapers/2023/118069/pdf/index.html)); streamgraph over time (Rosenthal et al.); [DIA2](https://cs.au.dk/~elm/pdf/dia2.pdf) | Field → subfield → topic share | Topics-over-time streamgraph for "what is growing here" | Says nothing about individuals |
| 9 | Geographic collaboration maps | [UW Global Engagement map](https://www.washington.edu/global/global-engagement-map) (OpenAlex); [UVic](https://vpri-sri.uvic.ca/collab-map/index.html) (OpenAlex); [Kyushu](https://www3.ir.kyushu-u.ac.jp/en/globalengagement); Pure network map | A country or partner institution | Cheap to add from the same co-author data | Answers a different question (where, not what) |
| 10 | Unit × area matrix | GTU's lower panel | A count cell | The single most readable summary for leadership | None; keep it |

## 3. What a new map could do that GTU does not

- **Co-author links on top of the semantic map.** Two people who sit close
  together but have never co-authored are collaboration candidates. Families
  1 and 5 combined.
- **A shared base map across universities.** Colour by OpenAlex field (26
  fields, same palette everywhere) and optionally place every university on
  one fitted layout, so maps can be compared. Family 7.
- **Zoom-level labels:** broad areas when zoomed out, specific topics when
  zoomed in. Family 2.
- **Year filter and "new topics" colouring.** Family 4's overlay and family 8's streamgraph.
- **"Paste a call for proposals" search** that returns people with their
  matching titles as evidence. REMatch plus GTU's evidence rule.

## 4. Data sources

| Source | Coverage | Departments? | Cost | Notes |
|---|---|---|---|---|
| OpenAlex | Global; works, authors, ORCID, topics (domain/field/subfield/topic), abstracts for many works, institutions with ROR | No | API key required since Feb 2026; a free key gives about $1/day of budget (a list call of up to 200 records costs $0.001, so about 1,000 list calls a day); lookups by ID are free. [Docs](https://developers.openalex.org/api-reference/authentication) | Author disambiguation errors exist; ORCID matching helps |
| University roster | Exactly the people you want, with departments and titles | Yes | Free, but manual or scraped | Needed because OpenAlex's "last known institution" includes students, alumni, staff, and has no department field |
| Institution systems (Pure, Symplectic Elements, VIVO, Activity Insight) | Curated, has departments, sometimes courses and grants | Yes | Needs institutional access | Best data when available |
| National systems (YÖK Akademik, etc.) | Country-specific | Yes | Free, public | What GTU used; adapter per country |
| Semantic Scholar | Strong in CS/biomed; SPECTER embeddings available | No | Free key | Alternative or supplement |

Checked from this container on 2026-11-07: the shared no-key OpenAlex budget
was already used up, so a key is needed. Hugging Face model downloads work.

## 5. Sources

- GTU Research Map: <https://tanitim.gtu.edu.tr/arastirma-haritasi/?lang=en>
- GTU build notes (method, search evaluation, lessons): <https://tanitim.gtu.edu.tr/arastirma-haritasi/nasil-yapildi.html>; summarised in PLAN.md, "Lessons from GTU's build notes"
- PeopleMap: <https://arxiv.org/abs/2006.06105>, <https://arxiv.org/abs/2009.00091>
- REMatch: <https://smsf.cs.arizona.edu/~kobourov/rematch.pdf>
- Cartolabe: <https://arxiv.org/pdf/2003.00975>, <https://www.aviz.fr/Research/Cartolabe>
- DataMapPlot: <https://datamapplot.readthedocs.io/en/latest/interactive_intro.html>
- Embedding Atlas: <https://apple.github.io/embedding-atlas/overview.html>, <https://github.com/apple/embedding-atlas>
- Open Knowledge Maps: <https://openknowledgemaps.org/faq>, <https://elifesciences.org/labs/ef274c83/open-knowledge-maps-a-visual-interface-to-the-world-s-scientific-knowledge>
- VOSviewer: <https://www.vosviewer.com/features/examples>, <https://leidenmadtrics.nl/articles/visualising-quantitative-data-with-vosviewer-will-widen-your-research-projects>
- Northeastern NetSI: <https://www.networkscienceinstitute.org/news/a-netsi-co-op-student-maps-the-hidden-architecture-of-academic-collaboration-at-northeastern-university>
- Northwestern CRS: <https://www.northwestern.edu/crs/news/2021/visualizing-crs-faculty-collaboration.html>
- UCSF: <https://biomed20.ucsf.edu/2013/11/22/ucsf-collaborations-visualized>
- Harvard Catalyst Profiles: <https://connects.catalyst.harvard.edu/Profiles/display/person/43793/network/coauthors/radial>
- Pure fingerprints: <https://library.maastrichtuniversity.nl/?p=4225760>, <https://becker.wustl.edu/resources/research-profiles/>
- UCSD Map of Science: <https://cns.iu.edu/2012-UCSDMap.html>
- Portfolio charts: <https://scitepress.org/publishedPapers/2023/118069/pdf/index.html>, <https://arxiv.org/pdf/2204.11859>, <https://cs.au.dk/~elm/pdf/dia2.pdf>
- Geographic maps: <https://www.washington.edu/global/global-engagement-map>, <https://vpri-sri.uvic.ca/collab-map/index.html>, <https://www3.ir.kyushu-u.ac.jp/en/globalengagement>
- BERTopic on university publications: <https://arxiv.org/pdf/2601.20806>
- OpenAlex keys and pricing: <https://developers.openalex.org/api-reference/authentication>, <https://groups.google.com/g/openalex-users/c/rI1GIAySpVQ>
