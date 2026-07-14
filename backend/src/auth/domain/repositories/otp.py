from abc import ABC, abstractmethod


class OTPRepository(ABC):
    @abstractmethod
    def save_otp(self, _phone: str, _otp: str, ttl: int) -> None: ...

    @abstractmethod
    def get_otp(self, _phone: str) -> str | None: ...

    @abstractmethod
    def verify_otp(self, _phone: str, _otp: str) -> bool: ...

    @abstractmethod
    def delete_otp(self, _phone: str) -> None: ...
