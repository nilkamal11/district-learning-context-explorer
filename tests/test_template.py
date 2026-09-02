from jinja2 import Environment, PackageLoader


def test_report_template_compiles():
    environment = Environment(loader=PackageLoader("district_context", "templates"))
    template = environment.get_template("district_profile.html.j2")
    assert template.name == "district_profile.html.j2"
