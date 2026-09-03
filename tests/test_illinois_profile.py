from district_context.config import PROJECT_ROOT


def test_illinois_profile_template_has_dashboard_controls_and_dynamic_charts():
    template = (
        PROJECT_ROOT
        / "src"
        / "district_context"
        / "templates"
        / "illinois_grade4_profile.html.j2"
    ).read_text(encoding="utf-8")

    for control_id in (
        "district-filter",
        "school-filter",
        "grade-filter",
        "subject-filter",
        "year-start",
        "year-end",
        "reset-button",
        "download-button",
    ):
        assert f'id="{control_id}"' in template

    assert 'Plotly.react("proficiency-chart"' in template
    assert 'Plotly.react("growth-chart"' in template
    assert 'Plotly.react("context-chart"' in template
    assert "const selectedRows" in template
    assert "north-palos-grade4-filtered.csv" in template
    assert 'id="measurement-guide"' in template
    assert "ELA · English language arts/literacy" in template
    assert "Math · Mathematics" in template
    assert "https://www.isbe.net/iar" in template
    assert "Public-Business-Rules-2024-Report-Card-Metrics.pdf" in template
    assert "Unified-Perf-Levels-FAQ.pdf" in template
    assert "Student-Growth-Percentile-2025.pdf" in template
    assert 'src="assets/plotly-cartesian-3.7.0.min.js"' in template
    assert template.count("{{ proficiency_definition }}") == 2
    assert "minimum proficient scale score changed from 750 to 737 in ELA" in template
    assert "from 750 to 740 in mathematics" in template
    assert "explicitly says not to compare 2025 proficiency rates with prior years" in template
    assert "Built {{ built_at }}" not in template
    assert "Levels 3+4" not in template
    assert "What this can support" not in template
    assert "What it cannot claim" not in template
    assert "No causal effect" not in template
