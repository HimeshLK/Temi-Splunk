from pydantic import BaseModel, EmailStr, Field

class RegistrationIn(BaseModel):
    name: str = Field(min_length=1, max_length=120)
    email: EmailStr
    designation: str = Field(default="", max_length=120)
    # company: str = Field(default="", max_length=120)  - As loshani Mentioned not required
    # phone: str = Field(default="", max_length=20) - As loshani Mentioned not required

class FeedbackIn(BaseModel):
    rating: int = Field(ge=1, le=5)
    comment: str = Field(default="", max_length=2000)
