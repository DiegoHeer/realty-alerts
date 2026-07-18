def test_mjml_python_compiles_basic_document():
    from mjml import mjml2html

    html = mjml2html("<mjml><mj-body><mj-section><mj-column>"
                     "<mj-text>Hi</mj-text></mj-column></mj-section></mj-body></mjml>")
    assert "<html" in html.lower()
    assert "Hi" in html
