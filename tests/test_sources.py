from district_context import sources


def test_skip_hash_is_disclosed_in_inventory(tmp_path, monkeypatch):
    source_file = tmp_path / "source.csv"
    source_file.write_text("id,value\n1,2\n", encoding="utf-8")
    expected = "a" * 64
    monkeypatch.setattr(sources, "raw_data_dir", lambda: tmp_path)
    monkeypatch.setattr(
        sources,
        "source_config",
        lambda: {
            "test_source": {
                "version": "1",
                "required_filename": "source.csv",
                "required_columns": ["id", "value"],
                "expected_min_bytes": 1,
                "sha256": expected,
            }
        },
    )
    result = sources.verify_sources(compute_hashes=False, write_inventory=False)[0]
    assert result["valid"]
    assert result["expected_sha256"] == expected
    assert result["observed_sha256"] is None
    assert result["hash_verified"] is False
