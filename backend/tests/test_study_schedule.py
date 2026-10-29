def test_private_study_schedule_persists_and_validates(client, owner, other):
    assert client.get("/api/core/study-schedule").status_code == 401
    assert client.get("/api/core/study-schedule", headers=owner).json() == {"days": None}
    days = [["Sunday study"], [], ["ITT585"], [], [], [], []]
    assert client.put("/api/core/study-schedule", headers=owner, json={"days": days}).status_code == 200
    assert client.get("/api/core/study-schedule", headers=owner).json()["days"] == days
    assert client.get("/api/core/study-schedule", headers=other).json()["days"] is None
    for bad in [[], [["x" * 201]] * 7, [[" "]] * 7]:
        assert client.put("/api/core/study-schedule", headers=owner, json={"days": bad}).status_code == 422
