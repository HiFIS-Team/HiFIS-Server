"""전화번호 검증/정규화 함수 테스트"""
import pytest

from app.utils.validators import is_valid_phone, normalize_phone


class TestNormalizePhone:
    """하이픈·공백·괄호 등 제거 후 숫자만 남기는지"""

    def test_strips_hyphens(self):
        assert normalize_phone("010-1234-5678") == "01012345678"

    def test_strips_spaces(self):
        assert normalize_phone("010 1234 5678") == "01012345678"

    def test_strips_parens(self):
        assert normalize_phone("(02)1234-5678") == "0212345678"

    def test_mixed_separators(self):
        assert normalize_phone("010.1234-5678") == "01012345678"

    def test_only_digits_unchanged(self):
        assert normalize_phone("01012345678") == "01012345678"

    def test_empty_string(self):
        assert normalize_phone("") == ""


class TestIsValidPhone:
    """9~12자리 숫자만 통과"""

    @pytest.mark.parametrize("phone", [
        "01012345678",       # 휴대폰 11자리
        "010-1234-5678",     # 하이픈
        "010 1234 5678",     # 공백
        "0212345678",        # 서울 10자리
        "02-123-4567",       # 서울 9자리
        "070-1234-5678",     # 인터넷전화
        "050714989680",      # 12자리
    ])
    def test_valid_formats(self, phone):
        assert is_valid_phone(phone) is True

    @pytest.mark.parametrize("phone", [
        "",                  # 빈 문자열
        "12345678",          # 8자리 (너무 짧음)
        "0123456789012345",  # 16자리 (너무 김)
        "abc-defg-hijk",     # 숫자 없음
        "-----",             # 하이픈만
    ])
    def test_invalid_formats(self, phone):
        assert is_valid_phone(phone) is False
