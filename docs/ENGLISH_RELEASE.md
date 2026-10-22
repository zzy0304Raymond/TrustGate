# English release and experiment provenance

The repository documentation, demonstration, console messages, and
review annotations are published in English. The original trial measurements,
case identities, task definitions, attack payloads, model requests, permissions,
and experiment manifests are unchanged.

The original manifests also fingerprint reporting and validation files. Their
recorded hashes predate this language revision. `english_revision.json` preserves
those original hashes alongside the exact SHA256 of each English file. The
validation entry points use `release_integrity.recorded_digest` to recognize only
these explicitly listed revisions. An unlisted or subsequently edited file still
fails its original check. The map is not permission to modify the experiment.

Run `python scripts/reproduce.py` to verify the release map, recompute the public
statistics, and compare them with the published results. Full MCP and detector
validation is described in [the reproduction guide](REPRODUCE_ZH.md).
The verification receipt records the actual byte hashes of the reproduction
script and the English revision map, alongside the checked Git commit.

Files with a legacy `_ZH` suffix retain their names because earlier frozen
manifests and provenance references use those paths; their current content is
English. Earlier Git revisions remain the historical record of the experiment.
