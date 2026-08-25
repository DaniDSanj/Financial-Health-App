"""Tests de las plantillas (Polish)."""


def test_login_page_disables_password_autocomplete(client) -> None:
    response = client.get("/login")
    assert 'autocomplete="off"' in response.text
    # Confirma que el atributo está específicamente en el campo password, no en
    # cualquier lugar.
    password_field_start = response.text.index('name="password"')
    surrounding = response.text[
        max(0, password_field_start - 20) : password_field_start + 100
    ]
    assert 'autocomplete="off"' in surrounding
