import jinja2


def test_render_template_smoke():
    tmpl = jinja2.Template("Hello {{ name }}")
    assert tmpl.render(name="World") == "Hello World"
