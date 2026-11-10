def test_browser_may_send_school_header(client):
    """The dashboard (another origin) must be allowed to send X-School-ID."""
    r = client.options(
        "/api/v1/children/",
        HTTP_ORIGIN="http://localhost:3000",
        HTTP_ACCESS_CONTROL_REQUEST_METHOD="GET",
        HTTP_ACCESS_CONTROL_REQUEST_HEADERS="authorization,x-school-id",
    )
    assert r.status_code == 200
    assert "x-school-id" in r["access-control-allow-headers"]
