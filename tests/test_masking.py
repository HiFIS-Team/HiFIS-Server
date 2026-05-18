"""전화번호 마스킹 함수 테스트 (로그 출력용)"""
import pytest

from app.utils.masking import mask_phone


class TestMaskPhone:
    """가운데 4자리만 마스킹 - 앞 prefix와 뒤 4자리는 그대로 노출"""

    def test_mobile_with_hyphens(self):
        assert mask_phone("010-1234-5678") == "010-****-5678"

    def test_mobile_no_hyphens(self):
        assert mask_phone("01012345678") == "010-****-5678"

    def test_seoul_landline(self):
        """서울 02는 2자리 지역번호로 마스킹"""
        assert mask_phone("0212345678") == "02-****-5678"

    def test_seoul_landline_with_hyphens(self):
        assert mask_phone("02-1234-5678") == "02-****-5678"

    def test_internet_phone_070(self):
        assert mask_phone("0701234567") == "070-****-4567"

    def test_too_short_returns_stars(self):
        """7자리 미만은 통째로 마스킹"""
        assert mask_phone("123456") == "****"

    def test_empty_returns_stars(self):
        assert mask_phone("") == "****"

    @pytest.mark.parametrize("input_phone,expected", [
        ("010.1234.5678", "010-****-5678"),
        ("(02) 1234-5678", "02-****-5678"),
    ])
    def test_various_separators(self, input_phone, expected):
        """어떤 구분자가 와도 마스킹 결과는 동일"""
        assert mask_phone(input_phone) == expected
