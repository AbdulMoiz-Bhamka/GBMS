# app/modules/auth/schemas.py
from pydantic import BaseModel, ConfigDict, Field, model_validator


class LoginPayload(BaseModel):
    username: str = Field(min_length=1, max_length=80)
    password: str = Field(min_length=1, max_length=1024)


class ChangePasswordPayload(BaseModel):
    model_config = ConfigDict(extra="forbid")
    current_password: str = Field(min_length=1, max_length=1024)
    new_password: str = Field(min_length=12, max_length=128)
    confirm_password: str = Field(min_length=12, max_length=128)

    @model_validator(mode="after")
    def validate_new_password(self):
        if self.new_password != self.confirm_password:
            raise ValueError("New password and confirmation do not match.")
        if not any(character.isalpha() for character in self.new_password) or not any(
            character.isdigit() for character in self.new_password
        ):
            raise ValueError("New password must contain at least one letter and one number.")
        return self
