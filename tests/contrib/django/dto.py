from pydantic import BaseModel, ConfigDict


class SchoolDTO(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    name: str


class StudentDTO(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    name: str
    school_id: int


class CourseDTO(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    title: str


class StudentProfileDTO(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    student_id: int
    nickname: str
