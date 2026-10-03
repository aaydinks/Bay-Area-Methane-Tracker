import json

from methanewatch.provenance import PullManifest, read_manifests, sha256_file


def test_manifest_round_trip(tmp_path):
    m = PullManifest.start("carbonmapper", "plumes", {"site": "newby-island", "radius_km": 5})
    pull_dir = tmp_path / "carbonmapper" / m.pull_id
    pull_dir.mkdir(parents=True)
    f = pull_dir / "page-001.json"
    f.write_text(json.dumps({"items": [1, 2, 3]}))
    m.finish(pull_dir, [f], n_records=3)

    [loaded] = read_manifests(tmp_path)
    assert loaded["n_records"] == 3
    assert loaded["files"] == {"page-001.json": sha256_file(f)}
