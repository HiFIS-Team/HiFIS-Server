"""GET /enums 통합 테스트 - Phase A에서 trigger_type/source_type 추가됨"""


class TestEnumsEndpoint:

    def test_enums_returns_all_groups(self, client):
        """모든 enum 그룹 반환 (gender·referral·payment_method·motivation·trigger_type·source_type)"""
        res = client.get("/enums")
        assert res.status_code == 200
        body = res.json()
        assert {
            "gender", "referral", "payment_method",
            "motivation", "trigger_type", "source_type",
        } <= set(body.keys())

    def test_trigger_type_includes_known_triggers(self, client):
        """trigger_type에 주요 트리거(REGISTERED, HOLD, EXPIRED_TODAY 등) 포함 + 한국어 라벨"""
        res = client.get("/enums")
        body = res.json()
        codes = {item["code"] for item in body["trigger_type"]}
        assert {"REGISTERED", "HOLD", "HOLD_CANCEL",
                "EXPIRED_TODAY", "EXPIRED_FOLLOWUP"} <= codes

        # 라벨이 비어 있지 않아야 (한국어)
        labels = {item["code"]: item["label"] for item in body["trigger_type"]}
        assert labels["REGISTERED"]
        assert labels["HOLD"]

    def test_source_type_includes_all_sources(self, client):
        """source_type에 4종(MEMBER, PT_APPLICATION, RESERVATION, HOLD) 포함"""
        res = client.get("/enums")
        body = res.json()
        codes = {item["code"] for item in body["source_type"]}
        assert {"MEMBER", "PT_APPLICATION", "RESERVATION", "HOLD"} <= codes
