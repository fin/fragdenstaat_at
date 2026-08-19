# 8.19.x, matching fragdenstaat_de. Do not drop below 8.16: the
# hyphenation_decompounder's `no_sub_matches` option (theme/search.py) is
# silently ignored by older 8.x releases -- no error, just spurious subtokens
# like "formation"/"format"/"form" for "Informationsfreiheit", which quietly
# degrades search quality. theme/tests/test_search.py detects this and skips
# rather than failing, so a stale image shows up as skips, not red tests.
#
# 8.15 -> 8.19 is within one major version, so the existing es-data volume is
# compatible. (The earlier 7.15 -> 8.x bump was not, and had to be reverted.)
FROM docker.elastic.co/elasticsearch/elasticsearch:8.19.3

# Pinned to the same commit as fragdenstaat_de rather than tracking master:
# these files define how German compounds are split, so an upstream change would
# silently move the token expectations in theme/tests/testdata/search_tokens.py.
ARG DECOMPOUNDER_REV=6227be052f4215294b5a5d498cdcdadfcf7196e6
RUN mkdir -p /usr/share/elasticsearch/config/analysis \
    && curl -fsSL -o /usr/share/elasticsearch/config/analysis/de_DR.xml \
       "https://raw.githubusercontent.com/uschindler/german-decompounder/${DECOMPOUNDER_REV}/de_DR.xml" \
    && curl -fsSL -o /usr/share/elasticsearch/config/analysis/dictionary-de.txt \
       "https://raw.githubusercontent.com/uschindler/german-decompounder/${DECOMPOUNDER_REV}/dictionary-de.txt"
