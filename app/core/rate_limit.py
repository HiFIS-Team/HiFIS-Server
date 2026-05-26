"""API rate limiting - IP 기준 인메모리 limiter (slowapi)

라우터에서 @limiter.limit("N/minute") 데코레이터로 엔드포인트별 제한을 건다.
테스트에서는 conftest가 limiter.enabled=False로 끈다 (반복 호출이 429로 깨지지 않게).
"""
from slowapi import Limiter
from slowapi.util import get_remote_address

# key_func=get_remote_address → 클라이언트 IP 기준으로 호출 횟수 집계.
# 리버스 프록시(nginx 등) 뒤에 배포할 때는 uvicorn을 --proxy-headers 옵션으로
# 띄워야 프록시 IP가 아닌 실제 클라이언트 IP가 잡힌다.
limiter = Limiter(key_func=get_remote_address)
