async def test_index_returns_200(client):
    response = await client.get("/")
    assert response.status_code == 200


async def test_healthz_returns_ok(client):
    response = await client.get("/healthz")
    assert response.status_code == 200
    assert response.json() == {"status": "ok"}
