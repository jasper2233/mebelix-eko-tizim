from pydantic import BaseModel


class Token(BaseModel):
    access_token: str
    token_type: str


class TokenData(BaseModel):
    # Identifier the JWT subject resolves to — either a username or an E.164 phone (`+998…`).
    username_or_phone: str
    token_version: int = 0
